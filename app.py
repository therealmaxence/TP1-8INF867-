# -*- coding: utf-8 -*-
"""8INF867 - TP1 - Point d'entree. Fourni, ne pas modifier.

    python app.py

Charge le fichier brut, applique votre nettoyage, partitionne, entraine
votre modele et affiche le score. Ce fichier est reecrit a l'identique
avant la correction : toute modification que vous y apporteriez serait sans
effet sur votre note.
"""
import sys

import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix)

from src.annexe import (CHEMIN_DONNEES, CIBLE, PLAFOND_ACCURACY,
                        PLANCHER_ACCURACY)
from src.pipeline import build_model, clean, split


def load_raw(chemin=CHEMIN_DONNEES):
    """Lecture stricte : tout reste en texte, rien n'est interprete."""
    return pd.read_csv(chemin, dtype=str, keep_default_na=False)


def report_score(modele, test):
    y = test[CIBLE]
    pred = modele.predict(test.drop(columns=[CIBLE]))
    exactitude = accuracy_score(y, pred)
    print(classification_report(y, pred, digits=3, zero_division=0))
    print("matrice de confusion")
    print(confusion_matrix(y, pred))
    print()
    print("exactitude (accuracy) : %.4f" % exactitude)
    print("enveloppe attendue    : %.2f a %.2f"
          % (PLANCHER_ACCURACY, PLAFOND_ACCURACY))
    if exactitude < PLANCHER_ACCURACY:
        print("-> sous le plancher : la chaine perd du signal.")
    elif exactitude > PLAFOND_ACCURACY:
        print("-> au-dessus du plafond : une information posterieure au"
              " prelevement subsiste.")
    else:
        print("-> dans l'enveloppe.")
    return exactitude


def main():
    brut = load_raw()
    print("brut   : %d lignes, %d colonnes" % brut.shape)

    propre = clean(brut)
    print("propre : %d lignes, %d colonnes" % propre.shape)
    print("colonnes conservees :", list(propre.columns))
    print()

    entrainement, test = split(propre)
    print("entrainement : %d lignes, %d machines"
          % (len(entrainement), entrainement["machine_id"].nunique()))
    print("test         : %d lignes, %d machines"
          % (len(test), test["machine_id"].nunique()))
    print()

    modele = build_model(entrainement)
    modele.fit(entrainement.drop(columns=[CIBLE]), entrainement[CIBLE])
    return report_score(modele, test)


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as e:
        print("Fonction non implementee :", e)
        sys.exit(1)
