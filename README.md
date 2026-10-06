# 8INF867 : Travail pratique 1

**Apprentissage supervisé : d'un fichier de laboratoire à un classifieur évalué**

Sujet distribué le 1er octobre 2026. Remise le 22 octobre 2026 à 23 h 59.
Pondération : 20 % de la note finale. Travail individuel.

Ce fichier est l'énoncé complet du travail. Il n'y en a pas d'autre.

---

## 1. Contexte

Un exploitant industriel suit l'état de ses machines par analyse périodique de
l'huile de lubrification. Chaque prélèvement part vers un laboratoire qui
mesure les concentrations d'éléments métalliques, la viscosité, la teneur en
eau et l'indice d'oxydation. Lorsque les résultats l'inquiètent, le service de
maintenance déclenche une alerte et programme une intervention.

Le fichier `data/oil_samples.csv` rassemble deux années de prélèvements sur un
parc de soixante machines, analysés par trois laboratoires. Il a été constitué
par concaténation d'exports successifs, sans contrôle de cohérence. Il est
donc dans l'état où vous trouverez ce genre de fichier en entreprise :
utilisable, mais pas exploitable en l'état.

Votre objectif est de produire un tableau propre, puis un classifieur qui
prédit le déclenchement d'une alerte à partir des seules informations
disponibles au moment du prélèvement.

**L'essentiel du travail n'est pas la modélisation.** Le classifieur final
occupera moins de deux heures sur les douze que représente ce travail. Le reste
est du diagnostic : comprendre ce que contient ce fichier, pourquoi il ne dit
pas ce qu'il a l'air de dire, et ce qu'il faut lui faire subir pour qu'il le
dise.

---

## 2. Notion du domaine

Une seule notion du fichier ne relève pas de la science des données et suffit
pour comprendre R6 : la viscosité. Tout le reste du règlement se comprend sans
connaissance de l'analyse d'huile.

**Viscosité, centistokes et secondes Saybolt.** La viscosité cinématique
mesure la résistance d'un fluide à l'écoulement. Elle se rapporte en
centistokes (cSt), avec 1 cSt = 1 mm²/s
([Stokes (unité)](https://fr.wikipedia.org/wiki/Stokes_(unit%C3%A9))). Certains
laboratoires rapportent à la place un temps d'écoulement en secondes Saybolt
universelles (SUS), une échelle plus ancienne décrite sur la page
[Saybolt universal viscosity](https://en.wikipedia.org/wiki/Saybolt_universal_viscosity)
et normalisée par [ASTM D2161](https://store.astm.org/d2161-20r25.html). Ce
travail applique le facteur unique de l'annexe, une division par 4,635 pour
passer des SUS aux cSt. La
[table de conversion de Cole-Parmer](https://www.coleparmer.ca/tech-article/viscosity-conversion-factors)
permet de vérifier un ordre de grandeur : 1 000 SUS correspondent à environ
216 cSt.

---

## 3. Ce que vous devez rendre

Un dépôt Git contenant votre implémentation de `src/pipeline.py`. Ce fichier
est le point d'entrée : c'est lui que `app.py` et la suite de tests importent.
Vous pouvez ajouter les dossiers et les fichiers que vous jugez utiles
(modules auxiliaires, notebooks d'exploration, notes), en nombre illimité, à
deux conditions : ils sont versionnés dans le dépôt, et `pytest tests/`, lancé
depuis la racine du dépôt, s'exécute sans autre manipulation de votre part.
Vos modules s'importent depuis la racine (`from src.outils import ...`), pas
par un chemin relatif au fichier.

Trois fonctions constituent le contrat d'interface et doivent rester
importables depuis `src.pipeline`. Leurs noms, leurs signatures et la nature
de ce qu'elles renvoient sont imposés.

```python
clean(brut)             -> DataFrame nettoyé
split(propre)           -> (entraînement, test)
build_model(entrainement) -> sklearn.pipeline.Pipeline non ajusté
```

`app.py`, `src/annexe.py` et `tests/` sont fournis et ne doivent pas être
modifiés. Le dossier `tests/` est en outre fermé à tout ajout : n'y déposez
aucun fichier, y compris vos propres tests (placez-les ailleurs, dans un dossier
`essais/` par exemple). Ces éléments sont réécrits à l'identique avant la
correction, `tests/` étant supprimé puis restauré en entier : une modification
ou un ajout de votre part serait sans effet sur votre note.

Le fichier `requirements.txt` est fixe : aucune dépendance supplémentaire ne
sera installée.

---

## 4. Mise en route

L'environnement d'exécution est fourni sous forme de conteneur Docker. Il
contient Python 3.14 et les versions exactes des bibliothèques
(`requirements.txt`), ainsi que les éléments
imposés (`app.py`, `src/annexe.py`, `data/oil_samples.csv` et `tests/`). Votre
dépôt y est monté en lecture seule ; vous continuez donc à éditer vos fichiers
avec votre éditeur habituel. Docker Desktop (Windows, macOS) ou Docker Engine
avec le plugin Compose (Linux) suffit.

```bash
docker compose up --build
```

Cette commande est la seule à connaître. Elle construit l'image, lance
`pytest tests/` sur votre dépôt, affiche le résultat et s'arrête sur votre
note, par exemple `Note : 85 / 100`. Relancez-la après chaque modification de
votre code.

Sous Linux, si le conteneur signale que le dépôt n'est pas lisible, faites
précéder la commande de `TP_UID=$(id -u) TP_GID=$(id -g)`.

Le conteneur n'a pas accès au réseau et dispose de deux processeurs, de 2 Go de
mémoire et de quinze minutes ; ce sont les conditions de la correction. Si vous
préférez travailler sans Docker pendant la mise au point, un environnement
virtuel Python 3.14 suffit (`python3.14 -m venv .venv`, activation,
`pip install -r requirements.txt`, puis `pytest tests/`, ou `python app.py` pour
afficher le rapport de classification), mais la validation finale se fait avec
la commande Docker ci-dessus.

---

## 5. Règlement de traitement

Ce qu'il faut corriger n'est pas indiqué ; **comment** le corriger l'est
intégralement. Le règlement ci-dessous fixe une politique unique pour chaque
type de traitement, de sorte que deux implémentations correctes produisent le
même tableau. Il ne nomme aucune colonne fautive et aucune ligne : c'est à vous
de les trouver.

**Clause liminaire.** Tous les critères statistiques du règlement (médiane par
laboratoire, part de la modalité dominante, fréquence d'une valeur exacte) se
calculent sur le tableau tel qu'il est chargé, avant toute suppression de
ligne. L'ordre des opérations est donc libre, à la seule exception signalée en
R12.

**R1. Typage.** Les colonnes de mesure listées en annexe sont ramenées au type
flottant. Une valeur numérique écrite en texte se lit en supprimant les
espaces, y compris les espaces insécables, et en remplaçant la virgule
décimale par un point.

**R2. Valeurs manquantes.** Les jetons de l'annexe désignent une absence et
deviennent des valeurs manquantes, quelle que soit la colonne. Tous ne sont pas
nécessairement présents dans le fichier.

**R3. Catégorielles.** Les identifiants textuels sont canonisés : suppression
des espaces de bordure, suppression des accents, passage en majuscules,
suppression de tout caractère non alphanumérique, puis réinsertion d'un tiret
devant le groupe final de chiffres, ou devant la dernière lettre si la valeur
ne contient aucun chiffre. Ainsi `at-03`, `AT03 ` et `AT-03` désignent le même
atelier, et `LABA` s'écrit `LAB-A`.

**R4. Laboratoire absent.** Un laboratoire manquant est rétabli par la
correspondance entre machine et laboratoire, établie sur les lignes où il est
renseigné ; la modalité majoritaire de la machine fait foi.

**R5. Dates.** Le format est déterminé laboratoire par laboratoire. Un
laboratoire dont au moins une date porte un premier champ supérieur à douze
écrit en jour-mois ; les autres écrivent en mois-jour. Le format retenu
s'applique à toutes les dates de ce laboratoire.

**R6. Unités.** La viscosité s'exprime en centistokes. Un laboratoire dont la
viscosité médiane dépasse le seuil donné en annexe rapporte en secondes
Saybolt ([notion du domaine](#2-notion-du-domaine)) ; ses valeurs sont
divisées par le facteur de conversion de l'annexe et arrondies au centième.

**R7. Bornes physiques.** Toute valeur hors de l'intervalle admissible de sa
colonne devient manquante. La ligne n'est pas supprimée.

**R8. Cohérence interne.** Lorsque les heures de service depuis la dernière
vidange dépassent les heures de service cumulées de la machine, la première
devient manquante.

**R9. Artefacts de capteur.** Dans une colonne numérique, une valeur exacte
portée par une part des observations renseignées supérieure au seuil de
l'annexe est un artefact de saturation ; les cellules concernées deviennent
manquantes.

**R10. Fenêtre de collecte.** Les prélèvements datés hors de la période donnée
en annexe sont supprimés.

**R11. Périmètre.** Les prélèvements dont l'atelier canonisé est absent du
référentiel de l'annexe sont supprimés.

**R12. Étiquettes contradictoires.** La clé métier d'un prélèvement est le
couple machine et date. Lorsque les lignes partageant une même clé ne portent
pas toutes la même étiquette, la clé entière est supprimée. **Cette règle
s'applique avant R13 ; c'est la seule précédence imposée du règlement.**

**R13. Doublons.** Parmi les lignes restantes partageant une même clé métier,
une seule est conservée : celle dont l'identifiant de prélèvement est le plus
petit.

**R14. Colonnes retirées.** Est retirée toute colonne dont une modalité
représente une part des valeurs renseignées supérieure au seuil de l'annexe,
toute colonne dont l'information n'est pas disponible au moment du
prélèvement, et tout identifiant technique ou champ de saisie libre.
L'identifiant de machine est conservé, non comme variable explicative mais
comme clé de regroupement pour la partition.

**R15. Forme du tableau.** Le tableau retourné est trié par date puis par
machine, et son index est réinitialisé. Les colonnes de mesure sont de type
flottant, la date de type datetime, la cible de type entier. Le tableau passé
en entrée n'est pas modifié sur place.

**R16. Frontière.** Aucune imputation, aucune mise à l'échelle, aucun encodage
n'est effectué dans `clean`. Ces opérations estiment un paramètre sur une
population et appartiennent au `Pipeline` retourné par `build_model`, que
scikit-learn ajustera sur le seul ensemble d'entraînement.

**R17. Partition.** La partition se fait par machine : aucune machine ne peut
figurer dans les deux ensembles. La part de test et la graine sont données en
annexe.

---

## 6. Annexe technique

Toutes les constantes du règlement sont dans `src/annexe.py`, qui fait partie
de l'énoncé : dictionnaire des colonnes de mesure, jetons d'absence, bornes
physiques, référentiel des ateliers, fenêtre de collecte, facteur de conversion
Saybolt, seuils de R9 et R14, paramètres de partition, enveloppe de
performance. Importez-les plutôt que de les recopier.

La cible est `alert`. Le score retenu est l'exactitude (accuracy) sur l'ensemble de test.

---

## 7. Comment vous êtes évalué

### Suite de tests

Votre note est le résultat de `pytest tests/` exécuté sur votre dépôt à
l'échéance ; il n'existe pas d'autre suite. `pytest tests/` exécute dix-sept
tests que vous pouvez lancer autant de fois que vous le voulez. Chaque test nomme **la propriété qu'il vérifie**, jamais le
défaut qui la met en défaut. `test_05_temporal_consistency` vous dit où
regarder ; il ne vous dit pas ce qui cloche dans les dates.

Aucun test ne compare votre résultat à un tableau de référence. Tous vérifient
des propriétés, calculées soit sur votre tableau, soit directement sur le
fichier brut.

| Test | Propriété vérifiée | Points |
|---|---|---:|
| `test_01_sample_uniqueness` | unicité des prélèvements | 5 |
| `test_02_missing_value_encoding` | aucune absence déguisée en valeur | 5 |
| `test_03_column_typing` | chaque colonne porte le type que son contenu appelle | 5 |
| `test_04_category_normalization` | une réalité, une écriture | 5 |
| `test_05_temporal_consistency` | dates lisibles et dans la fenêtre | 5 |
| `test_06_physical_plausibility` | mesures dans leur domaine physique | 5 |
| `test_07_legitimate_extremes_preserved` | aucune mesure légitime n'est perdue, queue haute comprise | 5 |
| `test_08_unit_homogeneity` | une grandeur, une unité | 5 |
| `test_09_sensor_artifacts` | aucune valeur exacte surreprésentée | 5 |
| `test_10_label_consistency` | aucune étiquette contestée conservée | 5 |
| `test_11_fleet_scope` | le parc retenu est celui du référentiel | 5 |
| `test_12_residual_volume` | l'effectif final est celui qui se déduit du brut | 5 |
| `test_13_target_independence` | aucune colonne ne sait l'avenir | 8 |
| `test_14_group_partitioning` | aucune machine des deux côtés | 8 |
| `test_15_fit_on_training_only` | les paramètres appris viennent de l'entraînement | 8 |
| `test_16_performance_envelope` | le score tient dans l'enveloppe | 8 |
| `test_17_determinism` | deux exécutions donnent le même résultat | 8 |

Le test 07 mérite un avertissement. Certaines valeurs de ce fichier sont
extrêmes **et parfaitement réelles** : une machine en fin de vie produit
légitimement des concentrations de fer très au-dessus de l'ordinaire, et ce
sont les prélèvements les plus informatifs du jeu de données. Une stratégie
consistant à écrêter tout ce qui dépasse échouera. Distinguer l'impossible du
rare est le cœur de ce travail.

Le test 16 encadre le score par un plancher et un plafond. Le plancher signale
une chaîne qui a perdu du signal. **Le plafond signale l'inverse : un score
trop élevé n'est pas une bonne nouvelle.**

### Règles, pas réponses

Votre code doit encoder des règles, pas des réponses : une implémentation qui
s'appuie sur des index ou des valeurs précis du fichier, et que vous ne savez
pas expliquer, est traitée comme telle (section 8).

### Conditions d'exécution

La correction utilise le conteneur décrit à la section 4, construit à partir du
dépôt de référence et non de votre copie : votre dépôt est cloné tel qu'il se
trouve sur `main` et monté en lecture seule ; `app.py`, `src/annexe.py` et
`data/oil_samples.csv` y sont remplacés par les versions de l'image, le dossier
`tests/` est supprimé puis restauré en entier, et les fichiers de configuration
de pytest que vous auriez placés à la racine sont ignorés. La correction
consiste à lancer `pytest tests/` depuis la racine ; tout ce qui n'y roule pas
ne compte pas. Le code s'exécute sans accès réseau, avec une limite de temps et
de mémoire. Un module qui importerait une bibliothèque absente de
`requirements.txt` fait échouer l'importation de `src.pipeline`. Toute rupture
du contrat d'interface produit zéro sur les tests concernés.

### Pondération

La note est sur 100. Chacun des douze premiers tests (nettoyage) vaut 5 points
et chacun des cinq suivants (absence de fuite, partition, ajustement,
enveloppe de score, déterminisme) vaut 8 points ; un test est réussi en entier
ou ne rapporte rien. Un test qui ne peut pas s'exécuter parce que
`src.pipeline` ne s'importe pas ou qu'une fonction du contrat manque rapporte
zéro. La suite affiche votre note en dernière ligne, après le bilan de pytest,
sous la forme `Note : 85 / 100`. Aucun rapport n'est demandé.

---

## 8. Règles

Travail strictement individuel. Les remises sont passées à un outil de
détection de similarité de code. L'écriture de code assistée est autorisée,
mais vous répondez de chaque ligne que vous remettez : une implémentation que
vous ne savez pas expliquer sera traitée comme telle.

L'accès en écriture à votre dépôt est coupé automatiquement à l'échéance. Tout
travail en retard sans motif valable préalablement discuté se voit attribuer la
note zéro. Le dernier état poussé sur `main` avant la coupure fait foi.

Les questions d'intérêt général vont dans le canal `#discussion` du Discord du
cours. Une réponse vous parvient sous 48 heures.
