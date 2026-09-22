"""Gráficos de la fase 2 (arquetipos).

Uso:
    python -m nbafit.viz.archetypes      # genera reports/figures/fase2_*.png
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture

from nbafit import archetypes
from nbafit.config import PROJECT_ROOT
from nbafit.features import STYLE_FEATURES, standardize_by_season

FIG_DIR = PROJECT_ROOT / "reports" / "figures"

# Paleta de referencia (modo claro).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#d9d8d4"
GRID = "#ecebe8"
BLUE, ORANGE = "#2a78d6", "#eb6834"
DIVERGING = LinearSegmentedColormap.from_list(
    "div", ["#1c5cab", "#6da7ec", "#f0efec", "#ec8a88", "#b52a2a"]
)

FEATURE_LABELS = {
    "usg": "Uso (USG%)",
    "ast_pct": "Asistencias (AST%)",
    "fg3a_100": "Triples /100 pos.",
    "fg3a_rate": "% tiros que son triple",
    "fta_rate": "Tiros libres por tiro",
    "paint_share": "% puntos en pintura",
    "midrange_share": "% puntos media distancia",
    "fastbreak_share": "% puntos contraataque",
    "self_created": "% canastas no asistidas",
    "oreb_pct": "Rebote ofensivo %",
    "dreb_pct": "Rebote defensivo %",
    "stl_100": "Robos /100 pos.",
    "blk_100": "Tapones /100 pos.",
    "height_in": "Altura",
    "weight_lb": "Peso",
}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "figure.titlesize": 14, "figure.titleweight": "bold",
})


def _title(fig, title: str, subtitle: str) -> None:
    fig.suptitle(title, x=0.01, ha="left", y=0.995)
    fig.text(0.01, 0.945, subtitle, ha="left", va="top", color=INK_2, fontsize=10)


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}")


def fig_model_selection(model: archetypes.ArchetypeModel, ks=range(3, 13), n_boot: int = 10) -> None:
    X = model.components
    rng = np.random.default_rng(1)
    bic, stab = [], []
    for k in ks:
        ref = GaussianMixture(k, covariance_type="full", n_init=5, random_state=0).fit(X)
        bic.append(ref.bic(X))
        labels = ref.predict(X)
        stab.append(np.mean([
            adjusted_rand_score(labels, GaussianMixture(k, covariance_type="full", n_init=2, random_state=s)
                                .fit(X[rng.choice(len(X), len(X))]).predict(X))
            for s in range(n_boot)
        ]))

    var = np.cumsum(PCA().fit(model.z).explained_variance_ratio_)
    n_pca = model.pca.n_components_
    k_sel = archetypes.N_ARCHETYPES

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    ax = axes[0]
    ax.plot(range(1, len(var) + 1), var * 100, color=BLUE, lw=2, marker="o", ms=5)
    ax.axhline(archetypes.PCA_VARIANCE * 100, color=INK_2, lw=1, ls="--")
    ax.annotate(f"{n_pca} componentes → {var[n_pca - 1]:.0%}", (n_pca, var[n_pca - 1] * 100),
                xytext=(n_pca + 1.2, 72), color=INK, arrowprops=dict(arrowstyle="-", color=INK_2))
    ax.set(title="PCA: varianza explicada acumulada", xlabel="Nº de componentes", ylabel="%", ylim=(35, 101))

    for ax, values, title, ylabel in [
        (axes[1], bic, "BIC del GMM (menor = mejor ajuste)", "BIC"),
        (axes[2], stab, "Estabilidad (ARI en bootstrap, mayor = mejor)", "ARI medio"),
    ]:
        ax.plot(list(ks), values, color=BLUE, lw=2, marker="o", ms=5)
        i = list(ks).index(k_sel)
        ax.scatter([k_sel], [values[i]], s=110, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2)
        ax.annotate(f"k = {k_sel} elegido", (k_sel, values[i]), xytext=(-12, 16), textcoords="offset points",
                    color=INK, ha="right")
        ax.set(title=title, xlabel="Nº de arquetipos (k)", ylabel=ylabel)
        ax.set_xticks(list(ks))

    _title(fig, "Cuántos arquetipos: no hay un corte natural",
           "El BIC es mejor con 5-6 grupos y la estabilidad cae al subir k: los estilos son un continuo, "
           "no grupos separados.\nSe eligen 8 porque con 5-6 se mezclan roles distintos (Brunson con Maxey, "
           "Durant con Barnes); la incertidumbre se recoge guardando probabilidades.")
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    _save(fig, "fase2_1_seleccion_modelo.png")


def _oriented_axes(model: archetypes.ArchetypeModel) -> tuple[np.ndarray, np.ndarray]:
    """PC1 positivo = interior (altura), PC2 positivo = creador (uso)."""
    load = pd.DataFrame(model.pca.components_[:2].T, index=model.z.columns)
    s1 = np.sign(load.loc["height_in", 0])
    s2 = np.sign(load.loc["usg", 1])
    return model.components[:, 0] * s1, model.components[:, 1] * s2


def fig_style_map(model: archetypes.ArchetypeModel, assign: pd.DataFrame) -> None:
    x, y = _oriented_axes(model)
    fig, axes = plt.subplots(2, 4, figsize=(15, 8), sharex=True, sharey=True)
    current = assign["SEASON"] == assign["SEASON"].max()
    for ax, name in zip(axes.flat, archetypes.ARCHETYPE_NAMES):
        mask = (assign["archetype"] == name).to_numpy()
        ax.scatter(x[~mask], y[~mask], s=8, color=MUTED, linewidth=0)
        ax.scatter(x[mask], y[mask], s=14, color=BLUE, alpha=0.75, edgecolor=SURFACE, linewidth=0.4)
        top = assign[mask & current].nlargest(3, "MIN")
        for idx, row in top.iterrows():
            ax.scatter(x[idx], y[idx], s=40, color=INK, edgecolor=SURFACE, linewidth=1.2, zorder=3)
            ax.annotate(row["PLAYER_NAME"].split(" ", 1)[-1], (x[idx], y[idx]), xytext=(4, 4),
                        textcoords="offset points", fontsize=8.5, color=INK)
        ax.set_title(f"{name}  ({mask.sum()})", fontsize=10.5)
        ax.grid(False)
        ax.axhline(0, color=GRID, lw=0.8, zorder=0)
        ax.axvline(0, color=GRID, lw=0.8, zorder=0)
    for ax in axes[1]:
        ax.set_xlabel("← exterior     PC1     interior →")
    for ax in axes[:, 0]:
        ax.set_ylabel("← sin balón     PC2     creador →")
    _title(fig, "Mapa de estilos: cada arquetipo ocupa una zona del plano",
           "Cada punto es un jugador-temporada (2021-22 a 2025-26, ≥500 min). Los dos primeros componentes "
           "explican el 59 % de la varianza.\nEn negro, los 3 jugadores con más minutos de cada arquetipo en 2025-26.")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _save(fig, "fase2_2_mapa_estilos.png")


def fig_profiles(model: archetypes.ArchetypeModel, assign: pd.DataFrame) -> None:
    prof = model.z.groupby(assign["archetype"].to_numpy()).mean().loc[archetypes.ARCHETYPE_NAMES]
    features = list(STYLE_FEATURES)
    prof = prof[features]

    fig, ax = plt.subplots(figsize=(14, 5.8))
    im = ax.imshow(prof.to_numpy(), cmap=DIVERGING, vmin=-2, vmax=2, aspect="auto")
    ax.set_xticks(range(len(features)), [FEATURE_LABELS[f] for f in features], rotation=35, ha="right")
    ax.set_yticks(range(len(prof)), prof.index)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(prof.shape[0]):
        for j in range(prof.shape[1]):
            v = prof.iat[i, j]
            ax.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=8.5,
                    color="white" if abs(v) > 1.2 else INK)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.01)
    cb.set_label("Desviaciones típicas respecto a la media de la liga", color=INK_2)
    cb.outline.set_visible(False)
    _title(fig, "Qué define a cada arquetipo",
           "Media de cada variable en el arquetipo, en desviaciones típicas respecto a la liga de su temporada "
           "(azul = por debajo, rojo = por encima).")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    _save(fig, "fase2_3_perfil_arquetipos.png")


def fig_league_trend(assign: pd.DataFrame) -> None:
    share = (assign.groupby(["SEASON", "archetype"])["MIN"].sum()
             / assign.groupby("SEASON")["MIN"].sum()).unstack("archetype") * 100
    seasons = list(share.index)
    x = np.arange(len(seasons))

    fig, axes = plt.subplots(2, 4, figsize=(14, 6.4), sharex=True, sharey=True)
    for ax, name in zip(axes.flat, share[archetypes.ARCHETYPE_NAMES].mean().sort_values(ascending=False).index):
        s = share[name]
        ax.plot(x, s, color=BLUE, lw=2, marker="o", ms=6, markeredgecolor=SURFACE, markeredgewidth=1.2)
        ax.annotate(f"{s.iloc[-1]:.1f} %", (x[-1], s.iloc[-1]), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=9, color=INK)
        ax.set_title(f"{name}\n{s.min():.1f}–{s.max():.1f} %", fontsize=10)
        ax.set_xticks(x, [f"{a[2:4]}-{a[-2:]}" for a in seasons])
        ax.set_ylim(0, 28)
    for ax in axes[:, 0]:
        ax.set_ylabel("% de minutos de la liga")
    _title(fig, "El reparto de roles es estable: no hay una tendencia clara en cinco temporadas",
           "% de los minutos de la liga jugados por cada arquetipo y temporada. Las variaciones anuales son de "
           "±2 puntos y sin dirección constante.\nOjo: las variables se estandarizan por temporada, así que esto "
           "mide roles relativos a su liga, no el aumento general de triples.")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    _save(fig, "fase2_4_evolucion_liga.png")


def fig_hybrids(assign: pd.DataFrame) -> None:
    cur = assign[assign["SEASON"] == assign["SEASON"].max()]
    cur = cur[cur["MIN"] >= 1500].nsmallest(12, "archetype_prob")
    pcols = [f"p_{n}" for n in archetypes.ARCHETYPE_NAMES]
    rows = []
    for _, r in cur.iterrows():
        top2 = r[pcols].astype(float).nlargest(2)
        rows.append((r["PLAYER_NAME"], top2.index[0][2:], top2.iloc[0], top2.index[1][2:], top2.iloc[1]))
    df = pd.DataFrame(rows, columns=["player", "a1", "p1", "a2", "p2"]).iloc[::-1]

    fig, ax = plt.subplots(figsize=(11, 5.6))
    y = np.arange(len(df))
    ax.barh(y, df["p1"] * 100, color=BLUE, height=0.62, label="Arquetipo principal")
    ax.barh(y, df["p2"] * 100, left=df["p1"] * 100 + 0.6, color=ORANGE, height=0.62, label="Segundo arquetipo")
    for i, r in enumerate(df.itertuples()):
        ax.text(1.5, i, r.a1, va="center", color="white", fontsize=8.5)
        ax.text(r.p1 * 100 + r.p2 * 100 + 2, i, r.a2, va="center", color=INK, fontsize=8.5)
    ax.set_yticks(y, df["player"])
    ax.set_xlim(0, 135)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Probabilidad de pertenecer al arquetipo (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2, frameon=False)
    _title(fig, "Los jugadores híbridos: por qué se guarda la probabilidad",
           "Jugadores de 2025-26 (≥1500 min) con la asignación menos clara. Su perfil se reparte entre "
           "dos arquetipos, y eso se usará en el modelo de fit.")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    _save(fig, "fase2_5_hibridos.png")


def main() -> None:
    model = archetypes.fit()
    assign = model.assignments()
    print(f"Generando figuras en {FIG_DIR}")
    fig_style_map(model, assign)
    fig_profiles(model, assign)
    fig_league_trend(assign)
    fig_hybrids(assign)
    fig_model_selection(model)


if __name__ == "__main__":
    main()
