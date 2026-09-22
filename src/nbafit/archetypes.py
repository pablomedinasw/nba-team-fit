"""Arquetipos de jugador: PCA + Gaussian Mixture sobre el perfil de estilo.

Los estilos NBA son un continuo, no grupos separados (silueta ~0.1-0.2),
así que además de la etiqueta se guarda la probabilidad de pertenecer a
cada arquetipo: un jugador híbrido se reparte entre varios.

Uso:
    python -m nbafit.archetypes            # ajusta y guarda data/processed/archetypes.parquet
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture

from nbafit.config import DATA_DIR
from nbafit.features import KEYS, build_profiles, standardize_by_season

PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_PATH = PROCESSED_DIR / "archetypes.parquet"

N_ARCHETYPES = 8
PCA_VARIANCE = 0.90
SEED = 0


@dataclass(frozen=True)
class Archetype:
    name: str
    description: str
    anchor: tuple[str, str]  # (jugador, temporada) que define el grupo


# El nombre de cada grupo se asigna por el jugador ancla que contiene, no por
# el número del cluster (que puede cambiar si cambian los datos).
ARCHETYPES: list[Archetype] = [
    Archetype("Creador principal", "Mucho uso y tiro propio, media distancia", ("Jalen Brunson", "2025-26")),
    Archetype("Base / escolta exterior", "Bajitos, triples en volumen y algo de creación", ("Tyrese Maxey", "2025-26")),
    Archetype("Tirador 3&D", "Poco uso, casi todo triples asistidos", ("Donte DiVincenzo", "2025-26")),
    Archetype("Conector defensivo", "Robos, contraataque, poco tiro", ("Dyson Daniels", "2025-26")),
    Archetype("Alero anotador", "Aleros/ala-pívots de volumen, penetran y tiran", ("Paolo Banchero", "2025-26")),
    Archetype("Pívot moderno", "Grandes que rebotean, taponan y abren algo el campo", ("Evan Mobley", "2025-26")),
    Archetype("Pívot de referencia", "Grandes con mucho uso y rebote dominante; incluye organizadores", ("Nikola Jokić", "2025-26")),
    Archetype("Pívot de pintura", "Sin tiro exterior: rebote ofensivo, tapón, continuación", ("Rudy Gobert", "2025-26")),
]
ARCHETYPE_NAMES = [a.name for a in ARCHETYPES]


@dataclass
class ArchetypeModel:
    profiles: pd.DataFrame      # identificación + variables sin escalar
    z: pd.DataFrame             # variables estandarizadas por temporada
    pca: PCA
    gmm: GaussianMixture
    components: np.ndarray      # coordenadas PCA de cada jugador-temporada
    cluster_names: list[str]    # nombre de cada componente del GMM

    def predict_proba(self, z: pd.DataFrame) -> pd.DataFrame:
        """Probabilidad de cada arquetipo para perfiles ya estandarizados (p. ej. jugadores nuevos)."""
        probs = self.gmm.predict_proba(self.pca.transform(z[self.z.columns]))
        return pd.DataFrame(probs, columns=self.cluster_names, index=z.index)[ARCHETYPE_NAMES]

    def assignments(self) -> pd.DataFrame:
        """Una fila por jugador-temporada: arquetipo, probabilidad y reparto entre arquetipos."""
        probs = pd.DataFrame(self.gmm.predict_proba(self.components), columns=self.cluster_names)
        probs = probs[ARCHETYPE_NAMES]
        out = self.profiles[KEYS + ["PLAYER_NAME", "TEAM_ABBREVIATION", "MIN"]].copy()
        out["archetype"] = probs.idxmax(axis=1)
        out["archetype_prob"] = probs.max(axis=1)
        for i in range(2):
            out[f"PC{i + 1}"] = self.components[:, i]
        return pd.concat([out, probs.add_prefix("p_")], axis=1)


def _name_clusters(profiles: pd.DataFrame, labels: np.ndarray) -> list[str]:
    names: dict[int, str] = {}
    for arch in ARCHETYPES:
        player, season = arch.anchor
        mask = (profiles["PLAYER_NAME"] == player) & (profiles["SEASON"] == season)
        if mask.sum() != 1:
            raise ValueError(f"Ancla no encontrada: {arch.anchor}")
        cluster = int(labels[mask.to_numpy()][0])
        if cluster in names:
            raise ValueError(f"'{arch.name}' y '{names[cluster]}' caen en el mismo cluster: revisar anclas")
        names[cluster] = arch.name
    return [names[i] for i in range(len(names))]


def fit(seasons: list[str] | None = None, k: int = N_ARCHETYPES, seed: int = SEED) -> ArchetypeModel:
    profiles = build_profiles(seasons)
    z = standardize_by_season(profiles)
    pca = PCA(n_components=PCA_VARIANCE, random_state=seed)
    components = pca.fit_transform(z)
    gmm = GaussianMixture(k, covariance_type="full", n_init=10, random_state=seed).fit(components)
    names = _name_clusters(profiles, gmm.predict(components))
    return ArchetypeModel(profiles, z, pca, gmm, components, names)


def main() -> None:
    model = fit()
    out = model.assignments()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"{len(out)} jugador-temporadas, {model.pca.n_components_} componentes PCA -> {OUTPUT_PATH}")
    print(out.groupby("archetype").agg(n=("PLAYER_ID", "size"), prob_media=("archetype_prob", "mean")).round(2))


if __name__ == "__main__":
    main()
