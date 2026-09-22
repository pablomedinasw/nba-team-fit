"""Tabla de quintetos con el perfil de sus cinco jugadores.

Cada fila es un quinteto-temporada con su net rating y posesiones. Los
jugadores con al menos PROFILE_MIN_MINUTES tienen perfil de estilo; los de
menos de 500 min se acercan a la media (shrinkage) porque su perfil es ruidoso.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from nbafit import storage
from nbafit.archetypes import ARCHETYPE_NAMES, ArchetypeModel
from nbafit.features import KEYS, MIN_MINUTES, STYLE_FEATURES, build_profiles, shrink_low_minutes, standardize_by_season

# Jugadores con menos minutos no tienen perfil; sus quintetos se descartan
# (son el ~2 % de las posesiones).
PROFILE_MIN_MINUTES = 100


@dataclass
class LineupData:
    lineups: pd.DataFrame   # una fila por quinteto-temporada
    players: pd.DataFrame   # una fila por jugador-temporada con perfil (z) y arquetipos (p_*)
    slots: np.ndarray       # (n_quintetos, 5) índices de fila en `players`


def player_table(model: ArchetypeModel) -> pd.DataFrame:
    """Perfil estandarizado (con shrinkage) y probabilidades de arquetipo de cada jugador-temporada."""
    profiles = build_profiles(min_minutes=PROFILE_MIN_MINUTES)
    reference = profiles[profiles["MIN"] >= MIN_MINUTES]
    z = standardize_by_season(profiles, reference=reference)
    z = shrink_low_minutes(z, profiles["MIN"])
    probs = model.predict_proba(z).add_prefix("p_")
    ident = profiles[KEYS + ["PLAYER_NAME", "TEAM_ABBREVIATION", "MIN", "POSS"]]
    return pd.concat([ident, z, probs], axis=1).reset_index(drop=True)


def build(model: ArchetypeModel) -> LineupData:
    players = player_table(model)
    row_of = {(pid, season): i for i, (pid, season) in enumerate(zip(players["PLAYER_ID"], players["SEASON"]))}

    raw = storage.load("lineups_advanced")
    raw = raw[raw["POSS"] > 0]
    ids = raw["GROUP_ID"].str.strip("-").str.split("-")
    slots = np.array([[row_of.get((int(p), s), -1) for p in group] for group, s in zip(ids, raw["SEASON"])])
    complete = (slots >= 0).all(axis=1)

    lineups = raw.loc[complete, ["SEASON", "TEAM_ID", "TEAM_ABBREVIATION", "GROUP_ID", "GROUP_NAME", "MIN", "POSS",
                                 "OFF_RATING", "DEF_RATING", "NET_RATING"]].reset_index(drop=True)
    kept = lineups["POSS"].sum() / raw["POSS"].sum()
    print(f"Quintetos: {len(lineups)} de {len(raw)} ({kept:.1%} de las posesiones)")
    return LineupData(lineups, players, slots[complete])


def archetype_counts(data: LineupData) -> pd.DataFrame:
    """Suma de probabilidades de cada arquetipo en el quinteto (≈ nº de jugadores de ese rol)."""
    p = data.players[[f"p_{a}" for a in ARCHETYPE_NAMES]].to_numpy()
    counts = p[data.slots].sum(axis=1)
    return pd.DataFrame(counts, columns=ARCHETYPE_NAMES)


def style_sums(data: LineupData) -> pd.DataFrame:
    """Suma de cada variable de estilo (z) en el quinteto."""
    z = data.players[list(STYLE_FEATURES)].to_numpy()
    return pd.DataFrame(z[data.slots].sum(axis=1), columns=list(STYLE_FEATURES))
