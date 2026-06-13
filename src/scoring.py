"""Calcul de l'indice de readiness.

Idee centrale : un score brut (ex: "sommeil 3/5") ne veut rien dire dans
l'absolu. Il prend du sens par rapport a la baseline de l'athlete lui-meme.
On calcule donc un z-score glissant de chaque composante sur la moyenne et
l'ecart-type des jours precedents (fenetre BASELINE_WINDOW), puis on agrege.

Tant que la baseline n'est pas etablie (< BASELINE_MIN_DAYS), on bascule sur
un mapping absolu pour ne pas renvoyer du vide les premiers jours.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _rolling_baseline_z(series: pd.Series) -> pd.Series:
    """z-score de chaque point vs baseline des jours STRICTEMENT precedents.

    On decale d'un cran (shift) pour eviter que la valeur du jour ne pollue
    sa propre baseline (pas de fuite d'information).
    """
    mean = series.rolling(
        config.BASELINE_WINDOW, min_periods=config.BASELINE_MIN_DAYS
    ).mean().shift(1)
    std = series.rolling(
        config.BASELINE_WINDOW, min_periods=config.BASELINE_MIN_DAYS
    ).std().shift(1)

    z = (series - mean) / std
    # std nul (athlete tres regulier) -> pas d'ecart significatif -> z = 0
    z = z.where(std.fillna(0) > 0, 0.0)
    # baseline pas encore dispo -> NaN (gere par le fallback en aval)
    z = z.where(mean.notna(), np.nan)
    return z


def _absolute_fallback(row: pd.Series) -> float:
    """Mapping absolu 0-100 pour la phase de demarrage (cold start)."""
    parts, weights = [], []
    for item in config.WELLNESS_ITEMS:
        val = row.get(item["key"])
        if pd.notna(val):
            parts.append((float(val) - 1) / 4)  # 1-5 -> 0..1
            weights.append(config.WEIGHTS[item["key"]])
    h = row.get(config.SLEEP_HOURS_KEY)
    if pd.notna(h):
        norm = (float(h) - config.SLEEP_HOURS_MIN) / (
            config.SLEEP_HOURS_MAX - config.SLEEP_HOURS_MIN
        )
        parts.append(float(np.clip(norm, 0, 1)))
        weights.append(config.WEIGHTS[config.SLEEP_HOURS_KEY])
    if not parts:
        return np.nan
    return float(np.average(parts, weights=weights) * 100)


def compute_readiness(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute readiness, statut et z-scores par composante au DataFrame.

    df doit etre trie par date croissante et contenir les colonnes des
    composantes (cf config.SCORE_COMPONENTS).
    """
    if df.empty:
        return df.assign(readiness=[], status=[], baseline_building=[])

    out = df.sort_values("date").reset_index(drop=True).copy()
    out["date"] = pd.to_datetime(out["date"])

    # z-score par composante
    z_cols = []
    for comp in config.SCORE_COMPONENTS:
        if comp in out.columns:
            zc = f"z_{comp}"
            out[zc] = _rolling_baseline_z(out[comp].astype(float))
            z_cols.append((comp, zc))

    readiness, statuses, building = [], [], []
    for _, row in out.iterrows():
        # composite z pondere sur les composantes ou la baseline existe
        zs, ws = [], []
        for comp, zc in z_cols:
            if pd.notna(row[zc]):
                zs.append(row[zc])
                ws.append(config.WEIGHTS[comp])

        if len(zs) >= 3:  # baseline suffisante
            z_comp = np.average(zs, weights=ws)
            score = 50 + config.Z_TO_SCORE_SCALE * z_comp
            is_building = False
        else:  # cold start
            score = _absolute_fallback(row)
            is_building = True

        score = float(np.clip(score, 0, 100)) if pd.notna(score) else np.nan
        readiness.append(round(score, 1) if pd.notna(score) else np.nan)
        statuses.append(_status(score))
        building.append(is_building)

    out["readiness"] = readiness
    out["status"] = statuses
    out["baseline_building"] = building
    return out


def _status(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= config.STATUS_THRESHOLDS["fresh"]:
        return "fresh"
    if score >= config.STATUS_THRESHOLDS["normal"]:
        return "normal"
    if score >= config.STATUS_THRESHOLDS["caution"]:
        return "caution"
    return "fatigue"


# --- Hook pour la charge d'entrainement (a brancher quand le dataset arrive) ---

def apply_training_load(readiness: float, acwr: float | None) -> float:
    """Module la readiness selon l'ACWR (acute:chronic workload ratio).

    Stub volontairement simple : on penalise une charge en pic (>1.5) et on
    valorise legerement une zone "sweet spot" (0.8-1.3). A calibrer avec les
    vraies donnees Enduraw. Permet de montrer ou se branche le volet objectif.
    """
    if acwr is None or pd.isna(acwr):
        return readiness
    if acwr > 1.5:
        return float(np.clip(readiness - 15, 0, 100))
    if 0.8 <= acwr <= 1.3:
        return float(np.clip(readiness + 3, 0, 100))
    return readiness
