# -*- coding: utf-8 -*-
"""8INF867 - TP1 - Chaine de traitement a completer.

Ce fichier est le point d'entree de la correction. Vous pouvez y ecrire tout
votre code ou le repartir dans d'autres modules et dossiers de votre depot
(importes depuis la racine, par exemple `from src.outils import ...`), pourvu
que `pytest tests/` s'execute depuis la racine sans autre manipulation et
sans dependance absente de `requirements.txt`.

Les trois fonctions ci-dessous constituent le contrat d'interface. Leurs
noms, leurs signatures et la nature de ce qu'elles renvoient sont imposes.
`app.py` et la suite de tests s'appuient dessus et ne doivent pas etre
modifies.

Rappel de la frontiere posee par R16 : `clean` ne fait que des operations
decidables ligne par ligne, plus les suppressions de lignes et de colonnes
prevues par le reglement. Toute operation qui estime un parametre sur une
population (imputation, mise a l'echelle, encodage) appartient au `Pipeline`
retourne par `build_model`, que scikit-learn ajustera sur le seul ensemble
d'entrainement.
"""
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.annexe import (BORNES, CIBLE, CLE_METIER, DEBUT_COLLECTE,
                        FIN_COLLECTE, MESURES, PART_TEST,
                        REFERENTIEL_ATELIERS, SEED_PARTITION, SENTINELLES,
                        SEUIL_MODALITE_DOMINANTE, SEUIL_SATURATION,
                        SEUIL_VISCOSITE_SUS, SUS_PAR_CST)


def clean(brut):
    """Applique le reglement R1 a R15 au tableau brut.

    Parametres
    ----------
    brut : pandas.DataFrame
        Le fichier tel que charge par `app.load_raw`, toutes colonnes en
        texte, aucune valeur manquante interpretee.

    Retour
    ------
    pandas.DataFrame
        Tableau nettoye, trie par date puis par machine, index reinitialise.
        Les colonnes de mesure sont de type flottant, `sample_date` est de
        type datetime, `alert` est de type entier.

    Le tableau passe en entree ne doit pas etre modifie sur place.
    """
    raise NotImplementedError("R1 a R15")


def split(propre):
    """Partitionne le tableau nettoye selon R17.

    Retour
    ------
    (pandas.DataFrame, pandas.DataFrame)
        Entrainement et test, index reinitialises. Aucune machine ne doit
        figurer dans les deux ensembles.
    """
    raise NotImplementedError("R17")


def build_model(entrainement):
    """Construit la chaine de modelisation, non ajustee.

    Parametres
    ----------
    entrainement : pandas.DataFrame
        L'ensemble d'entrainement, colonne cible comprise. Il sert a
        determiner quelles colonnes traiter, pas a calculer des statistiques.

    Retour
    ------
    sklearn.pipeline.Pipeline
        Chaine acceptant en entree un tableau de la meme forme que celui
        renvoye par `clean`, prive de la colonne cible. Elle doit contenir
        toutes les operations qui estiment un parametre sur la population.
        Le classifieur final est libre parmi ceux vus en cours.
    """
    raise NotImplementedError("R16")
