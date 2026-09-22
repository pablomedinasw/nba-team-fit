"""CLI de ingesta.

Ejemplos:
    python -m nbafit.ingest                          # últimas 5 temporadas, todo
    python -m nbafit.ingest --seasons 2025-26 --force  # recargar la actual
    python -m nbafit.ingest --datasets player_base player_bio
"""

import argparse
import logging

from nbafit.config import DEFAULT_N_SEASONS, recent_seasons
from nbafit.ingest.nba_stats import DATASETS, ingest


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m nbafit.ingest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seasons", nargs="+", default=None,
                        help=f"Temporadas 'YYYY-YY' (por defecto, las últimas {DEFAULT_N_SEASONS})")
    parser.add_argument("--datasets", nargs="+", choices=list(DATASETS), default=None,
                        help="Datasets a descargar (por defecto, todos)")
    parser.add_argument("--force", action="store_true", help="Volver a descargar aunque ya exista")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    ingest(args.seasons or recent_seasons(), args.datasets, args.force)


if __name__ == "__main__":
    main()
