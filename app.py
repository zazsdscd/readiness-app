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
from src.training_load import acwr_on, compute_training_load, DEFAULT_CSV

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


def fmt_duration(seconds: float) -> str:
    minutes = int(round(float(seconds) / 60))
    hh, mm = divmod(minutes, 60)
    return f"{hh}h{mm:02d}" if hh else f"{mm} min"


def training_load_chart(load_df: pd.DataFrame) -> go.Figure:
    """CTL et ATL en courbes, zone TSB coloree selon son signe."""
    d = load_df.reset_index()
    fig = go.Figure()
    # zone TSB : vert au-dessus de zero (frais), rouge en dessous (fatigue)
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["tsb"].clip(lower=0), fill="tozeroy", mode="none",
        fillcolor="rgba(22,163,74,0.25)", name="TSB positif (frais)"))
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["tsb"].clip(upper=0), fill="tozeroy", mode="none",
        fillcolor="rgba(220,38,38,0.25)", name="TSB negatif (fatigue)"))
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["ctl"], mode="lines", name="CTL (forme de fond)",
        line=dict(color="#2563eb", width=2)))
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["atl"], mode="lines", name="ATL (fatigue recente)",
        line=dict(color="#f59e0b", width=2)))
    fig.update_layout(
        height=340, margin=dict(t=10, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_title="charge (relative effort)",
    )
    return fig


@st.cache_data
def load_training_load() -> pd.DataFrame:
    return compute_training_load()


@st.cache_data
def load_activities() -> pd.DataFrame:
    return pd.read_csv(DEFAULT_CSV, parse_dates=["date"])


# ----------------------------- sidebar -----------------------------

with st.sidebar:
    st.header("Donnees")
    st.caption("La baseline s'etablit apres "
               f"{config.BASELINE_MIN_DAYS} jours de check-in.")
    if st.button("Charger l'historique demo", use_container_width=True):
        database.reset_db()
        database.bulk_insert(generate_history())
        st.success("Historique demo charge.")
        st.rerun()
    if st.button("Reinitialiser", use_container_width=True):
        database.reset_db()
        st.rerun()
    st.divider()
    st.caption("Le ressenti demo est cale sur la charge Strava reelle, et la "
               "readiness est modulee par l'ACWR via "
               "`scoring.apply_training_load`.")


# ----------------------------- data -----------------------------

load_df = load_training_load()
raw = database.fetch_all()
scored = compute_readiness(raw, load_df) if not raw.empty else raw

tab_checkin, tab_trend, tab_load, tab_method = st.tabs(
    ["Check-in du jour", "Mon etat dans le temps",
     "Charge d'entrainement", "Methodo"]
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
    def fmt_hours(h):
        total_min = int(round(float(h) * 60))
        hh, mm = divmod(total_min, 60)
        return f"{hh}h{mm:02d}"
    sleep_opts = [round(3.0 + 0.25 * i, 2) for i in range(int((12.0 - 3.0) / 0.25) + 1)]
    default_sleep = float(prefill.get("sleep_hours", 7.5))
    if default_sleep not in sleep_opts:
        default_sleep = min(sleep_opts, key=lambda x: abs(x - default_sleep))
    sleep_hours = st.select_slider(
        "Heures de sommeil",
        options=sleep_opts,
        value=default_sleep,
        format_func=fmt_hours,
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
            acwr_today = acwr_on(pd.Timestamp(today), load_df)
            if acwr_today is not None and acwr_today > 1.5:
                st.caption(
                    f"Charge recente elevee (ACWR {acwr_today:.2f}) : une baisse "
                    "de readiness est attendue, la fatigue est coherente avec ton "
                    "bloc d'entrainement et non un signal anormal.")
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


# ----------------------------- tab : charge -----------------------------

with tab_load:
    st.subheader("Charge d'entrainement (Strava)")
    st.caption("Charge quotidienne = relative effort cumule du jour. "
               "ATL = fatigue 7 j, CTL = forme de fond 42 j, TSB = CTL - ATL.")

    last_load = load_df.iloc[-1]
    acwr_today = acwr_on(load_df.index[-1], load_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("CTL (forme)", f"{last_load['ctl']:.0f}")
    c2.metric("ATL (fatigue)", f"{last_load['atl']:.0f}",
              f"TSB {last_load['tsb']:+.0f}")
    c3.metric("ACWR du jour",
              f"{acwr_today:.2f}" if acwr_today is not None else "n/a")

    st.plotly_chart(training_load_chart(load_df), use_container_width=True)

    st.markdown("#### Dernieres activites")
    acts = load_activities().sort_values("date", ascending=False).head(15)
    table = pd.DataFrame({
        "Date": acts["date"].dt.strftime("%Y-%m-%d"),
        "Sport": acts["sport_type"],
        "Duree": acts["moving_time_s"].map(fmt_duration),
        "Charge": acts["relative_effort"].astype(int),
    })
    st.dataframe(table, use_container_width=True, hide_index=True)


# ----------------------------- tab : methodo -----------------------------

with tab_method:
    st.markdown("""
#### Comment la readiness est calculee

Un score brut (ex : *sommeil 3/5*), prend
du sens **par rapport a la baseline de l'athlete**.

1. **z-score individuel** : chaque composante est comparee a sa moyenne et son
   ecart-type sur les 28 jours precedents (fenetre glissante, sans fuite du
   jour courant).
2. **Composite pondere** : les z-scores sont agreges (poids explicites,
   ajustables, potentiellement appris).
3. **Indice 0-100** : `readiness = 50 + 15 * z`, borne entre 0 et 100. 50 = ta
   norme, au-dessus = supercompensation, en dessous = vigilance.
4. **Demarrage** : tant que la baseline n'est pas etablie, on utilise un
   mapping absolu, signale a l'utilisateur.

5. **Charge d'entrainement** : la readiness relative est ensuite modulee par
   la charge reelle issue de Strava (ACWR, TSB/CTL/ATL) via
   `scoring.apply_training_load`. La valeur avant modulation est conservee
   (`readiness_base`). Cela permet de distinguer une fatigue *attendue* (gros
   bloc, ACWR en pic) d'une fatigue *anormale*. Voir l'onglet
   *Charge d'entrainement*.
    """)
