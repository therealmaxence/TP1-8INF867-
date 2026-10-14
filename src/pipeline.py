# -*- coding: utf-8 -*-
import re
import unicodedata
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.annexe import (BORNES, CIBLE, CLE_METIER, DEBUT_COLLECTE,
                        FIN_COLLECTE, MESURES, PART_TEST,
                        REFERENTIEL_ATELIERS, SEED_PARTITION, SENTINELLES,
                        SEUIL_MODALITE_DOMINANTE, SEUIL_SATURATION,
                        SEUIL_VISCOSITE_SUS, SUS_PAR_CST)


# --- Fonctions utilitaires ---

def _canon(s):
    """Normalise les identifiants"""
    t = "".join(c for c in unicodedata.normalize("NFD", str(s).strip())
                if unicodedata.category(c) != "Mn").upper()
    t = re.sub(r"[^A-Z0-9]", "", t)
    m = re.match(r"^([A-Z]+)(\d+)$", t) or re.match(r"^([A-Z]+)([A-Z])$", t)
    return "%s-%s" % (m.group(1), m.group(2)) if m else t


def _nombre(s):
    """Convertit une chaîne en float"""
    t = str(s).replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return np.nan


def _jetons_numeriques():
    """Extrait les valeurssentinelles convertibles en float (-999, 9999)."""
    jetons = []
    for j in SENTINELLES:
        try:
            jetons.append(float(j))
        except ValueError:
            pass
    return jetons


# --- Nettoyage (R1 a R15) ---

def _harmoniser_identifiants(df):
    """Normalise les catégories et affecte le labo de chaque machine (R3, R4)."""
    df["machine_id"] = df["machine_id"].map(_canon)
    df["workshop"] = df["workshop"].map(_canon)

    # Reconstitution du labo : chaque machine est associée à son labo majoritaire
    est_absent = df["lab_id"].astype(str).str.strip().str.upper().isin(SENTINELLES)
    connu = df[~est_absent].copy()
    connu["lab_canon"] = connu["lab_id"].map(_canon)
    par_machine = connu.groupby("machine_id")["lab_canon"].agg(
        lambda s: s.value_counts().sort_index().idxmax()
    )
    df["lab_id"] = df["machine_id"].map(par_machine)
    return df


def _analyser_donnees_brutes(df):
    """Calcule les statistiques initiales sur le brut avant toute suppression (clause liminaire, R6, R9)."""
    jetons_num = _jetons_numeriques()
    mesures_lues = {}

    # Lecture des mesures et remplacement des sentinelles par NaN
    for c in MESURES:
        raw = df[c].map(lambda x: np.nan if str(x).strip().upper() in SENTINELLES else _nombre(x))
        mesures_lues[c] = raw.where(~raw.isin(jetons_num), np.nan)

    # R6 : un labo avec viscosité médiane > 150 rapporte en secondes Saybolt (SUS)
    visc_raw = mesures_lues["viscosity_cst"]
    lab_mediane = visc_raw.groupby(df["lab_id"]).median()
    labs_sus = set(lab_mediane[lab_mediane > SEUIL_VISCOSITE_SUS].index)

    # R9 : détection des plateaux de capteur (valeur répétée à plus de 2%)
    saturations = {}
    for c in MESURES:
        v = mesures_lues[c].dropna()
        part = v.value_counts(normalize=True)
        saturations[c] = set(part[part > SEUIL_SATURATION].index)

    return mesures_lues, labs_sus, saturations


def _convertir_dates(df):
    """Déduit le format de date (JJ/MM ou MM/JJ) par laboratoire et parse en datetime (R5)."""
    champs = df["sample_date"].str.extract(r"^(\d+)/(\d+)/(\d+)$").astype(float)
    # Si un premier champ dépasse 12, le labo écrit en JJ/MM, sinon en MM/JJ
    jour_mois = (champs[0] > 12).groupby(df["lab_id"]).transform("max").fillna(False).astype(bool)

    df["sample_date"] = pd.to_datetime({
        "year": champs[2],
        "month": champs[1].where(jour_mois, champs[0]),
        "day": champs[0].where(jour_mois, champs[1])
    }, errors="coerce")
    return df


def _nettoyer_mesures(df, mesures_lues, labs_sus, saturations):
    """Applique les conversions d'unités, les bornes physiques et les cohérences (R6, R7, R8, R9)."""
    for c in MESURES:
        val = mesures_lues[c].copy()

        # R6 : conversion SUS vers cSt (division par 4.635 arrondie à 2 décimales)
        if c == "viscosity_cst":
            val = val.where(~df["lab_id"].isin(labs_sus), (val / SUS_PAR_CST).round(2))

        # R7 : mise à NaN des valeurs hors bornes physiques (on ne supprime pas la ligne)
        bas, haut = BORNES[c]
        val = val.where(val.between(bas, haut), np.nan)

        # R9 : retrait des artefacts de saturation de capteur
        if c in saturations and len(saturations[c]) > 0:
            val = val.where(~mesures_lues[c].isin(saturations[c]), np.nan)

        df[c] = val

    # R8 : incohérence interne (heures depuis vidange <= total machine)
    incoherent = df["hours_since_oil_change"] > df["machine_total_hours"]
    df.loc[incoherent, "hours_since_oil_change"] = np.nan

    # Vérification d'éventuels plateaux résiduels après conversion
    for c in MESURES:
        part = df[c].dropna().value_counts(normalize=True)
        trop = set(part[part > SEUIL_SATURATION].index)
        if trop:
            df.loc[df[c].isin(trop), c] = np.nan

    return df


def _filtrer_lignes(df):
    """Filtre les dates, ateliers, et résout les doublons et conflits"""
    # R10 & R11 : dates dans la période (2024-2025) et ateliers du référentiel
    df = df[(df["sample_date"] >= pd.Timestamp(DEBUT_COLLECTE)) &
            (df["sample_date"] <= pd.Timestamp(FIN_COLLECTE))]
    df = df[df["workshop"].isin(REFERENTIEL_ATELIERS)].copy()

    # R12 : si un prélèvement a des alertes contradictoires, supprimer tout le groupe (avant R13)
    df["_alert_int"] = df[CIBLE].astype(int)
    conflits = df.groupby(["machine_id", "sample_date"])["_alert_int"].transform("nunique")
    df = df[conflits == 1].copy()

    # R13 : en cas de doublon, conserver celui avec le plus petit sample_id
    df["_sample_id_num"] = df["sample_id"].astype(float)
    df = df.sort_values("_sample_id_num").drop_duplicates(
        subset=["machine_id", "sample_date"], keep="first"
    )
    df = df.drop(columns=["_sample_id_num", "_alert_int"])
    return df


def _finaliser_tableau(df):
    """Conserve uniquement les colonnes autorisées, type et trie le tableau (R14, R15)."""
    # R14 : on retire les identifiants techniques, commentaires et coûts postérieurs
    cols_a_garder = ["machine_id", "workshop", "lab_id", "sample_date"] + MESURES + [CIBLE]
    df = df[cols_a_garder].copy()

    # R15 : typage et tri stable par date puis par machine
    for c in MESURES:
        df[c] = df[c].astype(float)
    df[CIBLE] = df[CIBLE].astype(int)

    return df.sort_values(["sample_date", "machine_id"], kind="stable").reset_index(drop=True)


# --- Fonctions principales ---

def clean(brut):
    """Applique le règlement de nettoyage R1 à R15 au DataFrame brut."""
    df = brut.copy()

    # 1. Normalisation catégorielle et imputation du laboratoire par machine
    df = _harmoniser_identifiants(df)

    # 2. Calculs statistiques liminaires sur le brut (SUS et saturations)
    mesures_lues, labs_sus, saturations = _analyser_donnees_brutes(df)

    # 3. Résolution des dates selon la convention de chaque labo
    df = _convertir_dates(df)

    # 4. Traitement physique des mesures
    df = _nettoyer_mesures(df, mesures_lues, labs_sus, saturations)

    # 5. Filtrage des lignes (fenêtre, ateliers, conflits R12, doublons R13)
    df = _filtrer_lignes(df)

    # 6. Sélection des colonnes utiles, typage et tri final
    return _finaliser_tableau(df)


def split(propre):
    """Partitionne le tableau en train/test par groupe de machine (R17)."""
    gss = GroupShuffleSplit(n_splits=1, test_size=PART_TEST, random_state=SEED_PARTITION)
    train_idx, test_idx = next(gss.split(propre, groups=propre["machine_id"]))

    tr = propre.iloc[train_idx].sort_values(["sample_date", "machine_id"], kind="stable").reset_index(drop=True)
    te = propre.iloc[test_idx].sort_values(["sample_date", "machine_id"], kind="stable").reset_index(drop=True)
    return tr, te


def build_model(entrainement):
    """Construit la chaîne scikit-learn non ajustée (R16)."""
    num_cols = [c for c in MESURES if c in entrainement.columns]
    cat_cols = [c for c in ["workshop", "lab_id"] if c in entrainement.columns]

    # Preprocessing : imputation médiane + standardisation pour les mesures, One-Hot pour les catégories
    # machine_id et sample_date sont exclus pour éviter tout biais (ex: overfitting)
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ],
        remainder="drop"
    )

    classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        random_state=42
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])
