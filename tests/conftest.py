# -*- coding: utf-8 -*-
"""Fixtures de la suite publique.

Les tests ne comparent jamais votre resultat a un tableau de reference : ils
verifient des proprietes, calculees soit sur votre tableau, soit directement
sur le fichier brut. Ils ne vous diront donc pas quoi corriger, seulement
qu'une propriete attendue n'est pas satisfaite.
"""
import re
import unicodedata

import numpy as np
import pandas as pd
import pytest

from src.annexe import (BORNES, CHEMIN_DONNEES, CIBLE, MESURES, SENTINELLES,
                        SEUIL_SATURATION, SEUIL_VISCOSITE_SUS, SUS_PAR_CST)


# ------------------------------------------------------------- utilitaires

def canon(s):
    """Canonisation d'un identifiant textuel, au sens de R3."""
    t = "".join(c for c in unicodedata.normalize("NFD", str(s).strip())
                if unicodedata.category(c) != "Mn").upper()
    t = re.sub(r"[^A-Z0-9]", "", t)
    m = re.match(r"^([A-Z]+)(\d+)$", t) or re.match(r"^([A-Z]+)([A-Z])$", t)
    return "%s-%s" % (m.group(1), m.group(2)) if m else t


def nombre(s):
    """Lecture d'un nombre ecrit a la francaise, au sens de R1."""
    t = str(s).replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return np.nan


def annee_brute(serie):
    """Annee d'une date brute, lisible quel que soit l'ordre des champs."""
    return pd.to_numeric(serie.astype(str).str.slice(-4), errors="coerce")


def ecritures_possibles(horodatage):
    """Les deux ecritures possibles d'une date, sans prejuger du format."""
    return {horodatage.strftime("%d/%m/%Y"), horodatage.strftime("%m/%d/%Y")}


def lire_dates_brutes(brut, propre):
    """Dates du fichier brut, lues selon la convention de chaque laboratoire.

    Un laboratoire dont au moins une date porte un premier champ superieur a
    douze ecrit en jour-mois, les autres en mois-jour. Le laboratoire d'une
    machine est celui que porte `propre`.
    """
    labo = brut["machine_id"].map(canon).map(
        propre.drop_duplicates("machine_id").set_index("machine_id")["lab_id"])
    champs = brut["sample_date"].str.extract(r"^(\d+)/(\d+)/(\d+)$").astype(float)
    jour_mois = ((champs[0] > 12).groupby(labo).transform("max")
                 .fillna(False).astype(bool))
    return pd.to_datetime({"year": champs[2],
                           "month": champs[1].where(jour_mois, champs[0]),
                           "day": champs[0].where(jour_mois, champs[1])},
                          errors="coerce")


def relier(brut, propre):
    """Pour chaque ligne de `propre`, les indices des lignes brutes qui la
    fondent : meme machine canonisee, meme date une fois lue.
    """
    lues = lire_dates_brutes(brut, propre)
    index = {}
    for i, cle in enumerate(zip(brut["machine_id"].map(canon), lues)):
        index.setdefault(cle, []).append(i)
    return [index.get(cle, []) for cle in zip(propre["machine_id"],
                                              propre["sample_date"])]


def est_absent(cellule):
    """Vrai si la cellule brute designe une absence au sens de R2."""
    return str(cellule).strip().upper() in SENTINELLES


def mesure_brute(serie):
    """Lecture d'une colonne de mesure brute, absences comprises (R1, R2).

    Renvoie un tableau numpy : les jetons d'absence, y compris ecrits sous une
    forme numerique equivalente, valent NaN.
    """
    jetons = []
    for j in SENTINELLES:
        try:
            jetons.append(float(j))
        except ValueError:
            pass
    v = np.array([np.nan if est_absent(x) else nombre(x) for x in serie],
                 dtype=float)
    return np.where(np.isin(v, jetons), np.nan, v)


def mesures_legitimes(brut, propre):
    """Pour chaque colonne de mesure, les cellules du fichier brut qui n'ont
    aucune raison d'etre supprimees : lisibles, converties d'unite si leur
    laboratoire rapporte en SUS, dans leur domaine physique, coherentes entre
    compteurs et non portees par une valeur de saturation.

    Renvoie {colonne: tableau de booleens, une valeur par ligne brute}.
    """
    labo = brut["machine_id"].map(canon).map(
        propre.drop_duplicates("machine_id").set_index("machine_id")["lab_id"])
    valeurs = {c: pd.Series(mesure_brute(brut[c]), index=brut.index)
               for c in MESURES}
    visc = valeurs["viscosity_cst"]
    mediane = labo.map(visc.groupby(labo).median())
    valeurs["viscosity_cst"] = visc.where(~(mediane > SEUIL_VISCOSITE_SUS),
                                          (visc / SUS_PAR_CST).round(2))
    legitimes = {}
    for c in MESURES:
        v = valeurs[c]
        v = v.where(v.between(*BORNES[c]))
        legitimes[c] = v
    contradiction = (legitimes["hours_since_oil_change"]
                     > legitimes["machine_total_hours"])
    legitimes["hours_since_oil_change"] = legitimes[
        "hours_since_oil_change"].where(~contradiction)
    sortie = {}
    for c, v in legitimes.items():
        part = v.value_counts(normalize=True)
        sortie[c] = (v.notna() & ~v.isin(part[part > SEUIL_SATURATION].index)
                     ).to_numpy()
    return sortie


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="session")
def brut():
    return pd.read_csv(CHEMIN_DONNEES, dtype=str, keep_default_na=False)


@pytest.fixture(scope="session")
def propre(brut):
    from src.pipeline import clean
    df = clean(brut.copy())
    assert isinstance(df, pd.DataFrame), "clean doit renvoyer un DataFrame"
    assert len(df) > 0, "clean renvoie un tableau vide"
    return df


@pytest.fixture(scope="session")
def partition(propre):
    from src.pipeline import split
    tr, te = split(propre.copy())
    return tr, te


@pytest.fixture(scope="session")
def modele_ajuste(partition):
    tr, te = partition
    from src.pipeline import build_model
    m = build_model(tr.copy())
    m.fit(tr.drop(columns=[CIBLE]), tr[CIBLE])
    return m, tr, te


@pytest.fixture
def alea():
    return np.random.default_rng(20261022)


# ------------------------------------------------------------------- note

# Points par test, sur 100. Les douze tests de nettoyage valent 5 points, les
# cinq tests de modelisation et d'hygiene valent 8 points. Un test non execute
# vaut zero.
POIDS = {"test_%02d" % i: 5 for i in range(1, 13)}
POIDS.update({"test_%02d" % i: 8 for i in range(13, 18)})


def _numero(rapport):
    m = re.search(r"::(test_\d\d)_", rapport.nodeid)
    return m.group(1) if m else None


def _afficher_note(config):
    tr = config.pluginmanager.get_plugin("terminalreporter")
    reussis, rates = set(), set()
    for rep in tr.stats.get("passed", []):
        if rep.when == "call":
            reussis.add(_numero(rep))
    for cle in ("failed", "error"):
        for rep in tr.stats.get(cle, []):
            rates.add(_numero(rep))
    reussis = (reussis - rates) & set(POIDS)
    note = sum(POIDS[t] for t in reussis)
    total = sum(POIDS.values())
    tr.write_sep("=", "NOTE", bold=True)
    for t in sorted(set(POIDS) - reussis):
        tr.write_line("  %s : 0 / %d" % (t, POIDS[t]))
    tr.write_line("Tests reussis : %d / %d" % (len(reussis), len(POIDS)))
    tr.write_line("Note : %d / %d" % (note, total), bold=True)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Imprime la note apres le bilan de pytest, donc en toute derniere ligne."""
    resultat = yield
    try:
        _afficher_note(session.config)
    except Exception as e:  # la note ne doit jamais masquer le resultat des tests
        print("Note non calculee : %r" % (e,))
    return resultat
