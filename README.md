# nba-team-fit

¿Qué jugador de la NBA encajaría mejor en mi plantilla, qué gano con él y cuánto debería costar comparado con jugadores similares?

## Enfoque

1. **Perfil de jugador**: vector de estilo y rol (volumen, zonas de tiro, creación, rebote, defensa), normalizado por posesiones y temporada. PCA + clustering para obtener arquetipos.
2. **Modelo de quintetos**: predecir el net rating de un quinteto a partir de los perfiles de sus cinco jugadores.
3. **Fit**: mejora marginal del net rating predicho al meter al jugador en la rotación del equipo.
4. **Precio**: aportación frente al salario de los jugadores más parecidos → jugadores infravalorados.
5. **Traspasos**: filtrar por las reglas salariales del convenio.

## Estado

- [x] Fase 1: ingesta de estadísticas (jugadores y quintetos) desde stats.nba.com
- [x] Fase 2: arquetipos (PCA + clustering): 8 roles de jugador
- [x] Fase 3: modelo de quintetos y fit: calidad individual (RAPM) + complementariedad entre roles, y recomendador
- [ ] Fase 4: salarios y valor
- [ ] Fase 5: traspasos
- [ ] Fase 6: web

El detalle de cada paso, las decisiones y las conclusiones (con gráficos) están en la [bitácora](docs/bitacora.md).

![Mapa de estilos](reports/figures/fase2_2_mapa_estilos.png)

## Instalación

Requiere Python 3.14.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Descarga de datos

```powershell
python -m nbafit.ingest                            # últimas 5 temporadas, todos los datasets
python -m nbafit.ingest --seasons 2025-26 --force  # recargar una temporada
python -m nbafit.ingest --datasets player_base player_bio
```

Lo ya descargado se salta, salvo con `--force`. Los datos se guardan en `data/raw/<dataset>/season=<temporada>.parquet` (no se suben al repo).

| Dataset | Contenido |
|---|---|
| `player_base` | Box score clásico (conteos) |
| `player_advanced` | Ratings, USG%, TS%, posesiones |
| `player_scoring` | Origen de los puntos, % asistidos |
| `player_usage` | % del total del equipo en pista |
| `player_defense` | Métricas defensivas, DEF_WS |
| `player_misc` | Puntos en pintura, contraataque, 2ª oportunidad |
| `player_bio` | Edad, altura, peso, draft |
| `lineups_base` | Quintetos: box score (conteos) |
| `lineups_advanced` | Quintetos: ratings y posesiones |

Todo se guarda en totales de temporada regular. Las tasas (por 100 posesiones, etc.) se calculan después.
Qué significa cada variable de jugador y en qué formato viene: [docs/variables_jugadores.md](docs/variables_jugadores.md).

Para leer un dataset desde Python:

```python
from nbafit import storage
df = storage.load("player_base")                 # todas las temporadas
df = storage.load("lineups_advanced", ["2025-26"])
```

## Estructura

```
src/nbafit/
  config.py        rutas, temporadas, parámetros de la API
  storage.py       lectura/escritura de Parquet
  ingest/          descarga desde stats.nba.com
  features.py      perfil de estilo de cada jugador-temporada
  archetypes.py    PCA + GMM -> arquetipos   (python -m nbafit.archetypes)
  lineups.py       quintetos con el perfil de sus jugadores
  fit_model.py     calidad + complementariedad (python -m nbafit.fit_model)
  recommend.py     mejor jugador para un núcleo (python -m nbafit.recommend --team DEN)
  viz/             gráficos de cada fase     (python -m nbafit.viz.archetypes | nbafit.viz.fit)
data/raw/          datos descargados (ignorado por git)
data/processed/    resultados de los modelos (ignorado por git)
reports/figures/   gráficos de conclusiones
docs/              bitácora y documentación de variables
```
