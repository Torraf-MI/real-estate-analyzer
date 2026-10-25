"""Valutazione di investimenti immobiliari: flussi di cassa, mutuo, fiscalità italiana, VAN/TIR, sensitività."""

from .flussi import costo_iniziale, proiezione
from .metriche import calcola, prezzo_massimo, tir, valore_dcf, van
from .modello import Acquisto, Investimento, Locazione, Mutuo, Scenario, Spese, esempio_milano, load_toml
from .mutuo import piano_ammortamento, rata_mensile

__all__ = [
    "Acquisto",
    "Investimento",
    "Locazione",
    "Mutuo",
    "Scenario",
    "Spese",
    "calcola",
    "costo_iniziale",
    "esempio_milano",
    "load_toml",
    "piano_ammortamento",
    "prezzo_massimo",
    "proiezione",
    "rata_mensile",
    "tir",
    "valore_dcf",
    "van",
]

__version__ = "0.1.0"
