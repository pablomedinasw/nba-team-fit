"""Lectura y escritura de la capa raw en Parquet.

Estructura: data/raw/<dataset>/season=<temporada>.parquet
Un archivo por dataset y temporada, así se puede recargar una sola temporada.
"""

from pathlib import Path

import duckdb
import pandas as pd

from nbafit.config import RAW_DIR


def season_path(dataset: str, season: str) -> Path:
    return RAW_DIR / dataset / f"season={season}.parquet"


def exists(dataset: str, season: str) -> bool:
    return season_path(dataset, season).exists()


def save(df: pd.DataFrame, dataset: str, season: str) -> Path:
    path = season_path(dataset, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Se escribe primero a un temporal para no dejar archivos a medias.
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path


def load(dataset: str, seasons: list[str] | None = None) -> pd.DataFrame:
    """Carga un dataset (todas las temporadas descargadas o solo `seasons`)."""
    files = sorted((RAW_DIR / dataset).glob("season=*.parquet"))
    if seasons is not None:
        files = [f for f in files if f.stem.removeprefix("season=") in seasons]
    if not files:
        raise FileNotFoundError(f"No hay datos para '{dataset}' en {RAW_DIR}")
    paths = [str(f) for f in files]
    return duckdb.read_parquet(paths, union_by_name=True).df()
