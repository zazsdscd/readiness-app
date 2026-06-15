# Demarche, choix de conception et pistes d'amelioration

## 1. Objectifs

Suivre l'évolution de l'etat physique et mental d'un athlete dans le temps. Deux contraintes :

- la saisie doit etre simple, rapide, sinon l'athlete arrete de la remplir et la serie
  temporelle se troue ;
- l'info captee doit rester assez fiable pour servir a une analyse.

J'ai donc d'abord travaille la qualite de la donnee dans le temps, avant de
m'occuper de l'interface.

## 2. Le questionnaire.

Plutot que multiplier les champs, je me suis base sur les questionnaires de
wellness utilises en sport de haut niveau (type Hooper), qui resument l'etat de
forme percu en 4 ou 5 questions. J'ai garde :

| Item | Pourquoi |
|---|---|
| Qualite du sommeil | Premier facteur de recuperation percue |
| Niveau d'energie | Reflet direct de la fatigue centrale |
| Fraicheur musculaire | Capte les courbatures, la fatigue des jambes |
| Humeur / stress | Charge mentale, souvent oubliee mais importante |
| Motivation | Signal precoce de lassitude ou de surmenage |

Plus la duree de sommeil, qui est presque une donnee objective et coute peu a
saisir.

Tous les items sont noté de 1 à 5 avec : 1 = mauvais état & 5 = bon etat. J'ai reformule les items negatifs (fatigue devient energie, courbatures deviennent fraicheur). C'est plus
clair a remplir et ca evite les inversions de signe dans le calcul.

## 3. Le score : une readiness propre a chaque athlete

Le point principal : une note brute ne dit pas grand-chose en absolu. Dormir 7h
ou se noter 3/5 en energie n'a pas le meme sens d'un  athlète a l'autre, ni
d'une periode a l'autre. Un seuil fixe pour tout le monde donnerait surtout du
bruit.

Le score compare donc chaque saisie a l'historique de l'athlete :

1. **z-score glissant** : pour chaque item, `z = (valeur - moyenne) / ecart-type`
   sur les 28 jours precedents. Le jour en cours est exclu de sa propre moyenne
   pour ne pas fausser le calcul.
2. **moyenne ponderee** des z-scores (l'energie et le sommeil pesent un peu
   plus). Les poids sont volontairement simples et modifiables.
3. **passage en 0-100** : `readiness = 50 + 15 * z`. 50 = la moyenne de
   l'athlete, au-dessus = meilleur que d'habitude, en dessous = a surveiller.
4. **un statut lisible** plutot qu'un feu alarmant : "dans ta norme" est l'etat
   normal la plupart du temps, seuls les vrais ecarts ressortent.

### Les premiers jours

Tant qu'il n'y a pas assez d'historique, la moyenne glissante n'existe pas.
Plutot que d'afficher du vide, le score passe par un calcul simple (1-5 ramene a
0-100), et l'app le signale. Il bascule en mode relatif apres 7 jours.

## 4. La charge d'entrainement, le volet objectif

Le ressenti subjectif prend tout son sens croise avec la charge reelle. Les
activites Strava (champ `relative_effort`) donnent une charge quotidienne, dont
on derive les indicateurs classiques du "performance manager" :

| Indicateur | Definition | Lecture |
|---|---|---|
| ATL | moyenne lissee de la charge sur 7 jours | fatigue recente |
| CTL | moyenne lissee de la charge sur 42 jours | forme de fond |
| TSB | CTL - ATL | fraicheur, positif = frais, negatif = fatigue de fond |
| ACWR | charge des 7 derniers jours / moyenne hebdo sur 28 jours | charge aigue vs chronique |

![Charge d'entrainement](training_load.png)

L'ACWR module ensuite la readiness (`scoring.apply_training_load`) : au-dela de
1.5, la charge aigue depasse nettement le niveau habituel, le score est penalise
car la fatigue est attendue ; dans la zone 0.8 a 1.3, charge soutenable, le score
est legerement valorise. La valeur avant modulation est conservee
(`readiness_base`), ce qui permet de distinguer une fatigue *attendue* (gros bloc,
ACWR en pic) d'une fatigue *anormale* a ressenti egal. Le ressenti synthetique de
la demo est lui-meme cale sur cette charge Strava reelle : l'energie et la
fraicheur baissent quand la charge du jour est forte et quand le TSB est negatif.

## 5. Stack technique

- **Streamlit** pour aller vite tout en gardant une saisie agreable. Le check-in
  tient sur un ecran.
- **SQLite** : un check-in par jour. Si on resaisit le meme jour, ca ecrase
  l'ancien. Simple, et facile a migrer vers Postgres plus tard sans toucher au
  calcul.
- **Tout le calcul est dans `src/scoring.py`**, regle depuis `src/config.py`. On
  change les poids, la fenetre ou les seuils sans toucher au reste.
- Le ressenti demo est synthetique mais cale sur la charge Strava reelle (rythme
  de la semaine, blocs charges issus des activites, mauvaises nuits) pour verifier
  que le score reagit comme prevu. Le graphe `docs/readiness_timeline.png` montre
  la readiness qui baisse sur les periodes de fatigue de fond et remonte ensuite.

## 6. Place dans l'ecosysteme Enduraw

La readiness est un signal subjectif, en complement des donnees objectives
recuperees a travers differents capteurs. Quelques usages :

- la croiser avec la charge d'entrainement pour distinguer une fatigue normale apres un gros bloc d'une
  fatigue inhabituelle ;
- garder une reference subjective propre a chaque athlete, qui se precise avec
  le temps ;
- plus tard, s'en servir comme base pour predire la perf ou un risque de
  blessure.

## 7. Limites et pistes

- **Subjectivite** : un athlete recalibre sa perception avec le temps. Le
  z-score individuel limite ce biais sans l'effacer. On pourrait reancrer de
  temps en temps avec des mesures objectives (HRV, FC repos).
- **Passage premiers jours / mode relatif** : la bascule a 7 jours cree une
  petite rupture. A lisser avec une moyenne ponderee entre les deux modes
  pendant la transition.
- **Poids fixes** : pour l'instant choisis a la main. Avec une cible (perf du
  lendemain, RPE de seance), on pourrait les apprendre par athlete.
- **Donnees manquantes** : un jour saute troue la moyenne. Prevoir une
  imputation simple et suivre le taux de remplissage.
- **Calibration de la charge** : la modulation par l'ACWR s'appuie sur de vraies
  donnees Strava, mais ses seuils (1.5, zone 0.8 a 1.3) et le poids relatif charge
  contre ressenti restent heuristiques. A calibrer avec une cible (perf, RPE) une
  fois les donnees Enduraw completes dispo.
- **Items par discipline** : le trail et le triathlon n'ont pas forcement les
  memes signaux importants. Un profil par sport serait un plus.
