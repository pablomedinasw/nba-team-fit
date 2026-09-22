"""Descarga de estadísticas desde stats.nba.com (vía nba_api).

Todo se guarda en totales (no per game ni per 100) para conservar los
conteos brutos: las tasas se calculan después, y los conteos hacen falta
para ponderar por minutos o aplicar shrinkage a jugadores con pocos datos.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd
from nba_api.stats.endpoints import (
    leaguedashlineups,
    leaguedashplayerbiostats,
    leaguedashplayerstats,
)
from nba_api.stats.static import teams

from nbafit import storage
from nbafit.config import MAX_RETRIES, REQUEST_DELAY_S, REQUEST_TIMEOUT_S

log = logging.getLogger(__name__)

SEASON_TYPE = "Regular Season"


def _call(endpoint_cls, **params) -> pd.DataFrame:
    """Llama a un endpoint con pausa y reintentos con backoff exponencial."""
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY_S)
        try:
            resp = endpoint_cls(timeout=REQUEST_TIMEOUT_S, **params)
            return resp.get_data_frames()[0]
        except Exception as exc:  # timeouts, 429, respuestas vacías...
            if attempt == MAX_RETRIES:
                raise
            wait = 2**attempt
            log.warning("%s falló (%s). Reintento %d en %ds", endpoint_cls.__name__, exc, attempt, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _clean(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Quita las columnas de ranking (ruido) y añade la temporada."""
    df = df.loc[:, [c for c in df.columns if not c.endswith("_RANK")]]
    return df.assign(SEASON=season)


def _player_stats(measure: str) -> Callable[[str], pd.DataFrame]:
    def fetch(season: str) -> pd.DataFrame:
        return _call(
            leaguedashplayerstats.LeagueDashPlayerStats,
            season=season,
            season_type_all_star=SEASON_TYPE,
            measure_type_detailed_defense=measure,
            per_mode_detailed="Totals",
        )

    return fetch


def _player_bio(season: str) -> pd.DataFrame:
    return _call(
        leaguedashplayerbiostats.LeagueDashPlayerBioStats,
        season=season,
        season_type_all_star=SEASON_TYPE,
    )


def _lineups(measure: str) -> Callable[[str], pd.DataFrame]:
    # La consulta de toda la liga se corta en 2000 filas, así que se pide
    # equipo a equipo (cada equipo tiene unos cientos de quintetos).
    def fetch(season: str) -> pd.DataFrame:
        frames = []
        for team in teams.get_teams():
            frames.append(
                _call(
                    leaguedashlineups.LeagueDashLineups,
                    season=season,
                    season_type_all_star=SEASON_TYPE,
                    team_id_nullable=team["id"],
                    group_quantity=5,
                    measure_type_detailed_defense=measure,
                    per_mode_detailed="Totals",
                )
            )
        return pd.concat(frames, ignore_index=True)

    return fetch


@dataclass(frozen=True)
class Dataset:
    name: str
    fetch: Callable[[str], pd.DataFrame]
    description: str


DATASETS: dict[str, Dataset] = {
    d.name: d
    for d in [
        Dataset("player_base", _player_stats("Base"), "Box score clásico (conteos)"),
        Dataset("player_advanced", _player_stats("Advanced"), "Ratings, USG%, TS%, posesiones"),
        Dataset("player_scoring", _player_stats("Scoring"), "Origen de los puntos, % asistidos"),
        Dataset("player_usage", _player_stats("Usage"), "% del total del equipo en pista"),
        Dataset("player_defense", _player_stats("Defense"), "Métricas defensivas, DEF_WS"),
        Dataset("player_misc", _player_stats("Misc"), "Puntos en pintura, contraataque, 2ª oportunidad"),
        Dataset("player_bio", _player_bio, "Edad, altura, peso, draft"),
        Dataset("lineups_base", _lineups("Base"), "Quintetos: box score (conteos)"),
        Dataset("lineups_advanced", _lineups("Advanced"), "Quintetos: ratings y posesiones"),
    ]
}


def ingest(seasons: list[str], datasets: list[str] | None = None, force: bool = False) -> None:
    """Descarga y guarda cada dataset/temporada. Salta lo ya descargado salvo `force`."""
    names = datasets or list(DATASETS)
    for season in seasons:
        for name in names:
            if storage.exists(name, season) and not force:
                log.info("%-18s %s  ya existe, se salta", name, season)
                continue
            t0 = time.perf_counter()
            df = _clean(DATASETS[name].fetch(season), season)
            storage.save(df, name, season)
            log.info("%-18s %s  %5d filas  (%.1fs)", name, season, len(df), time.perf_counter() - t0)
