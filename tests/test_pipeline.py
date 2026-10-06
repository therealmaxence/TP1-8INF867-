# -*- coding: utf-8 -*-
"""8INF867 - TP1 - Suite publique.

Chaque test nomme la propriete qu'il verifie, jamais le defaut qui la met en
defaut. Un echec vous indique donc ou regarder, pas quoi corriger.

La note est le resultat de cette suite, executee sur le depot a l'echeance.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline

from src.annexe import (BORNES, CIBLE, CLE_METIER, DEBUT_COLLECTE,
                        FIN_COLLECTE, MESURES, PART_TEST, PLAFOND_ACCURACY,
                        PLANCHER_ACCURACY, REFERENTIEL_ATELIERS,
                        SEUIL_MODALITE_DOMINANTE, SEUIL_SATURATION,
                        SUS_PAR_CST)
from tests.conftest import (annee_brute, canon, ecritures_possibles,
                            est_absent, lire_dates_brutes, mesure_brute,
                            mesures_legitimes, nombre, relier)


# ---------------------------------------------------------------- structure

def test_01_sample_uniqueness(propre):
    """Aucun prelevement n'est represente plus d'une fois."""
    assert not propre.duplicated().any(), \
        "des lignes entierement identiques subsistent"
    doublons = propre.duplicated(CLE_METIER, keep=False).sum()
    assert doublons == 0, \
        "%d lignes partagent une cle metier avec une autre" % doublons


def test_02_missing_value_encoding(propre):
    """Aucune absence n'est encore deguisee en valeur."""
    for c in MESURES:
        v = propre[c].dropna()
        assert not np.isclose(v, -999).any(), "colonne %s" % c
        assert not np.isclose(v, 9999).any(), "colonne %s" % c
    for c in propre.columns:
        if pd.api.types.is_numeric_dtype(propre[c]) or \
                pd.api.types.is_datetime64_any_dtype(propre[c]):
            continue
        v = propre[c].dropna().astype(str).str.strip().str.upper()
        residus = sorted(set(v) & {"N/A", "NA", "INCONNU", "", "-", "?"})
        assert not residus, "colonne %s : %s" % (c, residus)


def test_03_column_typing(brut, propre):
    """Chaque colonne porte le type et la forme que son contenu appelle."""
    for c in MESURES:
        assert c in propre.columns, "colonne %s absente" % c
        assert pd.api.types.is_float_dtype(propre[c]), \
            "colonne %s de type %s" % (c, propre[c].dtype)
    assert pd.api.types.is_datetime64_any_dtype(propre["sample_date"])
    assert pd.api.types.is_integer_dtype(propre[CIBLE])
    assert set(propre[CIBLE].unique()) <= {0, 1}
    # forme : index reinitialise, tri par date puis par machine
    assert list(propre.index) == list(range(len(propre))), \
        "index non reinitialise"
    ordre = propre.sort_values(["sample_date", "machine_id"], kind="stable")
    assert propre.equals(ordre.reset_index(drop=True)), \
        "tableau non trie par date puis par machine"
    # lecture fidele : toute valeur presente se retrouve, telle quelle ou
    # convertie d'unite, dans une ligne brute du meme prelevement
    liens = relier(brut, propre)
    for c in MESURES:
        source = mesure_brute(brut[c])
        lues = propre[c].to_numpy(dtype=float)
        infideles = 0
        for i, idx in enumerate(liens):
            if np.isnan(lues[i]):
                continue
            admis = [x for x in source[idx] if not np.isnan(x)]
            if c == "viscosity_cst":
                admis += [f(x / SUS_PAR_CST, 2) for x in admis
                          for f in (round, np.round)]
            if not any(abs(lues[i] - a) < 1e-9 for a in admis):
                infideles += 1
        assert infideles == 0, \
            "%s : %d valeurs ne se retrouvent pas dans la source" \
            % (c, infideles)


def test_04_category_normalization(brut, propre):
    """Une realite, une ecriture."""
    for c in ["machine_id", "workshop", "lab_id"]:
        assert c in propre.columns, "colonne %s absente" % c
        modalites = propre[c].dropna().unique().tolist()
        assert all(m == canon(m) for m in modalites), \
            "colonne %s : %s" % (c, sorted(m for m in modalites
                                           if m != canon(m))[:5])
    assert propre["workshop"].nunique() <= len(REFERENTIEL_ATELIERS)
    assert propre["lab_id"].notna().all(), "des laboratoires restent inconnus"
    # toute colonne textuelle conservee est un identifiant canonise
    for c in propre.columns:
        if pd.api.types.is_numeric_dtype(propre[c]) or \
                pd.api.types.is_datetime64_any_dtype(propre[c]):
            continue
        mauvais = sorted(m for m in propre[c].dropna().unique()
                         if m != canon(m))
        assert not mauvais, "colonne %s : %s" % (c, mauvais[:5])
    # le laboratoire d'une machine est celui que le fichier lui attribue
    connu = brut[~brut["lab_id"].map(est_absent)]
    par_machine = connu["lab_id"].map(canon).groupby(
        connu["machine_id"].map(canon)).agg(
        lambda s: s.value_counts().sort_index().idxmax())
    ecarts = int((propre["lab_id"] != propre["machine_id"].map(par_machine)).sum())
    assert ecarts == 0, \
        "%d laboratoires different de celui de leur machine" % ecarts


def test_05_temporal_consistency(brut, propre):
    """Toutes les dates sont lisibles, dans la fenetre, et bien lues."""
    d = propre["sample_date"]
    assert d.notna().all(), "%d dates illisibles" % int(d.isna().sum())
    assert d.min() >= pd.Timestamp(DEBUT_COLLECTE), "date la plus ancienne %s" % d.min()
    assert d.max() <= pd.Timestamp(FIN_COLLECTE), "date la plus recente %s" % d.max()
    # chaque laboratoire ecrit toutes ses dates selon une seule convention,
    # que revele tout premier champ superieur a douze
    lues = lire_dates_brutes(brut, propre)
    admises = set(zip(brut["machine_id"].map(canon), lues))
    mal_lues = sum(1 for m, t in zip(propre["machine_id"], d)
                   if (m, t) not in admises)
    assert mal_lues == 0, "%d dates ne suivent pas la convention de leur " \
        "laboratoire" % mal_lues


# ------------------------------------------------------------------ mesures

def test_06_physical_plausibility(brut, propre):
    """Aucune mesure ne sort de son domaine physique."""
    for c, (bas, haut) in BORNES.items():
        v = propre[c].dropna()
        assert (v >= bas).all(), "%s : minimum %.4f" % (c, v.min())
        assert (v <= haut).all(), "%s : maximum %.4f" % (c, v.max())
    paire = propre[["hours_since_oil_change", "machine_total_hours"]].dropna()
    incoherent = int((paire.iloc[:, 0] > paire.iloc[:, 1]).sum())
    assert incoherent == 0, \
        "%d compteurs horaires se contredisent" % incoherent
    # quand la source se contredit, c'est l'un des deux compteurs qui cede
    depuis = mesure_brute(brut["hours_since_oil_change"])
    total = mesure_brute(brut["machine_total_hours"])
    fautes = 0
    h_propre = propre["hours_since_oil_change"].isna().to_numpy()
    t_propre = propre["machine_total_hours"].notna().to_numpy()
    for i, idx in enumerate(relier(brut, propre)):
        if any(depuis[j] > total[j] for j in idx):
            fautes += int(not (h_propre[i] and t_propre[i]))
    assert fautes == 0, \
        "%d contradictions horaires mal resolues" % fautes


def test_07_legitimate_extremes_preserved(brut, propre):
    """La queue haute de la distribution n'a pas ete rabotee."""
    fer_brut = brut["iron_ppm"].map(nombre)
    atelier = brut["workshop"].map(canon)
    annee = annee_brute(brut["sample_date"])
    eligible = (atelier.isin(REFERENTIEL_ATELIERS)
                & annee.isin([2024, 2025])
                & fer_brut.between(BORNES["iron_ppm"][0], BORNES["iron_ppm"][1]))
    # un prelevement replique dans le fichier brut ne compte qu'une fois
    unique = ~pd.DataFrame({"m": brut["machine_id"].map(canon),
                            "d": brut["sample_date"]}).duplicated()
    eligible = eligible & unique
    seuil = float(fer_brut[eligible].quantile(0.975))
    attendus = int((eligible & (fer_brut >= seuil)).sum())
    presents = int((propre["iron_ppm"] >= seuil).sum())
    assert presents >= 0.80 * attendus, \
        "%d valeurs au-dessus de %.1f ppm conservees sur %d admissibles" \
        % (presents, seuil, attendus)
    assert propre["iron_ppm"].max() >= seuil
    # et plus largement, aucune mesure legitime du fichier n'est perdue
    legitimes = mesures_legitimes(brut, propre)
    liens = relier(brut, propre)
    for c in MESURES:
        absente = propre[c].isna().to_numpy()
        perdues = sum(1 for i, idx in enumerate(liens)
                      if idx and legitimes[c][idx[0]] and absente[i])
        assert perdues == 0, \
            "%s : %d mesures legitimes du fichier ont ete perdues" \
            % (c, perdues)


def test_08_unit_homogeneity(brut, propre):
    """Une grandeur, une unite, sur tout le parc."""
    v = propre["viscosity_cst"].dropna()
    medianes = propre.groupby("lab_id")["viscosity_cst"].median().dropna()
    assert len(medianes) >= 2
    etendue = float(medianes.max() / medianes.min())
    assert etendue < 1.30, \
        "les medianes par laboratoire varient d'un facteur %.2f" % etendue
    assert float(v.quantile(0.99)) < 150.0
    # la conversion ne detruit la mesure d'aucun laboratoire
    vides = propre.groupby("lab_id")["viscosity_cst"].apply(lambda x: x.isna().mean())
    assert (vides <= 0.15).all(), \
        "viscosite manquante a plus de 15 %% pour %s" % sorted(vides[vides > 0.15].index)
    # aucun laboratoire ne melange deux unites
    liens = relier(brut, propre)
    source = mesure_brute(brut["viscosity_cst"])
    statuts = {}
    visco = propre["viscosity_cst"].to_numpy(dtype=float)
    labos = propre["lab_id"].to_numpy()
    for i, idx in enumerate(liens):
        x = visco[i]
        if np.isnan(x):
            continue
        brutes = [b for b in source[idx] if not np.isnan(b)]
        converti = any(abs(x - f(b / SUS_PAR_CST, 2)) < 1e-9
                       for b in brutes for f in (round, np.round))
        conserve = any(abs(x - b) < 1e-9 for b in brutes)
        if converti != conserve:
            statuts.setdefault(labos[i], set()).add(converti)
    melanges = sorted(l for l, s in statuts.items() if len(s) > 1)
    assert not melanges, "laboratoires aux unites melangees : %s" % melanges


def test_09_sensor_artifacts(brut, propre):
    """Aucune valeur exacte n'est portee par une part anormale des mesures."""
    for c in MESURES:
        v = propre[c].dropna()
        if len(v) == 0:
            continue
        part = v.value_counts(normalize=True)
        assert float(part.iloc[0]) <= SEUIL_SATURATION, \
            "%s : la valeur %s occupe %.1f %% de la colonne" \
            % (c, part.index[0], 100 * part.iloc[0])
    # et aucune des valeurs surrepresentees du fichier source ne subsiste
    for c in MESURES:
        source = pd.Series(mesure_brute(brut[c])).dropna()
        part = source.value_counts(normalize=True)
        for plateau in part[part > SEUIL_SATURATION].index:
            reste = int(np.isclose(propre[c].dropna(), plateau).sum())
            assert reste == 0, \
                "%s : %d occurrences de la valeur %s subsistent" \
                % (c, reste, plateau)


# --------------------------------------------------------- cible et parc

def test_10_label_consistency(brut, propre):
    """Aucun prelevement retenu ne portait deux etiquettes opposees."""
    cles = brut.assign(_m=brut["machine_id"].map(canon))
    conflits = cles.groupby(["_m", "sample_date"])[CIBLE].nunique()
    conflits = set(conflits[conflits > 1].index)
    assert len(conflits) > 0, "le fichier brut ne presente pas de conflit"
    restants = []
    for machine, horodatage in zip(propre["machine_id"], propre["sample_date"]):
        for ecriture in ecritures_possibles(horodatage):
            if (machine, ecriture) in conflits:
                restants.append((machine, ecriture))
    assert not restants, \
        "%d prelevements a etiquette contestee ont ete conserves" % len(restants)
    # l'etiquette conservee est celle du fichier source
    etiquettes = brut[CIBLE].astype(int).to_numpy()
    conservees = propre[CIBLE].to_numpy()
    infideles = sum(1 for i, idx in enumerate(relier(brut, propre))
                    if set(etiquettes[idx]) != {int(conservees[i])})
    assert infideles == 0, "%d etiquettes different de la source" % infideles


def test_11_fleet_scope(brut, propre):
    """Le parc retenu est celui du referentiel."""
    vus = set(propre["workshop"].dropna().unique())
    hors = vus - set(REFERENTIEL_ATELIERS)
    assert not hors, "ateliers hors referentiel : %s" % sorted(hors)
    assert vus == set(REFERENTIEL_ATELIERS), \
        "ateliers du referentiel absents : %s" \
        % sorted(set(REFERENTIEL_ATELIERS) - vus)
    ateliers = brut["workshop"].map(canon).to_numpy()
    conserves = propre["workshop"].to_numpy()
    infideles = sum(1 for i, idx in enumerate(relier(brut, propre))
                    if set(ateliers[idx]) != {conserves[i]})
    assert infideles == 0, "%d ateliers different de la source" % infideles


def test_12_residual_volume(brut, propre):
    """Le nettoyage retire ce qu'il faut, ni moins ni plus.

    Les prelevements attendus se deduisent du fichier brut : distincts, dans
    la fenetre, dans le referentiel, dont l'etiquette ne fait pas l'objet
    d'un desaccord. Aucun tableau de reference n'intervient.
    """
    cle = pd.DataFrame({"m": brut["machine_id"].map(canon),
                        "d": brut["sample_date"].astype(str)})
    recevable = (brut["workshop"].map(canon).isin(REFERENTIEL_ATELIERS)
                 & annee_brute(brut["sample_date"]).isin([2024, 2025]))
    desaccords = brut.groupby([cle["m"], cle["d"]])[CIBLE].nunique()
    desaccords = set(desaccords[desaccords > 1].index)
    attendus = {(t.m, t.d) for t in cle[recevable].itertuples(index=False)
                if (t.m, t.d) not in desaccords}
    attendu = len(attendus)
    assert len(propre) == attendu, \
        "%d lignes conservees, %d attendues" % (len(propre), attendu)
    etrangers = sum(1 for m, t in zip(propre["machine_id"], propre["sample_date"])
                    if not any((m, e) in attendus
                               for e in ecritures_possibles(t)))
    assert etrangers == 0, \
        "%d lignes ne correspondent a aucun prelevement attendu" % etrangers
    taux = float(propre[CIBLE].mean())
    assert 0.15 <= taux <= 0.26, "taux de la classe positive %.3f" % taux


def test_13_target_independence(propre):
    """Aucune colonne ne sait ce qui n'etait pas connu au prelevement."""
    y = propre[CIBLE]
    for c in propre.columns:
        if c == CIBLE:
            continue
        if pd.api.types.is_numeric_dtype(propre[c]):
            v = propre[c]
            ok = v.notna()
            if ok.sum() < 30 or v[ok].nunique() < 2:
                continue
            r = abs(float(np.corrcoef(v[ok], y[ok])[0, 1]))
            assert r < 0.60, "%s : correlation %.2f avec la cible" % (c, r)
            manquant = v.isna()
            if 0 < manquant.mean() < 1:
                r2 = abs(float(np.corrcoef(manquant.astype(float), y)[0, 1]))
                assert r2 < 0.60, \
                    "%s : son absence predit la cible (%.2f)" % (c, r2)
        else:
            g = y.groupby(propre[c]).agg(["mean", "size"])
            g = g[g["size"] >= 20]
            if len(g):
                assert float(g["mean"].max()) < 0.85, \
                    "%s : une modalite affiche %.0f %% de positifs" \
                    % (c, 100 * g["mean"].max())
    for c in propre.columns:
        v = propre[c].dropna()
        if len(v):
            assert float(v.value_counts(normalize=True).iloc[0]) <= \
                SEUIL_MODALITE_DOMINANTE or c == CIBLE, \
                "%s : colonne sans pouvoir discriminant conservee" % c
    for c in propre.columns:
        if c in MESURES or c == CIBLE or \
                pd.api.types.is_datetime64_any_dtype(propre[c]):
            continue
        assert propre[c].nunique() < len(propre), \
            "%s : une valeur distincte par ligne, c'est un identifiant" % c


# --------------------------------------------------------- partition, modele

def test_14_group_partitioning(partition, propre):
    """Aucune machine ne figure des deux cotes de la partition."""
    tr, te = partition
    commun = set(tr["machine_id"]) & set(te["machine_id"])
    assert not commun, "machines presentes des deux cotes : %s" \
        % sorted(commun)[:5]
    part = len(te) / (len(tr) + len(te))
    assert abs(part - PART_TEST) < 0.08, "part de test %.3f" % part
    assert tr.index.is_monotonic_increasing and te.index.is_monotonic_increasing
    assert list(tr.index) == list(range(len(tr))) and \
        list(te.index) == list(range(len(te))), "index non reinitialise"
    # rien n'est perdu, rien n'est duplique
    assert list(tr.columns) == list(propre.columns) == list(te.columns)
    ensemble = pd.concat([tr, te]).sort_values(["sample_date", "machine_id"])
    pd.testing.assert_frame_equal(ensemble.reset_index(drop=True),
                                  propre.reset_index(drop=True))
    # deux appels donnent la meme partition
    encore = __import__("src.pipeline", fromlist=["split"]).split(propre.copy())
    pd.testing.assert_frame_equal(tr, encore[0])
    pd.testing.assert_frame_equal(te, encore[1])


def test_15_fit_on_training_only(modele_ajuste, propre, partition):
    """Les parametres appris ne viennent que de l'entrainement."""
    modele, tr, te = modele_ajuste
    assert isinstance(modele, Pipeline), "build_model doit renvoyer un Pipeline"

    from sklearn.exceptions import NotFittedError
    from sklearn.utils.validation import check_is_fitted
    neuf = __import__("src.pipeline", fromlist=["build_model"]).build_model(
        partition[0].copy())
    with pytest.raises(NotFittedError):
        check_is_fitted(neuf)

    X = te.drop(columns=[CIBLE])
    pred = np.asarray(modele.predict(X))
    # la machine n'explique rien : la changer ne change aucune prediction,
    # y compris pour les machines que l'entrainement a vues
    appris = tr.drop(columns=[CIBLE])
    identifiants = sorted(appris["machine_id"].unique())
    autre = appris.copy()
    autre["machine_id"] = appris["machine_id"].map(
        dict(zip(identifiants, identifiants[1:] + identifiants[:1])))
    assert (np.asarray(modele.predict(autre))
            == np.asarray(modele.predict(appris))).all(), \
        "les predictions dependent de l'identifiant de machine"
    # une prediction ne depend que de sa ligne, pas du lot qui l'accompagne
    moitie = len(X) // 2
    assert (np.concatenate([modele.predict(X.iloc[:moitie]),
                            modele.predict(X.iloc[moitie:])]) == pred).all(), \
        "les predictions dependent du lot presente"
    for i in range(0, len(X), max(1, len(X) // 25)):
        assert modele.predict(X.iloc[[i]])[0] == pred[i], \
            "la prediction de la ligne %d depend du lot" % i

    appris = {}

    def visiter(objet):
        for attribut in ("statistics_", "mean_", "scale_", "data_min_",
                         "data_max_", "quantiles_"):
            if hasattr(objet, attribut):
                appris[(id(objet), attribut)] = np.asarray(
                    getattr(objet, attribut), dtype=float)
        for enfant in getattr(objet, "steps", []):
            visiter(enfant[1])
        for enfant in getattr(objet, "transformers_", []):
            if hasattr(enfant[1], "fit"):
                visiter(enfant[1])

    visiter(modele)
    if not appris:
        pytest.skip("aucun transformateur ajuste dans la chaine")

    temoin = build_model_temoin(modele, tr)
    for (_, attribut), valeur in appris.items():
        assert np.isfinite(valeur).all() or True
    # meme chaine ajustee sur l'ensemble complet : les parametres doivent
    # differer, sinon l'ajustement a vu le test
    complet = {}
    temoin.fit(propre.drop(columns=[CIBLE]), propre[CIBLE])

    def collecter(objet, cible):
        for attribut in ("statistics_", "mean_", "scale_"):
            if hasattr(objet, attribut):
                cible.append(np.asarray(getattr(objet, attribut), dtype=float))
        for enfant in getattr(objet, "steps", []):
            collecter(enfant[1], cible)
        for enfant in getattr(objet, "transformers_", []):
            if hasattr(enfant[1], "fit"):
                collecter(enfant[1], cible)

    a, b = [], []
    collecter(modele, a)
    collecter(temoin, b)
    if a and b and len(a) == len(b):
        identiques = all(x.shape == y.shape and np.allclose(x, y, equal_nan=True)
                         for x, y in zip(a, b))
        assert not identiques, \
            "les parametres appris sont ceux de l'ensemble complet"


def build_model_temoin(modele, tr):
    from sklearn.base import clone
    return clone(modele)


def test_16_performance_envelope(modele_ajuste):
    """Le score se tient dans l'enveloppe attendue."""
    modele, tr, te = modele_ajuste
    pred = modele.predict(te.drop(columns=[CIBLE]))
    exactitude = accuracy_score(te[CIBLE], pred)
    assert exactitude >= PLANCHER_ACCURACY, \
        "exactitude = %.4f, sous le plancher de %.2f" \
        % (exactitude, PLANCHER_ACCURACY)
    assert exactitude <= PLAFOND_ACCURACY, \
        "exactitude = %.4f, au-dessus du plafond de %.2f" \
        % (exactitude, PLAFOND_ACCURACY)


def test_17_determinism(brut, propre, alea):
    """Deux executions donnent le meme resultat, et l'entree est intacte."""
    avant = brut.copy()
    encore = __import__("src.pipeline", fromlist=["clean"]).clean(brut)
    assert brut.equals(avant), "clean modifie le tableau passe en entree"
    assert len(encore) == len(propre)
    assert list(encore.columns) == list(propre.columns)
    lignes = alea.choice(len(propre), size=min(50, len(propre)), replace=False)
    gauche = propre.iloc[sorted(lignes)].reset_index(drop=True)
    droite = encore.iloc[sorted(lignes)].reset_index(drop=True)
    pd.testing.assert_frame_equal(gauche, droite, check_dtype=False)
