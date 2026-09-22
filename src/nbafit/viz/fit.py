"""Gráficos de la fase 3 (modelo de quintetos y fit).

Uso:
    python -m nbafit.viz.fit      # genera reports/figures/fase3_*.png (requiere python -m nbafit.fit_model)
"""

import json

import numpy as np
from matplotlib.patches import Rectangle

from nbafit import fit_model, recommend
from nbafit.archetypes import ARCHETYPE_NAMES
from nbafit.viz.archetypes import BLUE, DIVERGING, INK, INK_2, ORANGE, SURFACE, _save, _title, plt

SHORT = {
    "Creador principal": "Creador",
    "Base / escolta exterior": "Base/escolta",
    "Tirador 3&D": "Tirador 3&D",
    "Conector defensivo": "Conector def.",
    "Alero anotador": "Alero anotador",
    "Pívot moderno": "Pívot moderno",
    "Pívot de referencia": "Pívot referencia",
    "Pívot de pintura": "Pívot pintura",
}


def fig_validation() -> None:
    val = json.loads(fit_model.VALIDATION_PATH.read_text())
    gain = np.array(val["gain_per_fold"]) * 1e4

    fig, ax = plt.subplots(figsize=(10, 3.6))
    rng = np.random.default_rng(0)
    jitter = rng.uniform(-0.12, 0.12, len(gain))
    colors = np.where(gain > 0, BLUE, ORANGE)
    ax.scatter(gain, jitter, s=60, c=colors, edgecolor=SURFACE, linewidth=1.2, zorder=3)
    ax.axvline(0, color=INK_2, lw=1)
    ax.axvline(gain.mean(), color=BLUE, lw=2, ls="--")
    ax.annotate(f"media +{gain.mean():.1f}", (gain.mean(), 0.2), xytext=(6, 0), textcoords="offset points",
                color=INK, va="center")
    ax.set_ylim(-0.3, 0.3)
    ax.set_yticks([])
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Mejora del error fuera de muestra al añadir la complementariedad (R², ×10⁻⁴)")
    _title(fig, "La complementariedad añade señal real, pero pequeña",
           f"Cada punto es una partición de la validación cruzada (5 folds × 4). Mejora en el "
           f"{val['folds_improved']:.0%} de ellas (t = {val['t_stat']:.1f}).\n"
           f"R² fuera de muestra: calidad {val['r2_quality']:.4f} → calidad + fit {val['r2_quality_fit']:.4f}. "
           "El R² es bajo porque la mayoría de quintetos juegan pocas posesiones (ruido).")
    fig.tight_layout(rect=(0, 0, 1, 0.78))
    _save(fig, "fase3_1_validacion.png")


def fig_pairs(model: fit_model.FitModel) -> None:
    raw = model.pair_effects("net", shrink=False)
    shrunk = model.pair_effects("net", shrink=True)
    z = raw / model.pair_se["net"]
    labels = [SHORT[a] for a in ARCHETYPE_NAMES]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.6))
    for ax, df, title in [(axes[0], raw, "Estimado"), (axes[1], shrunk, "Encogido según su incertidumbre")]:
        im = ax.imshow(df.to_numpy(), cmap=DIVERGING.reversed(), vmin=-0.8, vmax=0.8)
        ax.set_xticks(range(8), labels, rotation=40, ha="right")
        ax.set_yticks(range(8), labels)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        for i in range(8):
            for j in range(8):
                v = df.iat[i, j]
                sig = abs(z.iat[i, j]) > 2
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=8.5,
                        color="white" if abs(v) > 0.5 else INK, fontweight="bold" if sig else "normal")
                if sig:
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=INK, lw=1.8))
        ax.set_title(title)
    _title(fig, "Qué parejas de roles suman o restan",
           "Efecto de juntar un jugador de cada rol en el mismo quinteto, respecto al compañero medio. Recuadradas: "
           "las 3 parejas con efecto claro (|z| > 2):\npick & roll (base + pívot de pintura) suma; dos jugadores "
           "de balón (creador + base) y dos que no crean (tirador + conector) restan.")
    fig.subplots_adjust(top=0.8, bottom=0.2, left=0.1, right=0.86, wspace=0.45)
    cb = fig.colorbar(im, cax=fig.add_axes((0.9, 0.25, 0.012, 0.5)))
    cb.set_label("pts/100 posesiones (azul = suman, rojo = restan)", color=INK_2)
    cb.outline.set_visible(False)
    _save(fig, "fase3_2_parejas.png")


def _fits_across_teams(model: fit_model.FitModel, season: str) -> np.ndarray:
    players = model.players[model.players["SEASON"] == season]
    values = []
    for team in players["TEAM_ABBREVIATION"].unique():
        core = recommend.team_core(players, team)
        values.append(recommend.recommend(model, core, season)["fit"].to_numpy())
    return np.concatenate(values)


def fig_talent_vs_fit(model: fit_model.FitModel) -> None:
    season = model.players["SEASON"].max()
    players = model.players[(model.players["SEASON"] == season) & (model.players["MIN"] >= 500)]
    quality = players["q_net"].to_numpy()
    fits = _fits_across_teams(model, season)

    fig, ax = plt.subplots(figsize=(11, 3.8))
    for i, (vals, name, color) in enumerate([(fits, "Fit con el núcleo\n(30 equipos × candidatos)", ORANGE),
                                             (quality, "Calidad individual\n(jugadores ≥500 min)", BLUE)]):
        p5, p25, p50, p75, p95 = np.percentile(vals, [5, 25, 50, 75, 95])
        ax.plot([p5, p95], [i, i], color=color, lw=2, solid_capstyle="round")
        ax.add_patch(Rectangle((p25, i - 0.18), p75 - p25, 0.36, facecolor=color, edgecolor=SURFACE, lw=2))
        ax.plot([p50, p50], [i - 0.18, i + 0.18], color=SURFACE, lw=2)
        ax.annotate(f"p5–p95: {p5:+.1f} a {p95:+.1f}", (p95, i), xytext=(10, 0), textcoords="offset points",
                    va="center", color=INK, fontsize=9)
    ax.set_yticks([0, 1], ["Fit con el núcleo\n(30 equipos × candidatos)", "Calidad individual\n(jugadores ≥500 min)"])
    ax.set_ylim(-0.6, 1.6)
    ax.axvline(0, color=INK_2, lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("pts/100 posesiones")
    ax.set_xlim(-6, 9.5)
    _title(fig, "El talento pesa mucho más que el encaje",
           "Dispersión de la calidad de los jugadores frente a la de su fit con cada núcleo (caja = p25–p75, "
           "línea = p5–p95).\nEl fit sirve para desempatar entre jugadores de nivel parecido, no para cambiar "
           "el orden entre niveles distintos.")
    fig.tight_layout(rect=(0, 0, 1, 0.8))
    _save(fig, "fase3_3_talento_vs_encaje.png")


def fig_top_quality(model: fit_model.FitModel, n: int = 20) -> None:
    season = model.players["SEASON"].max()
    top = model.players[model.players["SEASON"] == season].nlargest(n, "q_net").iloc[::-1]
    y = np.arange(len(top))

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(y, top["q_off"], color=BLUE, height=0.62, label="Ataque")
    ax.barh(y, -top["q_def"], left=top["q_off"].clip(lower=0) * (top["q_def"] < 0),
            color=ORANGE, height=0.62, label="Defensa")
    for i, r in enumerate(top.itertuples()):
        right = max(r.q_off, 0) + max(-r.q_def, 0)
        ax.text(right + 0.12, i, f"{r.q_net:+.1f}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, top["PLAYER_NAME"])
    ax.axvline(0, color=INK_2, lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Impacto en pts/100 posesiones (RAPM de quintetos)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2, frameon=False)
    _title(fig, f"Los {n} jugadores de más impacto en {season}",
           "Calidad individual estimada por el modelo, repartida en ataque y defensa. El número es el total. "
           "Usa las cinco temporadas,\nasí que refleja el nivel de los últimos años más que solo el último.")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    _save(fig, "fase3_4_top_calidad.png")


def main() -> None:
    model = fit_model.load()
    print("Generando figuras en reports/figures")
    fig_validation()
    fig_pairs(model)
    fig_talent_vs_fit(model)
    fig_top_quality(model)


if __name__ == "__main__":
    main()
