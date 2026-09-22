"""Modelo de quintetos: calidad individual + complementariedad entre roles.

    rating del quinteto = intercepto
                        + suma de la calidad de sus 5 jugadores      (efecto común del jugador + desviación por temporada)
                        + control de tiempo basura                  (minutos de temporada de los 5)
                        + complementariedad                         (interacciones entre arquetipos)

Todo se ajusta a la vez con ridge ponderado por posesiones. La calidad es un
RAPM calculado sobre quintetos; el efecto común reparte información entre
temporadas (una sola temporada es muy ruidosa). La complementariedad solo usa términos
cruzados entre arquetipos: los efectos lineales ("tener un creador suma X")
ya los recoge la calidad de cada jugador, así que el fit es lo NO aditivo:
lo que un quinteto rinde por encima o por debajo de la suma de sus partes.

Uso:
    python -m nbafit.fit_model                       # entrena, valida y guarda el modelo
"""

import itertools
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

from nbafit import archetypes, lineups
from nbafit.archetypes import ARCHETYPE_NAMES
from nbafit.config import DATA_DIR

PLAYERS_PATH = DATA_DIR / "processed" / "fit_players.parquet"
INTERACTIONS_PATH = DATA_DIR / "processed" / "fit_interactions.json"
VALIDATION_PATH = DATA_DIR / "processed" / "fit_validation.json"

# Penalizaciones ridge (elegidas por validación cruzada, ver bitácora).
LAMBDA_PLAYER = 5000          # efecto común a todas las temporadas del jugador
LAMBDA_PLAYER_SEASON = 30000  # desviación de cada temporada respecto a ese efecto
LAMBDA_CONTROL = 1e4
LAMBDA_PAIRS = 1e6

N_BOOT = 50  # réplicas bootstrap para la incertidumbre de los efectos de pareja

PAIRS = list(itertools.combinations_with_replacement(range(len(ARCHETYPE_NAMES)), 2))
TARGETS = {"net": "NET_RATING", "off": "OFF_RATING", "def": "DEF_RATING"}


def _pair_features(counts: np.ndarray) -> np.ndarray:
    return np.column_stack([counts[:, a] * counts[:, b] for a, b in PAIRS])


def _control_features(data: lineups.LineupData) -> np.ndarray:
    """Proxy de tiempo basura: cuántos jugadores de pocos minutos hay y cuántos minutos juegan."""
    mins = data.players["MIN"].to_numpy()[data.slots]
    low = (mins < 500).sum(axis=1)
    log_mean = np.log(mins).mean(axis=1)
    log_min = np.log(mins).min(axis=1)
    return np.column_stack([low, low**2, log_mean, log_mean**2, log_min, log_min**2])


def _standardize(A: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean, std = A.mean(axis=0), A.std(axis=0)
    return (A - mean) / std, mean, std


@dataclass
class Design:
    X: sp.csr_matrix
    player_codes: np.ndarray  # fila de data.players -> índice del jugador (común a sus temporadas)
    n_players: int
    n_player_seasons: int
    n_control: int
    pair_std: np.ndarray


def build_design(data: lineups.LineupData, with_pairs: bool = True) -> Design:
    n = len(data.lineups)
    rows = np.repeat(np.arange(n), 5)
    codes = np.unique(data.players["PLAYER_ID"].to_numpy(), return_inverse=True)[1]
    P = sp.csr_matrix((np.ones(n * 5), (rows, codes[data.slots.ravel()])), shape=(n, codes.max() + 1))
    PS = sp.csr_matrix((np.ones(n * 5), (rows, data.slots.ravel())), shape=(n, len(data.players)))
    C, _, _ = _standardize(_control_features(data))
    blocks = [P / np.sqrt(LAMBDA_PLAYER), PS / np.sqrt(LAMBDA_PLAYER_SEASON),
              sp.csr_matrix(C / np.sqrt(LAMBDA_CONTROL))]
    pair_std = np.ones(len(PAIRS))
    if with_pairs:
        Phi, _, pair_std = _standardize(_pair_features(lineups.archetype_counts(data).to_numpy()))
        blocks.append(sp.csr_matrix(Phi / np.sqrt(LAMBDA_PAIRS)))
    return Design(sp.hstack(blocks).tocsr(), codes, P.shape[1], PS.shape[1], C.shape[1], pair_std)


def _ridge() -> Ridge:
    # Las penalizaciones ya van en la escala de las columnas; alpha=1 las aplica.
    return Ridge(alpha=1.0, solver="sparse_cg", max_iter=5000, tol=1e-7)


@dataclass
class FitModel:
    players: pd.DataFrame        # jugador-temporada: perfil, arquetipos y calidad (q_net, q_off, q_def)
    interactions: dict[str, np.ndarray]  # objetivo -> matriz 8x8 M: complementariedad = c' M c + cte
    pair_se: dict[str, np.ndarray] = field(default_factory=dict)  # objetivo -> error típico (bootstrap)

    def pair_effects(self, target: str = "net", shrink: bool = True) -> pd.DataFrame:
        """Efecto de juntar un jugador de cada rol, respecto al compañero medio (pts/100).

        Como un quinteto siempre suma 5 jugadores, M solo está identificada salvo
        términos lineales (que ya recoge la calidad de cada jugador); el doble
        centrado los elimina y deja la interacción pura.

        Con `shrink`, cada efecto se encoge hacia 0 según su incertidumbre
        (Bayes empírico): efecto * tau² / (tau² + se²), donde tau² es la varianza
        real entre parejas (varianza de los efectos menos la del ruido).
        """
        M = self.interactions[target]
        k = len(M)
        H = np.eye(k) - np.ones((k, k)) / k
        effects = 2 * H @ M @ H
        if shrink and target in self.pair_se:
            se = self.pair_se[target]
            iu = np.triu_indices(k)
            tau2 = max(0.0, effects[iu].var() - np.mean(se[iu] ** 2))
            effects = effects * tau2 / (tau2 + se**2)
        return pd.DataFrame(effects, index=ARCHETYPE_NAMES, columns=ARCHETYPE_NAMES)

    def fit_with(self, base_counts: np.ndarray, candidates: np.ndarray, target: str = "net") -> np.ndarray:
        """Fit de cada candidato (filas de probabilidades, n x 8) con el resto del quinteto (8,).

        Es la suma de sus efectos de pareja (encogidos) con cada compañero: solo
        términos cruzados, sin el propio candidato consigo mismo (eso es calidad, no fit).
        """
        return candidates @ self.pair_effects(target).to_numpy() @ base_counts


def _fit_target(design: Design, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ajusta un objetivo y devuelve (calidad por jugador-temporada, matriz de interacciones M)."""
    coef = _ridge().fit(design.X, y, sample_weight=w).coef_
    shared = coef[: design.n_players] / np.sqrt(LAMBDA_PLAYER)
    season = coef[design.n_players: design.n_players + design.n_player_seasons] / np.sqrt(LAMBDA_PLAYER_SEASON)
    start = design.n_players + design.n_player_seasons + design.n_control
    beta = coef[start:] / np.sqrt(LAMBDA_PAIRS) / design.pair_std
    M = np.zeros((len(ARCHETYPE_NAMES), len(ARCHETYPE_NAMES)))
    for (a, b), v in zip(PAIRS, beta):
        M[a, b] += v / 2
        M[b, a] += v / 2
    return shared[design.player_codes] + season, M


def train(data: lineups.LineupData) -> FitModel:
    design = build_design(data)
    w = data.lineups["POSS"].to_numpy(float)
    players = data.players.copy()
    interactions = {}
    for key, col in TARGETS.items():
        players[f"q_{key}"], interactions[key] = _fit_target(design, data.lineups[col].to_numpy(), w)
    return FitModel(players, interactions)


def bootstrap_pair_effects(data: lineups.LineupData, n_boot: int = 30, target: str = "net",
                           seed: int = 0) -> np.ndarray:
    """Efectos de pareja (n_boot x 8 x 8) re-ajustando con quintetos remuestreados.

    Bootstrap de Poisson: cada quinteto recibe un peso Poisson(1), equivalente
    a remuestrear con reemplazo.
    """
    design = build_design(data)
    y = data.lineups[TARGETS[target]].to_numpy()
    w = data.lineups["POSS"].to_numpy(float)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        _, M = _fit_target(design, y, w * rng.poisson(1.0, len(w)))
        out.append(FitModel(data.players, {target: M}).pair_effects(target).to_numpy())
    return np.array(out)


def validate(data: lineups.LineupData, reps: int = 4) -> dict:
    """Compara fuera de muestra el modelo sin y con complementariedad (mismas particiones)."""
    y = data.lineups["NET_RATING"].to_numpy()
    w = data.lineups["POSS"].to_numpy(float)
    X0 = build_design(data, with_pairs=False).X
    X1 = build_design(data, with_pairs=True).X
    rows = []
    for r in range(reps):
        for tr, te in KFold(5, shuffle=True, random_state=r).split(y):
            mu = np.average(y[tr], weights=w[tr])
            sse_base = np.sum(w[te] * (y[te] - mu) ** 2)
            sse = [np.sum(w[te] * (y[te] - _ridge().fit(X[tr], y[tr], sample_weight=w[tr]).predict(X[te])) ** 2)
                   for X in (X0, X1)]
            rows.append((sse_base, *sse))
    a = np.array(rows)
    gain = (a[:, 1] - a[:, 2]) / a[:, 0]
    return {
        "r2_quality": float(1 - a[:, 1].sum() / a[:, 0].sum()),
        "r2_quality_fit": float(1 - a[:, 2].sum() / a[:, 0].sum()),
        "gain_per_fold": gain.tolist(),
        "folds_improved": float(np.mean(gain > 0)),
        "t_stat": float(gain.mean() / (gain.std(ddof=1) / np.sqrt(len(gain)))),
    }


def load() -> FitModel:
    players = pd.read_parquet(PLAYERS_PATH)
    stored = json.loads(INTERACTIONS_PATH.read_text())
    interactions = {k: np.array(v) for k, v in stored["interactions"].items()}
    pair_se = {k: np.array(v) for k, v in stored["pair_se"].items()}
    return FitModel(players, interactions, pair_se)


def save(model: FitModel) -> None:
    PLAYERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.players.to_parquet(PLAYERS_PATH, index=False)
    INTERACTIONS_PATH.write_text(json.dumps({
        "interactions": {k: v.tolist() for k, v in model.interactions.items()},
        "pair_se": {k: v.tolist() for k, v in model.pair_se.items()},
    }))


def main() -> None:
    arch = archetypes.fit()
    data = lineups.build(arch)
    print("Validando (5-fold x 4)...")
    val = validate(data)
    print(f"  R² calidad: {val['r2_quality']:.4f} | calidad + fit: {val['r2_quality_fit']:.4f} | "
          f"mejora en {val['folds_improved']:.0%} de los folds (t = {val['t_stat']:.1f})")
    print("Entrenando modelo final...")
    model = train(data)
    print(f"Bootstrap de los efectos de pareja ({N_BOOT} réplicas por objetivo)...")
    model.pair_se = {key: bootstrap_pair_effects(data, N_BOOT, key).std(axis=0) for key in TARGETS}
    save(model)
    VALIDATION_PATH.write_text(json.dumps(val, indent=2))
    print(f"  -> {PLAYERS_PATH.parent}")


if __name__ == "__main__":
    main()
