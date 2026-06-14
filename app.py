"""Readiness App - check-in quotidien de l'etat de forme d'un athlete.

Lancer avec :  streamlit run app.py
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config, database
from src.scoring import compute_readiness
from src.synthetic import generate_history

st.set_page_config(page_title="Readiness", layout="centered")


# ----------------------------- helpers UI -----------------------------

def gauge(score: float, status: str) -> go.Figure:
    meta = config.STATUS_META[status]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "", "font": {"size": 44}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": meta["color"]},
            "steps": [
                {"range": [0, 28], "color": "#fee2e2"},
                {"range": [28, 40], "color": "#fef3c7"},
                {"range": [40, 60], "color": "#dbeafe"},
                {"range": [60, 100], "color": "#dcfce7"},
            ],
        },
    ))
    fig.update_layout(height=240, margin=dict(t=10, b=10, l=20, r=20))
    return fig


def status_banner(status: str):
    meta = config.STATUS_META[status]
    st.markdown(
        f"<div style='padding:12px 16px;border-radius:10px;"
        f"background:{meta['color']}1a;border-left:5px solid {meta['color']};'>"
        f"<b>{meta['emoji']} {meta['label']}</b><br>"
        f"<span style='color:#475569'>{meta['advice']}</span></div>",
        unsafe_allow_html=True,
    )


# ----------------------------- sidebar -----------------------------

with st.sidebar:
    st.header("Donnees")
    st.caption("La baseline s'etablit apres "
               f"{config.BASELINE_MIN_DAYS} jours de check-in.")
    if st.button("Charger un historique demo (75 j)", use_container_width=True):
        database.reset_db()
        database.bulk_insert(generate_history())
        st.success("Historique demo charge.")
        st.rerun()
    if st.button("Reinitialiser", use_container_width=True):
        database.reset_db()
        st.rerun()
    st.divider()
    st.caption("Une fois le dataset Enduraw dispo, la charge d'entrainement "
               "(ACWR) viendra moduler le score via `scoring.apply_training_load`.")


# ----------------------------- data -----------------------------

raw = database.fetch_all()
scored = compute_readiness(raw) if not raw.empty else raw

tab_checkin, tab_trend, tab_method = st.tabs(
    ["Check-in du jour", "Mon etat dans le temps", "Methodo"]
)


# ----------------------------- tab : check-in -----------------------------

with tab_checkin:
    st.subheader("Comment tu te sens aujourd'hui ?")
    st.caption("Echelle 1 (bas) a 5 (haut).")

    today = date.today().isoformat()
    existing = raw[raw["date"] == pd.Timestamp(today)] if not raw.empty else pd.DataFrame()
    prefill = existing.iloc[0].to_dict() if not existing.empty else {}

    answers = {}
    for item in config.WELLNESS_ITEMS:
        answers[item["key"]] = st.slider(
            item["label"], 1, 5,
            int(prefill.get(item["key"], 3)),
            help=item["help"],
        )
    sleep_hours = st.number_input(
        "Heures de sommeil", 3.0, 12.0,
        float(prefill.get("sleep_hours", 7.5)), step=0.5,
    )
    note = st.text_input("Note libre (optionnel)", value=str(prefill.get("note", "") or ""))

    if st.button("Valider mon check-in", type="primary", use_container_width=True):
        record = {"date": today, **answers, "sleep_hours": sleep_hours, "note": note}
        database.upsert_checkin(record)
        st.success("Check-in enregistre.")
        st.rerun()

    # feedback immediat sur la readiness du jour
    if not scored.empty:
        today_row = scored[scored["date"] == pd.Timestamp(today)]
        if not today_row.empty and pd.notna(today_row.iloc[0]["readiness"]):
            r = today_row.iloc[0]
            st.divider()
            st.markdown("#### Ta readiness du jour")
            st.plotly_chart(gauge(r["readiness"], r["status"]),
                            use_container_width=True)
            status_banner(r["status"])
            if r["baseline_building"]:
                st.info("Baseline en construction : score calcule en absolu "
                        "pour l'instant, il deviendra relatif a ton historique.")


# ----------------------------- tab : tendance -----------------------------

with tab_trend:
    if scored.empty or len(scored) < 2:
        st.info("Pas encore assez de donnees. Fais quelques check-ins ou "
                "charge l'historique demo depuis la barre laterale.")
    else:
        last = scored.iloc[-1]
        prev = scored.iloc[-2]
        c1, c2, c3 = st.columns(3)
        c1.metric("Readiness du jour", f"{last['readiness']:.0f}",
                  f"{last['readiness'] - prev['readiness']:+.0f}")
        c2.metric("Moyenne 7 j", f"{scored['readiness'].tail(7).mean():.0f}")
        c3.metric("Jours suivis", len(scored))

        st.markdown("#### Readiness sur la periode")
        line = scored.set_index("date")[["readiness"]]
        st.line_chart(line, height=260)

        st.markdown("#### Composantes")
        comp_labels = {i["key"]: i["label"] for i in config.WELLNESS_ITEMS}
        chosen = st.multiselect(
            "Choisir les composantes",
            list(comp_labels.values()),
            default=[comp_labels["energy"], comp_labels["freshness"]],
        )
        if chosen:
            inv = {v: k for k, v in comp_labels.items()}
            keys = [inv[c] for c in chosen]
            st.line_chart(scored.set_index("date")[keys], height=240)

        st.markdown("#### Sommeil (heures)")
        st.bar_chart(scored.set_index("date")[["sleep_hours"]], height=200)


# ----------------------------- tab : methodo -----------------------------

with tab_method:
    st.markdown("""
#### Comment la readiness est calculee

Un score brut (ex : *sommeil 3/5*) ne veut rien dire dans l'absolu. Il prend
du sens **par rapport a la baseline de l'athlete lui-meme**.

1. **z-score individuel** : chaque composante est comparee a sa moyenne et son
   ecart-type sur les 28 jours precedents (fenetre glissante, sans fuite du
   jour courant).
2. **Composite pondere** : les z-scores sont agreges (poids explicites,
   ajustables, potentiellement appris).
3. **Indice 0-100** : `readiness = 50 + 15 * z`, borne entre 0 et 100. 50 = ta
   norme, au-dessus = supercompensation, en dessous = vigilance.
4. **Demarrage** : tant que la baseline n'est pas etablie, on utilise un
   mapping absolu, signale a l'utilisateur.

**Prochaine etape (a brancher avec les donnees Enduraw)** : moduler la readiness
avec la charge d'entrainement (ACWR, TSB/CTL/ATL) via
`scoring.apply_training_load`, pour distinguer une fatigue *attendue* (gros bloc)
d'une fatigue *anormale*.
    """)
