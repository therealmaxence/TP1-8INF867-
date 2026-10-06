# -*- coding: utf-8 -*-
"""Annexe technique du TP1. Constantes publiques du reglement.

Ce fichier fait partie de l'enonce : il ne contient aucune information sur
les defauts presents dans le jeu de donnees, seulement les conventions du
domaine et les seuils cites par le reglement R1 a R17.

Ne pas modifier : les tests s'appuient dessus.
"""

# --- R2 : jetons designant une absence de valeur. Tous ne sont pas presents
#          dans le fichier ; la liste est celle du systeme d'acquisition.
SENTINELLES = {"-999", "9999", "N/A", "NA", "INCONNU", "-", "?", ""}

# --- Dictionnaire des colonnes de mesure
MESURES = [
    "hours_since_oil_change",   # heures de service depuis la derniere vidange
    "machine_total_hours",      # heures de service cumulees de la machine
    "iron_ppm",                 # fer, usure des pieces mobiles
    "copper_ppm",               # cuivre, usure des coussinets
    "lead_ppm",                 # plomb, usure des paliers
    "silicon_ppm",              # silicium, contamination par poussiere
    "viscosity_cst",            # viscosite cinematique a 40 degres
    "water_content_pct",        # teneur en eau
    "oxidation_index",          # indice d'oxydation de l'huile
]

# --- R7 : intervalles physiquement admissibles
BORNES = {
    "hours_since_oil_change": (0.0, 20000.0),
    "machine_total_hours": (0.0, 200000.0),
    "iron_ppm": (0.0, 2000.0),
    "copper_ppm": (0.0, 1000.0),
    "lead_ppm": (0.0, 1000.0),
    "silicon_ppm": (0.0, 1000.0),
    "viscosity_cst": (1e-9, 200.0),
    "water_content_pct": (0.0, 5.0),
    "oxidation_index": (0.0, 20.0),
}

# --- R11 : referentiel des ateliers en exploitation
REFERENTIEL_ATELIERS = ["AT-01", "AT-02", "AT-03", "AT-04", "AT-05"]

# --- R10 : fenetre de collecte
DEBUT_COLLECTE = "2024-01-01"
FIN_COLLECTE = "2025-12-31"

# --- R6 : conversion Saybolt Universal Seconds vers centistokes
SUS_PAR_CST = 4.635
SEUIL_VISCOSITE_SUS = 150.0     # mediane au-dela de laquelle un laboratoire
                                # rapporte en SUS

# --- R9 : part au-dela de laquelle une valeur exacte repetee est un artefact
SEUIL_SATURATION = 0.02

# --- R14 : part au-dela de laquelle une modalite rend sa colonne inutile
SEUIL_MODALITE_DOMINANTE = 0.99

# --- R12 / R13 : cle metier d'un prelevement
CLE_METIER = ["machine_id", "sample_date"]

# --- R17 : partition
SEED_PARTITION = 42
PART_TEST = 0.25

# --- Cible
CIBLE = "alert"

# --- Enveloppe de performance attendue (exactitude sur l'ensemble de test).
#     Le plancher est au-dessus de la part de la classe majoritaire (environ
#     0.79) : un modele qui ne predit jamais l'alerte n'est pas dans l'enveloppe.
PLANCHER_ACCURACY = 0.82
PLAFOND_ACCURACY = 0.92

CHEMIN_DONNEES = "data/oil_samples.csv"
