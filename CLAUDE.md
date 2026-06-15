# CLAUDE.md

Contexte projet pour Claude Code. Lis ce fichier avant toute modification.

## Projet

Readiness App : application Streamlit de check-in quotidien de l'etat de forme
d'un athlete d'endurance. Cas technique pour Enduraw (poste Data Scientist).
L'app capte un ressenti subjectif quotidien, le croise avec la charge
d'entrainement reelle issue de Strava, et restitue un indice de readiness.

## Stack

- Python 3.9+ (tout fichier avec annotations de type commence par
  `from __future__ import annotations`)
- Streamlit (UI), SQLite (persistance check-ins), pandas / numpy
- plotly (jauge, graphes interactifs), matplotlib (graphes statiques pour les docs)

## Lancer

```bash
source .venv/bin/activate
streamlit run app.py          # l'app
python analysis.py            # analyse + graphes statiques pour docs/
```

## Architecture

```
app.py                 # interface Streamlit (onglets)
analysis.py            # analyse DS + generation des graphes docs/
src/config.py          # items, poids, fenetres, seuils (toute la config)
src/database.py        # persistance SQLite, 1 check-in par jour
src/scoring.py         # calcul de la readiness (coeur)
src/synthetic.py       # generateur de ressenti synthetique pour la demo
src/training_load.py   # charge d'entrainement (ATL/CTL/TSB/ACWR) depuis Strava
data/strava_activities.csv  # activites Strava reelles (champs non sensibles)
docs/demarche.md       # document de demarche (livrable principal)
```

## Modele de readiness (ne pas casser cette logique)

1. Le score est RELATIF a la baseline de l'athlete : z-score glissant de chaque
   composante sur 28 jours (fenetre dans config), jour courant exclu de sa
   propre baseline.
2. Composite pondere des z-scores (poids dans `config.WEIGHTS`).
3. `readiness = 50 + 15 * z`, borne 0-100. 50 = la norme de l'athlete.
4. Avant 7 jours d'historique : fallback en mapping absolu, signale a l'user.
5. Statuts en 4 bandes (fresh / normal / caution / fatigue), milieu neutre.

## Modele de charge d'entrainement (deja implemente dans training_load.py)

- charge quotidienne = somme du `relative_effort` Strava du jour
- ATL = EWMA 7 j (fatigue), CTL = EWMA 42 j (forme de fond)
- TSB = CTL - ATL (fraicheur)
- ACWR = charge 7 j / (charge 28 j / 4), calcule seulement apres 28 j pleins
- `apply_training_load(readiness, acwr)` module la readiness : penalise un ACWR
  en pic (>1.5), valorise legerement la zone 0.8-1.3

## Conventions de style (strict)

- AUCUN em-dash. Utiliser des virgules a la place.
- AUCUN emoji dans le code ni dans l'app.
- Texte visible par l'utilisateur en francais.
- Input "heures de sommeil" affiche en format 7h30 (select_slider), pas 7.5.
- Dans les docs : metriques chiffrees dans des tableaux, prose plutot que
  listes a puces partout, ton sobre et direct.
- Ne pas reecrire les tournures de phrase existantes des docs sans raison.

## Git

- `data/*.db` est gitignore. Le CSV Strava, lui, EST versionne.
- Commits en anglais, concis, imperatif.
```
