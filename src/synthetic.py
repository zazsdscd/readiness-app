"""Generation d'un historique synthetique realiste pour la demo.

Tant que le dataset Enduraw n'est pas dispo, on simule un athlete sur ~75
jours avec une vraie structure : baseline individuelle par item, rythme
hebdomadaire (week-ends mieux dormis), un bloc d'entrainement charge qui
fait monter la fatigue et descendre la fraicheur, puis une recup, plus
quelques mauvaises nuits isolees. Objectif : que la baseline z-score ait
quelque chose a revertir.
"""

import numpy as np
import pandas as pd


def generate_history(n_days: int = 75, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.today().normalize()
    dates = pd.date_range(end=end, periods=n_days, freq="D")

    # baseline personnelle (chaque athlete a son propre niveau de reference)
    base = {"sleep_quality": 3.7, "energy": 3.6,
            "freshness": 3.5, "mood": 3.8, "motivation": 3.7}

    # bloc d'entrainement charge sur ~12 jours, vers le 2/3 de la periode
    block_start = int(n_days * 0.55)
    block_end = block_start + 12

    rows = []
    for i, d in enumerate(dates):
        weekend = d.dayofweek >= 5
        in_block = block_start <= i < block_end
        recovering = block_end <= i < block_end + 5

        # effet de la charge : fatigue qui s'accumule, fraicheur qui chute
        load_fatigue = -1.2 * (i - block_start) / 12 if in_block else 0.0
        load_fresh = -1.5 * (i - block_start) / 12 if in_block else 0.0
        recup_bonus = 0.6 if recovering else 0.0

        vals = {
            "sleep_quality": base["sleep_quality"] + (0.5 if weekend else 0) + rng.normal(0, 0.5),
            "energy": base["energy"] + load_fatigue + recup_bonus + rng.normal(0, 0.5),
            "freshness": base["freshness"] + load_fresh + recup_bonus + rng.normal(0, 0.4),
            "mood": base["mood"] + (0.3 if weekend else 0) + 0.5 * load_fatigue + rng.normal(0, 0.5),
            "motivation": base["motivation"] + 0.4 * load_fatigue + recup_bonus + rng.normal(0, 0.5),
        }
        sleep_hours = 7.4 + (0.6 if weekend else 0) + rng.normal(0, 0.6)

        # quelques mauvaises nuits isolees
        if i in (10, 33, int(n_days * 0.6)):
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
