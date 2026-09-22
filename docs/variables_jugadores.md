# Variables almacenadas por jugador

Hay **7 tablas de jugador** por temporada, en `data/raw/<tabla>/season=<temporada>.parquet`.
Cada tabla tiene **una fila por jugador y temporada** (temporada regular), identificada por `PLAYER_ID` + `SEASON`.

El ejemplo de cada variable es Nikola Jokić en 2025-26.

## Cuidado antes de usar los datos

1. **`MIN` no significa lo mismo en todas las tablas.** En `player_base`, `player_usage`, `player_defense` y `player_misc` son minutos **totales** (2264.9). En `player_advanced` y `player_scoring` son minutos **por partido** (34.8). Para los totales, usar siempre `player_base`.
2. **Los porcentajes no tienen todos la misma escala.** La mayoría van de 0 a 1 (`TS_PCT` = 0.67), pero `TM_TOV_PCT` y `E_TOV_PCT` van de 0 a 100 (10.7).
3. **En `player_bio` hay números guardados como texto.** `PLAYER_WEIGHT`, `DRAFT_YEAR`, `DRAFT_ROUND` y `DRAFT_NUMBER` son texto. Los no drafteados tienen el valor `"Undrafted"` y los que no fueron a la universidad tienen `COLLEGE = "None"`. Habrá que convertirlos antes de usarlos.

Además, un jugador traspasado aparece en **una sola fila** con el total de la temporada y el **último** equipo en el que jugó. `TEAM_COUNT` indica en cuántos equipos jugó (en 2025-26 hay 72 jugadores con más de uno).

## Columnas comunes

Casi todas las tablas repiten estas columnas. Se unen por `PLAYER_ID` + `SEASON`.

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `PLAYER_ID` | int | 203999 | Id del jugador en la NBA (clave) |
| `SEASON` | texto | 2025-26 | Temporada (clave) |
| `PLAYER_NAME`, `NICKNAME` | texto | Nikola Jokić | Nombre |
| `TEAM_ID`, `TEAM_ABBREVIATION` | int, texto | DEN | Último equipo |
| `TEAM_COUNT` | int | 1 | Nº de equipos en la temporada |
| `AGE` | float | 31.0 | Edad |
| `GP`, `W`, `L`, `W_PCT` | int / float | 65, 43, 22, 0.662 | Partidos jugados, ganados, perdidos, % victorias |
| `MIN` | float | 2264.9 | Minutos (ver aviso 1) |

## `player_base`: box score (totales de temporada)

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `PTS` | int | 1799 | Puntos |
| `FGM`, `FGA`, `FG_PCT` | int, int, 0–1 | 644, 1132, 0.569 | Tiros de campo anotados, intentados y % |
| `FG3M`, `FG3A`, `FG3_PCT` | int, int, 0–1 | 112, 295, 0.38 | Triples |
| `FTM`, `FTA`, `FT_PCT` | int, int, 0–1 | 399, 480, 0.831 | Tiros libres |
| `OREB`, `DREB`, `REB` | int | 192, 644, 836 | Rebotes ofensivos, defensivos, totales |
| `AST`, `TOV` | int | 697, 243 | Asistencias, pérdidas |
| `STL`, `BLK` | int | 92, 53 | Robos, tapones |
| `BLKA` | int | 50 | Tiros suyos taponados |
| `PF`, `PFD` | int | 173, 433 | Faltas cometidas, faltas recibidas |
| `PLUS_MINUS` | int | 555 | +/- acumulado con él en pista |
| `DD2`, `TD3` | int | 55, 34 | Dobles-dobles, triples-dobles |
| `NBA_FANTASY_PTS`, `WNBA_FANTASY_PTS`, `FP_HIGH_SCORE` | float | | Puntos de fantasy (no útiles) |

## `player_advanced`: eficiencia y ratings

Los ratings son **por 100 posesiones con el jugador en pista**. `E_` significa "estimado". Las columnas `sp_work_*` son copias internas de la NBA y se pueden ignorar.

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `OFF_RATING`, `E_OFF_RATING` | float | 126.1 | Puntos anotados por el equipo /100 posesiones |
| `DEF_RATING`, `E_DEF_RATING` | float | 115.3 | Puntos recibidos /100 posesiones |
| `NET_RATING`, `E_NET_RATING` | float | 10.8 | Diferencia entre los dos |
| `USG_PCT`, `E_USG_PCT` | 0–1 | 0.289 | % de jugadas del equipo que termina él |
| `TS_PCT` | 0–1 | 0.67 | True shooting (eficiencia de tiro incluyendo triples y libres) |
| `EFG_PCT` | 0–1 | 0.618 | % de campo ajustado (el triple vale 1.5) |
| `AST_PCT` | 0–1 | 0.458 | % de canastas de sus compañeros que asiste |
| `AST_TO` | float | 2.87 | Asistencias por pérdida |
| `AST_RATIO` | float | 30.6 | Asistencias por 100 jugadas propias |
| `TM_TOV_PCT`, `E_TOV_PCT` | **0–100** | 10.7 | Pérdidas por 100 jugadas propias |
| `OREB_PCT`, `DREB_PCT`, `REB_PCT` | 0–1 | 0.089, 0.27, 0.185 | % de rebotes disponibles que coge |
| `PACE`, `E_PACE`, `PACE_PER40` | float | 102.6 | Posesiones por 48 min (por 40 en `PACE_PER40`) |
| `PIE` | 0–1 | 0.213 | Player Impact Estimate: % de lo que pasa en el partido atribuible a él |
| `POSS` | int | 4854 | Posesiones jugadas (**base para calcular tasas por 100**) |
| `FGM_PG`, `FGA_PG` | float | 9.9, 17.4 | Tiros de campo por partido |

## `player_scoring`: de dónde salen sus puntos

Todo son proporciones de 0 a 1.

| Variable | Ejemplo | Significado |
|---|---|---|
| `PCT_FGA_2PT`, `PCT_FGA_3PT` | 0.739, 0.261 | Reparto de sus tiros entre 2 y 3 |
| `PCT_PTS_2PT`, `PCT_PTS_3PT`, `PCT_PTS_FT` | 0.591, 0.187, 0.222 | Reparto de sus puntos por tipo de tiro |
| `PCT_PTS_2PT_MR` | 0.073 | % de puntos en media distancia |
| `PCT_PTS_PAINT` | 0.518 | % de puntos en la pintura |
| `PCT_PTS_FB` | 0.032 | % de puntos al contraataque |
| `PCT_PTS_OFF_TOV` | 0.094 | % de puntos tras pérdida rival |
| `PCT_AST_2PM`, `PCT_UAST_2PM` | 0.564, 0.436 | Canastas de 2 asistidas vs. creadas por él |
| `PCT_AST_3PM`, `PCT_UAST_3PM` | 0.804, 0.196 | Triples asistidos vs. creados por él |
| `PCT_AST_FGM`, `PCT_UAST_FGM` | 0.606, 0.394 | Todas las canastas: asistidas vs. creadas por él |

## `player_usage`: su peso en el equipo

Cada `PCT_X` es la **fracción (0–1) del total del equipo en X mientras él está en pista**. Por ejemplo, `PCT_AST` = 0.461 significa que da el 46 % de las asistencias de su equipo cuando juega.

Variables: `USG_PCT`, `PCT_FGM`, `PCT_FGA`, `PCT_FG3M`, `PCT_FG3A`, `PCT_FTM`, `PCT_FTA`, `PCT_OREB`, `PCT_DREB`, `PCT_REB`, `PCT_AST`, `PCT_TOV`, `PCT_STL`, `PCT_BLK`, `PCT_BLKA`, `PCT_PF`, `PCT_PFD`, `PCT_PTS`.

## `player_defense`: defensa

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `DEF_RATING` | float | 115.3 | Puntos recibidos /100 posesiones con él |
| `DEF_WS`, `DEF_WS_RAW` | float | 5.7 | Defensive win shares: victorias atribuidas a su defensa |
| `DREB`, `DREB_PCT`, `PCT_DREB` | int, 0–1, 0–1 | 644, 0.27, 0.40 | Rebote defensivo (total, % disponibles, % del equipo) |
| `STL`, `PCT_STL`, `BLK`, `PCT_BLK` | int, 0–1 | 92, 0.271, 53, 0.299 | Robos y tapones (total y % del equipo) |
| `OPP_PTS_PAINT` | float | 2374 | Puntos del rival en la pintura con él en pista |
| `OPP_PTS_FB` | float | 734 | Puntos del rival al contraataque con él en pista |
| `OPP_PTS_2ND_CHANCE` | float | 591 | Puntos del rival en segundas oportunidades |
| `OPP_PTS_OFF_TOV` | float | 810 | Puntos del rival tras pérdidas de su equipo |

## `player_misc`: tipos de puntos (totales)

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `PTS_PAINT` | int | 932 | Puntos en la pintura |
| `PTS_2ND_CHANCE` | int | 306 | Puntos de segunda oportunidad |
| `PTS_FB` | int | 58 | Puntos al contraataque |
| `PTS_OFF_TOV` | int | 170 | Puntos tras pérdida rival |

También repite los `OPP_PTS_*` de `player_defense` y `BLK`, `BLKA`, `PF`, `PFD` y `NBA_FANTASY_PTS` de `player_base`.

## `player_bio`: físico y trayectoria

| Variable | Tipo | Ejemplo | Significado |
|---|---|---|---|
| `PLAYER_HEIGHT` | texto | 6-11 | Altura en pies-pulgadas |
| `PLAYER_HEIGHT_INCHES` | int | 83 | Altura en pulgadas (×2.54 = cm) |
| `PLAYER_WEIGHT` | **texto** | 284 | Peso en libras (6 nulos en 2025-26) |
| `COUNTRY` | texto | Serbia | País |
| `COLLEGE` | texto | None | Universidad (`"None"` si no fue) |
| `DRAFT_YEAR`, `DRAFT_ROUND`, `DRAFT_NUMBER` | **texto** | 2014, 2, 41 | Draft (`"Undrafted"` si no fue elegido) |

Además repite un resumen de otras tablas: `PTS`, `REB`, `AST`, `NET_RATING`, `OREB_PCT`, `DREB_PCT`, `USG_PCT`, `TS_PCT` y `AST_PCT`.

## Tamaño

| Temporada | Jugadores |
|---|---|
| 2021-22 | 605 |
| 2022-23 | 539 |
| 2023-24 | 572 |
| 2024-25 | 569 |
| 2025-26 | 582 |

Muchos de estos jugadores tienen muy pocos minutos: en 2025-26 solo 378 superan los 500.
