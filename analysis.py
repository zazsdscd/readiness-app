"""Analyse exploratoire du modele de readiness.

Genere un historique synthetique cale sur la charge d'entrainement Strava
reelle, calcule la readiness et produit deux graphes :

- docs/readiness_timeline.png : la readiness dans le temps, qui baisse sur les
  periodes de fatigue de fond (TSB negatif) et remonte ensuite ;
- docs/training_load.png : charge quotidienne, CTL et ATL en haut, TSB en bas,
  sur la plage des donnees Strava.

Sert de preuve de concept DS et illustre le doc de demarche.

Lancer :  python analysis.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src import config
from src.scoring import compute_readiness
from src.synthetic import generate_history
from src.training_load import compute_training_load


def _shade_regions(ax, dates, mask, color, alpha, label=None):
    """Ombre les plages contigues ou mask est vrai (axvspan par segment)."""
    dates = pd.Series(dates).to_numpy()
    mask = pd.Series(mask).to_numpy()
    start, labeled = None, False
    for i, m in enumerate(mask):
        if m and start is None:
            start = dates[i]
        last = i == len(mask) - 1
        if start is not None and (not m or last):
            ax.axvspan(start, dates[i], color=color, alpha=alpha,
                       label=None if labeled else label)
            labeled = True
            start = None


def readiness_figure(scored, load_df):
    tsb = load_df["tsb"].reindex(scored["date"]).to_numpy()

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(scored.date, scored.readiness, color="#0f172a", lw=2, label="Readiness")
    ax.axhspan(60, 100, color="#dcfce7", alpha=0.6)
    ax.axhspan(40, 60, color="#dbeafe", alpha=0.6)
    ax.axhspan(28, 40, color="#fef3c7", alpha=0.6)
    ax.axhspan(0, 28, color="#fee2e2", alpha=0.6)

    # marquer les periodes de fatigue de fond (TSB negatif), issues de la
    # charge Strava reelle : c'est la que la readiness doit decrocher
    _shade_regions(ax, scored.date, tsb < 0, color="#0f172a", alpha=0.08,
                   label="TSB negatif (fatigue de fond)")

    ax.set_ylim(0, 100)
    ax.set_ylabel("Indice de readiness")
    ax.set_title("Readiness dans le temps (ressenti synthetique cale sur Strava)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig("docs/readiness_timeline.png", dpi=130)
    print("Graphe sauvegarde : docs/readiness_timeline.png")


def training_load_figure(load_df):
    d = load_df.reset_index()
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]})

    # haut : charge quotidienne (barres) + CTL + ATL
    ax_top.bar(d["date"], d["load"], width=1.0, color="#cbd5e1",
               label="Charge quotidienne")
    ax_top.plot(d["date"], d["ctl"], color="#2563eb", lw=2, label="CTL (forme de fond)")
    ax_top.plot(d["date"], d["atl"], color="#f59e0b", lw=2, label="ATL (fatigue recente)")
    ax_top.set_ylabel("Charge (relative effort)")
    ax_top.set_title("Charge d'entrainement Strava : charge quotidienne, CTL, ATL")
    ax_top.legend(loc="upper left", fontsize=9)

    # bas : TSB, vert si positif (frais), rouge si negatif (fatigue)
    ax_bot.fill_between(d["date"], d["tsb"], 0, where=d["tsb"] >= 0,
                        interpolate=True, color="#16a34a", alpha=0.5)
    ax_bot.fill_between(d["date"], d["tsb"], 0, where=d["tsb"] < 0,
                        interpolate=True, color="#dc2626", alpha=0.5)
    ax_bot.axhline(0, color="#334155", lw=0.8)
    ax_bot.set_ylabel("TSB (fraicheur)")
    ax_bot.set_title("TSB = CTL - ATL")
    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    fig.tight_layout()
    fig.savefig("docs/training_load.png", dpi=130)
    print("Graphe sauvegarde : docs/training_load.png")


def main():
    load_df = compute_training_load()
    df = generate_history(seed=42)
    scored = compute_readiness(df, load_df)

    # quelques stats descriptives
    print(f"Periode : {scored.date.min().date()} -> {scored.date.max().date()} "
          f"({len(scored)} jours)")
    print(f"Readiness  min/moy/max : {scored.readiness.min():.0f} / "
          f"{scored.readiness.mean():.0f} / {scored.readiness.max():.0f}")
    print("Repartition des statuts :", scored.status.value_counts().to_dict())

    # correlation entre composantes et readiness (sanity check)
    print("\nCorrelation composante <-> readiness :")
    for comp in config.SCORE_COMPONENTS:
        c = scored[comp].corr(scored["readiness"])
        print(f"  {comp:<14} {c:+.2f}")

    print()
    readiness_figure(scored, load_df)
    training_load_figure(load_df)


if __name__ == "__main__":
    main()
