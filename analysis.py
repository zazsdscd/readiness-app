"""Analyse exploratoire du modele de readiness.

Genere un historique synthetique, calcule la readiness et produit un
graphe montrant que le score capte bien le bloc d'entrainement charge.
Sert de preuve de concept DS et illustre le doc de demarche.

Lancer :  python analysis.py
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src import config
from src.scoring import compute_readiness
from src.synthetic import generate_history


def main():
    df = generate_history(n_days=75, seed=42)
    scored = compute_readiness(df)

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

    # graphe : readiness + bandes de statut
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(scored.date, scored.readiness, color="#0f172a", lw=2, label="Readiness")
    ax.axhspan(60, 100, color="#dcfce7", alpha=0.6)
    ax.axhspan(40, 60, color="#dbeafe", alpha=0.6)
    ax.axhspan(28, 40, color="#fef3c7", alpha=0.6)
    ax.axhspan(0, 28, color="#fee2e2", alpha=0.6)

    # marquer le bloc d'entrainement charge
    block_start = scored.iloc[int(75 * 0.55)]["date"]
    block_end = scored.iloc[int(75 * 0.55) + 12]["date"]
    ax.axvspan(block_start, block_end, color="#0f172a", alpha=0.08)
    ax.text(block_start, 95, " bloc charge", fontsize=9, color="#334155")

    ax.set_ylim(0, 100)
    ax.set_ylabel("Indice de readiness")
    ax.set_title("Readiness dans le temps (donnees synthetiques)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig("docs/readiness_timeline.png", dpi=130)
    print("\nGraphe sauvegarde : docs/readiness_timeline.png")


if __name__ == "__main__":
    main()
