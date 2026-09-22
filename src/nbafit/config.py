"""Rutas y parámetros globales del proyecto."""

from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

# Pausa entre peticiones a stats.nba.com para no ser bloqueados.
REQUEST_DELAY_S = 0.7
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 4

# Número de temporadas que se descargan por defecto (terminando en la actual).
DEFAULT_N_SEASONS = 5


def season_str(start_year: int) -> str:
    """2025 -> '2025-26'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def current_season(today: date | None = None) -> str:
    """Temporada más reciente con datos: la que empieza en octubre."""
    today = today or date.today()
    start = today.year if today.month >= 10 else today.year - 1
    return season_str(start)


def recent_seasons(n: int = DEFAULT_N_SEASONS, today: date | None = None) -> list[str]:
    """Las últimas `n` temporadas, de la más antigua a la más reciente."""
    last = int(current_season(today)[:4])
    return [season_str(y) for y in range(last - n + 1, last + 1)]
