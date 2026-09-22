"""Perfil de estilo de cada jugador-temporada.

El perfil describe QUÉ hace un jugador (rol), no LO BIEN que lo hace:
la eficiencia se deja fuera a propósito para que los arquetipos agrupen
roles y no niveles. La calidad se evalúa aparte (fit y valor).
"""

import pandas as pd

from nbafit import storage

KEYS = ["PLAYER_ID", "SEASON"]

# Mínimo de minutos totales en la temporada para tener un perfil fiable.
MIN_MINUTES = 500

# Variables de estilo: nombre -> descripción.
STYLE_FEATURES: dict[str, str] = {
    "usg": "% de jugadas del equipo que termina (USG%)",
    "ast_pct": "% de canastas de compañeros que asiste",
    "fg3a_100": "Triples intentados por 100 posesiones",
    "fg3a_rate": "Fracción de sus tiros que son triples",
    "fta_rate": "Tiros libres intentados por tiro de campo",
    "paint_share": "% de sus puntos en la pintura",
    "midrange_share": "% de sus puntos de media distancia",
    "fastbreak_share": "% de sus puntos al contraataque",
    "self_created": "% de sus canastas no asistidas",
    "oreb_pct": "% de rebotes ofensivos disponibles que coge",
    "dreb_pct": "% de rebotes defensivos disponibles que coge",
    "stl_100": "Robos por 100 posesiones",
    "blk_100": "Tapones por 100 posesiones",
    "height_in": "Altura (pulgadas)",
    "weight_lb": "Peso (libras)",
}


def _load_joined(seasons: list[str] | None) -> pd.DataFrame:
    base = storage.load("player_base", seasons)
    adv = storage.load("player_advanced", seasons)
    scoring = storage.load("player_scoring", seasons)
    bio = storage.load("player_bio", seasons)

    # MIN se toma de player_base (totales); en advanced/scoring es por partido.
    df = base[KEYS + ["PLAYER_NAME", "TEAM_ABBREVIATION", "TEAM_COUNT", "AGE", "GP", "MIN",
                      "FGA", "FG3A", "FTA", "STL", "BLK"]]
    df = df.merge(adv[KEYS + ["POSS", "USG_PCT", "AST_PCT", "OREB_PCT", "DREB_PCT"]], on=KEYS, validate="1:1")
    df = df.merge(scoring[KEYS + ["PCT_PTS_PAINT", "PCT_PTS_2PT_MR", "PCT_PTS_FB", "PCT_UAST_FGM"]],
                  on=KEYS, validate="1:1")
    df = df.merge(bio[KEYS + ["PLAYER_HEIGHT_INCHES", "PLAYER_WEIGHT"]], on=KEYS, how="left", validate="1:1")
    return df


def build_profiles(seasons: list[str] | None = None, min_minutes: int = MIN_MINUTES) -> pd.DataFrame:
    """Una fila por jugador-temporada con >= `min_minutes`: identificación + STYLE_FEATURES (sin escalar)."""
    df = _load_joined(seasons)
    df = df[df["MIN"] >= min_minutes].copy()

    per100 = 100 / df["POSS"]
    fga = df["FGA"].where(df["FGA"] > 0)
    weight = pd.to_numeric(df["PLAYER_WEIGHT"], errors="coerce")

    feats = pd.DataFrame(
        {
            "usg": df["USG_PCT"],
            "ast_pct": df["AST_PCT"],
            "fg3a_100": df["FG3A"] * per100,
            "fg3a_rate": df["FG3A"] / fga,
            "fta_rate": df["FTA"] / fga,
            "paint_share": df["PCT_PTS_PAINT"],
            "midrange_share": df["PCT_PTS_2PT_MR"],
            "fastbreak_share": df["PCT_PTS_FB"],
            "self_created": df["PCT_UAST_FGM"],
            "oreb_pct": df["OREB_PCT"],
            "dreb_pct": df["DREB_PCT"],
            "stl_100": df["STL"] * per100,
            "blk_100": df["BLK"] * per100,
            "height_in": df["PLAYER_HEIGHT_INCHES"].astype(float),
            "weight_lb": weight,
        },
        index=df.index,
    )

    # Peso ausente (pocos casos): mediana de los jugadores de su misma altura.
    feats["weight_lb"] = feats["weight_lb"].fillna(
        feats.groupby("height_in")["weight_lb"].transform("median")
    )

    ident = df[KEYS + ["PLAYER_NAME", "TEAM_ABBREVIATION", "TEAM_COUNT", "AGE", "GP", "MIN", "POSS"]]
    out = pd.concat([ident, feats], axis=1).reset_index(drop=True)
    missing = out[list(STYLE_FEATURES)].isna().sum()
    if missing.any():
        raise ValueError(f"Valores nulos en el perfil:\n{missing[missing > 0]}")
    return out


def standardize_by_season(
    profiles: pd.DataFrame,
    features: list[str] | None = None,
    reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """z-score de cada variable dentro de su temporada (ponderado por igual a cada jugador).

    Así un jugador se compara con la liga de su año: el aumento general de
    triples no se confunde con un cambio de rol. Con `reference`, la media y
    la desviación se toman de ese conjunto (p. ej. los jugadores con >=500 min)
    en vez de del propio `profiles`.
    """
    features = features or list(STYLE_FEATURES)
    ref = profiles if reference is None else reference
    stats = ref.groupby("SEASON")[features].agg(["mean", "std"])
    mean = stats.xs("mean", axis=1, level=1).loc[profiles["SEASON"]].to_numpy()
    std = stats.xs("std", axis=1, level=1).loc[profiles["SEASON"]].to_numpy()
    return pd.DataFrame((profiles[features].to_numpy() - mean) / std, columns=features, index=profiles.index)


def shrink_low_minutes(z: pd.DataFrame, minutes: pd.Series, full_at: int = MIN_MINUTES) -> pd.DataFrame:
    """Acerca a la media de la liga (z = 0) el perfil de quien tiene pocos minutos.

    Con `full_at` minutos o más no se toca; por debajo se multiplica por
    minutos / full_at: un jugador con 100 min conserva el 20 % de su perfil.
    """
    factor = (minutes / full_at).clip(upper=1.0).to_numpy()[:, None]
    return z * factor
