"""Constantes de configuration de l'app Readiness.

Tout est centralisé ici pour pouvoir ajuster le modèle sans toucher
à la logique : poids du score, fenêtre de baseline, seuils des feux.
"""

# Items du check-in quotidien.
# Convention : echelle 1-5, ou 5 = meilleur etat possible.
# On reformule les items "negatifs" (fatigue, courbatures) en positif
# (energie, fraicheur) pour garder une direction coherente sur tout le
# questionnaire. C'est plus simple cote calcul ET cote UX.
WELLNESS_ITEMS = [
    {
        "key": "sleep_quality",
        "label": "Qualite du sommeil",
        "help": "1 = tres mauvaise nuit, 5 = sommeil reparateur",
    },
    {
        "key": "energy",
        "label": "Niveau d'energie",
        "help": "1 = vide, 5 = plein d'energie",
    },
    {
        "key": "freshness",
        "label": "Fraicheur musculaire",
        "help": "1 = courbatures importantes, 5 = jambes fraiches",
    },
    {
        "key": "mood",
        "label": "Humeur / stress",
        "help": "1 = tendu / stresse, 5 = serein",
    },
    {
        "key": "motivation",
        "label": "Motivation",
        "help": "1 = aucune envie, 5 = tres motive",
    },
]

# Cle numerique supplementaire (echelle differente, en heures).
SLEEP_HOURS_KEY = "sleep_hours"

# Liste des composantes utilisees dans le score (wellness + duree sommeil).
SCORE_COMPONENTS = [item["key"] for item in WELLNESS_ITEMS] + [SLEEP_HOURS_KEY]

# Poids des composantes dans le score composite.
# Heuristique de depart, volontairement explicite. Ces poids pourraient
# etre appris une fois qu'on a une cible (ex: perf du lendemain).
WEIGHTS = {
    "sleep_quality": 1.0,
    "energy": 1.2,
    "freshness": 1.0,
    "mood": 0.8,
    "motivation": 0.8,
    "sleep_hours": 1.0,
}

# Fenetre de baseline individuelle (en jours) et minimum pour l'activer.
BASELINE_WINDOW = 28
BASELINE_MIN_DAYS = 7

# Mapping z-score -> indice 0-100. readiness = 50 + SCALE * z, clampe.
# Avec SCALE = 15, un z de +3.3 donne ~100, un z de -3.3 donne ~0.
Z_TO_SCORE_SCALE = 15.0

# Statuts (sur l'indice 0-100). Le score etant RELATIF a la baseline de
# l'athlete, l'essentiel des jours tourne autour de 50 = "dans sa norme".
# On garde donc un milieu neutre qui ne doit PAS se lire comme une alerte :
# seuls les ecarts marques (au-dessus / en dessous de la norme) ressortent.
#   >= 60         : fresh   (au-dessus de la norme, bonne dispo)
#   40 - 60       : normal  (dans la norme, neutre)
#   28 - 40       : caution (sous la norme, vigilance)
#   < 28          : fatigue (nettement sous la norme)
STATUS_THRESHOLDS = {
    "fresh": 60,
    "normal": 40,
    "caution": 28,
}

# Libelles et couleurs associes aux statuts (utilises par l'UI).
STATUS_META = {
    "fresh":   {"label": "Au-dessus de ta norme", "color": "#16a34a", "emoji": "🟢",
                "advice": "Bonne fenetre pour une seance qualite ou un bloc charge."},
    "normal":  {"label": "Dans ta norme",          "color": "#3b82f6", "emoji": "🔵",
                "advice": "Etat habituel, entrainement comme prevu."},
    "caution": {"label": "Sous ta norme",          "color": "#f59e0b", "emoji": "🟠",
                "advice": "Vigilance : adapter l'intensite, surveiller la recup."},
    "fatigue": {"label": "Fatigue marquee",        "color": "#dc2626", "emoji": "🔴",
                "advice": "Privilegier la recuperation, eviter la charge."},
    "unknown": {"label": "Donnees insuffisantes",  "color": "#94a3b8", "emoji": "⚪",
                "advice": "Continue les check-ins pour etablir ta baseline."},
}

# Bornes pour le fallback "cold start" de la duree de sommeil (heures -> 0..1).
SLEEP_HOURS_MIN = 5.0
SLEEP_HOURS_MAX = 8.5
