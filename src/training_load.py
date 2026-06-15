"""Charge d'entrainement a partir des activites Strava.

On agrege le relative_effort de Strava par jour (proxy de charge), puis on
applique le modele classique "performance manager" :

- ATL (Acute Training Load)   : fatigue recente, EWMA constante de temps 7 j
- CTL (Chronic Training Load)  : forme de fond, EWMA constante de temps 42 j
- TSB (Training Stress Balance) : fraicheur = CTL - ATL
- ACWR (Acute:Chronic Workload Ratio) : charge 7 j / moyenne hebdo sur 28 j

L'ACWR alimente ensuite la modulation de la readiness (cf scoring).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ATL_TAU = 7    # jours
CTL_TAU = 42   # jours

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "strava_activities.csv"


def _ewm_alpha(tau: int) -> float:
    """Constante de lissage d'une EWMA a partir d'une constante de temps."""
    return 1 - math.exp(-1 / tau)


def compute_training_load(csv_path: Path = DEFAULT_CSV) -> pd.DataFrame:
    """Retourne un DataFrame journalier : load, atl, ctl, tsb, acwr."""
    acts = pd.read_csv(csv_path, parse_dates=["date"])

    # charge quotidienne = somme du relative_effort des activites du jour
    daily = acts.groupby("date")["relative_effort"].sum()

    # on reindexe sur tous les jours (les jours de repos comptent comme 0)
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    load = daily.reindex(full, fill_value=0).rename("load")

    df = load.to_frame()
    df["atl"] = load.ewm(alpha=_ewm_alpha(ATL_TAU), adjust=False).mean()
    df["ctl"] = load.ewm(alpha=_ewm_alpha(CTL_TAU), adjust=False).mean()
    df["tsb"] = df["ctl"] - df["atl"]

    # ACWR : charge aigue (7 j) sur charge chronique hebdo (28 j / 4).
    # On exige 28 jours pleins, sinon l'ACWR explose tant que le chronique
    # n'est pas etabli (artefact classique de debut de periode).
    acute = load.rolling(7, min_periods=7).sum()
    chronic = load.rolling(28, min_periods=28).sum() / 4
    df["acwr"] = (acute / chronic).replace([np.inf, -np.inf], np.nan)

    df.index.name = "date"
    return df


def acwr_on(date: pd.Timestamp, load_df: pd.DataFrame) -> float | None:
    """ACWR pour une date donnee, ou None si hors plage / indisponible."""
    ts = pd.Timestamp(date).normalize()
    if ts not in load_df.index:
        return None
    val = load_df.loc[ts, "acwr"]
    return None if pd.isna(val) else float(val)


if __name__ == "__main__":
    tl = compute_training_load()
    print(f"Periode : {tl.index.min().date()} -> {tl.index.max().date()} "
          f"({len(tl)} jours)")
    print(f"Charge totale : {int(tl.load.sum())}  |  pic journalier : {int(tl.load.max())}")
    print("\nDerniers jours :")
    print(tl.tail(7).round(1).to_string())
    print("\nPic de charge (top 5 jours) :")
    print(tl.load.sort_values(ascending=False).head(5).to_string())
