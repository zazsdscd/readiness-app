"""Generation d'un historique synthetique realiste pour la demo.

Le ressenti synthetique est cale sur la VRAIE charge d'entrainement Strava :
on couvre exactement la plage de dates des activites (cf
data/strava_activities.csv) et, jour par jour, on fait baisser l'energie et
la fraicheur quand la charge du jour est elevee et quand le TSB (fraicheur de
fond) est negatif. On garde une baseline individuelle par item plus du bruit,
quelques mauvaises nuits isolees, on clampe tout entre 1 et 5 et on reste
deterministe (seed). Objectif : que la baseline z-score ait quelque chose a
revertir, et que le score reagisse aux blocs de charge reels.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .training_load import DEFAULT_CSV, compute_training_load


def generate_history(seed: int = 42, csv_path=DEFAULT_CSV) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # charge reelle : on calque l'historique sur la plage des activites Strava
    load_df = compute_training_load(csv_path)
    dates = load_df.index

    # standardisation de la charge et du TSB pour en faire des effets bornes
    load = load_df["load"]
    load_mean = float(load.mean())
    load_std = float(load.std()) or 1.0
    tsb = load_df["tsb"]
    tsb_std = float(tsb.std()) or 1.0

    # baseline personnelle (chaque athlete a son propre niveau de reference)
    base = {"sleep_quality": 3.7, "energy": 3.6,
            "freshness": 3.5, "mood": 3.8, "motivation": 3.7}

    # quelques mauvaises nuits isolees, reparties sur la periode
    n_days = len(dates)
    bad_nights = {int(n_days * f) for f in (0.12, 0.34, 0.55, 0.78)}

    rows = []
    for i, d in enumerate(dates):
        weekend = d.dayofweek >= 5

        # charge du jour elevee -> coup de fatigue aigu (surtout energie)
        acute = max((load.iloc[i] - load_mean) / load_std, 0.0)
        # TSB negatif -> fatigue de fond accumulee (surtout fraicheur)
        chronic_fatigue = max(-tsb.iloc[i] / tsb_std, 0.0)

        vals = {
            "sleep_quality": base["sleep_quality"]
            + (0.4 if weekend else 0) + rng.normal(0, 0.5),
            "energy": base["energy"]
            - 0.45 * acute - 0.40 * chronic_fatigue + rng.normal(0, 0.45),
            "freshness": base["freshness"]
            - 0.35 * acute - 0.55 * chronic_fatigue + rng.normal(0, 0.4),
            "mood": base["mood"] + (0.3 if weekend else 0)
            - 0.20 * chronic_fatigue + rng.normal(0, 0.5),
            "motivation": base["motivation"]
            - 0.25 * chronic_fatigue + rng.normal(0, 0.5),
        }
        sleep_hours = 7.4 + (0.6 if weekend else 0) + rng.normal(0, 0.6)

        if i in bad_nights:
            sleep_hours -= rng.uniform(1.5, 2.5)
            vals["sleep_quality"] -= 1.5
            vals["energy"] -= 1.0

        clipped = {k: int(np.clip(round(v), 1, 5)) for k, v in vals.items()}
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            **clipped,
            "sleep_hours": round(float(np.clip(sleep_hours, 3.5, 10)), 1),
            "note": "",
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_history()
    print(df.head())
    print(f"\n{len(df)} jours generes, du {df.date.min()} au {df.date.max()}")
