"""¿Qué jugador completa mejor un núcleo de jugadores?

Para cada candidato se calcula:
    calidad  = su impacto individual (pts/100 posesiones, RAPM)
    fit      = cuánto mejora la complementariedad del quinteto núcleo + candidato,
               respecto al candidato medio (pts/100)
    total    = calidad + fit

Si el núcleo tiene menos de 4 jugadores, los huecos se rellenan con un
jugador de composición media de la liga.

Uso:
    python -m nbafit.recommend --team DEN                  # núcleo = los 4 con más minutos
    python -m nbafit.recommend --players "Jokić" "Murray"  # núcleo a mano
    python -m nbafit.recommend --team BOS --sort fit --top 20
"""

import argparse
import unicodedata

import numpy as np
import pandas as pd

from nbafit import fit_model
from nbafit.archetypes import ARCHETYPE_NAMES

PROB_COLS = [f"p_{a}" for a in ARCHETYPE_NAMES]
CANDIDATE_MIN_MINUTES = 500


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def find_players(season_players: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Busca cada nombre (sin acentos, coincidencia parcial). Error si no hay exactamente uno."""
    norm = season_players["PLAYER_NAME"].map(_norm)
    rows = []
    for name in names:
        hits = season_players[norm.str.contains(_norm(name), regex=False)]
        if len(hits) != 1:
            options = ", ".join(hits["PLAYER_NAME"].head(8)) or "ninguno"
            raise SystemExit(f"'{name}' coincide con {len(hits)} jugadores: {options}")
        rows.append(hits)
    return pd.concat(rows)


def team_core(season_players: pd.DataFrame, team: str, size: int = 4) -> pd.DataFrame:
    team_players = season_players[season_players["TEAM_ABBREVIATION"] == team.upper()]
    if team_players.empty:
        raise SystemExit(f"No hay jugadores del equipo '{team}'")
    return team_players.nlargest(size, "MIN")


def _core_counts(model: fit_model.FitModel, core: pd.DataFrame, season: str) -> np.ndarray:
    """Recuento de arquetipos del núcleo; los huecos hasta 4 se rellenan con la composición media."""
    players = model.players[model.players["SEASON"] == season]
    league_avg = np.average(players[PROB_COLS].to_numpy(), axis=0, weights=players["MIN"])
    return core[PROB_COLS].to_numpy().sum(axis=0) + max(0, 4 - len(core)) * league_avg


def archetype_fit(model: fit_model.FitModel, core: pd.DataFrame, season: str) -> pd.DataFrame:
    """Fit de un jugador 'puro' de cada arquetipo con el núcleo, respecto a la media de arquetipos."""
    base = _core_counts(model, core, season)
    pure = np.eye(len(ARCHETYPE_NAMES))
    out = pd.DataFrame({key: model.fit_with(base, pure, key) for key in ["net", "off", "def"]},
                       index=ARCHETYPE_NAMES)
    return (out - out.mean()).sort_values("net", ascending=False)


def recommend(model: fit_model.FitModel, core: pd.DataFrame, season: str) -> pd.DataFrame:
    players = model.players[model.players["SEASON"] == season]
    candidates = players[(players["MIN"] >= CANDIDATE_MIN_MINUTES) & ~players["PLAYER_ID"].isin(core["PLAYER_ID"])]
    base = _core_counts(model, core, season)

    out = candidates[["PLAYER_NAME", "TEAM_ABBREVIATION", "MIN", "q_net", "q_off", "q_def"]].copy()
    out["archetype"] = candidates[PROB_COLS].to_numpy().argmax(axis=1)
    out["archetype"] = out["archetype"].map(dict(enumerate(ARCHETYPE_NAMES)))
    for key in ["net", "off", "def"]:
        fit = model.fit_with(base, candidates[PROB_COLS].to_numpy(), key)
        out[f"fit_{key}"] = fit - np.average(fit, weights=candidates["MIN"])
    out = out.rename(columns={"q_net": "calidad", "fit_net": "fit"})
    out["total"] = out["calidad"] + out["fit"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m nbafit.recommend", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--team", help="Abreviatura del equipo (núcleo = sus 4 jugadores con más minutos)")
    group.add_argument("--players", nargs="+", help="Jugadores del núcleo (1 a 4)")
    parser.add_argument("--season", default=None, help="Temporada (por defecto, la más reciente)")
    parser.add_argument("--sort", choices=["total", "fit", "calidad"], default="total")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    model = fit_model.load()
    season = args.season or model.players["SEASON"].max()
    season_players = model.players[model.players["SEASON"] == season]
    core = team_core(season_players, args.team) if args.team else find_players(season_players, args.players)
    if not 1 <= len(core) <= 4:
        raise SystemExit("El núcleo debe tener entre 1 y 4 jugadores")

    print(f"Núcleo ({season}): " + ", ".join(core["PLAYER_NAME"]))
    by_role = archetype_fit(model, core, season).rename(columns={"net": "fit", "off": "fit_off", "def": "fit_def"})
    print("\nQué rol encaja mejor:")
    print(by_role.round(2).to_string())
    res = recommend(model, core, season).nlargest(args.top, args.sort)
    cols = ["PLAYER_NAME", "TEAM_ABBREVIATION", "archetype", "calidad", "fit", "total", "fit_off", "fit_def"]
    print(f"\nMejores candidatos (orden: {args.sort}):")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(res[cols].round(2).to_string(index=False))
    print("\ncalidad, fit y total en pts/100 posesiones. fit_def negativo = mejor defensa.")


if __name__ == "__main__":
    main()
