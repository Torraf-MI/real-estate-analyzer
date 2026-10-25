"""Indicatori di redditività e rischio: rendimenti, cap rate, VAN, TIR, DSCR, prezzo massimo."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy_financial as npf
import pandas as pd

from .flussi import costo_iniziale, proiezione
from .modello import Investimento


def van(flussi: pd.Series | np.ndarray, tasso: float) -> float:
    """Valore attuale netto, con il primo flusso all'anno 0."""
    return float(npf.npv(tasso, np.asarray(flussi, dtype=float)))


def tir(flussi: pd.Series | np.ndarray) -> float:
    """Tasso interno di rendimento (``nan`` se non esiste)."""
    valore = npf.irr(np.asarray(flussi, dtype=float))
    return float(valore) if valore is not None else float("nan")


def anno_recupero(flussi: pd.Series) -> float:
    """Primo anno in cui il flusso cumulato torna positivo (``nan`` se non accade)."""
    cumulato = flussi.cumsum()
    positivi = cumulato[cumulato >= 0]
    positivi = positivi[positivi.index > 0]
    return float(positivi.index[0]) if len(positivi) else float("nan")


def valore_dcf(inv: Investimento, tasso: float | None = None) -> float:
    """Valore attuale dei flussi senza leva (redditi netti e vendita) al tasso richiesto.

    È quanto l'investitore potrebbe spendere in tutto, oneri compresi, pagando in contanti e
    ottenendo esattamente il rendimento richiesto.
    """
    r = inv.scenario.tasso_sconto if tasso is None else tasso
    flussi = proiezione(inv)["Flusso senza leva"]
    return van(np.r_[0.0, flussi.iloc[1:]], r)


def con_prezzo(inv: Investimento, prezzo: float) -> Investimento:
    """Stesso immobile pagato un prezzo diverso: il valore di mercato resta quello originale."""
    return inv.con(acquisto__prezzo=prezzo, acquisto__valore_mercato=inv.acquisto.valore_iniziale)


def _bisezione(f: Callable[[float], float], basso: float, alto: float, tol: float = 1e-6) -> float:
    """Radice di una funzione decrescente in [basso, alto], ``nan`` se non è compresa."""
    f_basso, f_alto = f(basso), f(alto)
    if f_basso < 0 or f_alto > 0:
        return float("nan")
    for _ in range(200):
        medio = (basso + alto) / 2
        if f(medio) > 0:
            basso = medio
        else:
            alto = medio
        if alto - basso < tol * max(1.0, abs(medio)):
            break
    return (basso + alto) / 2


def prezzo_massimo(inv: Investimento, tasso: float | None = None) -> float:
    """Prezzo d'acquisto oltre il quale il VAN del capitale proprio diventa negativo.

    Imposte, provvigioni e mutuo vengono ricalcolati sul nuovo prezzo, mentre il valore di mercato
    dell'immobile resta invariato.
    """
    r = inv.scenario.tasso_sconto if tasso is None else tasso

    def f(p: float) -> float:
        return van(proiezione(con_prezzo(inv, p))["Flusso netto"], r)

    return _bisezione(f, 1.0, inv.acquisto.prezzo * 3)


def occupazione_pareggio(inv: Investimento) -> float:
    """Quota dell'anno in cui l'immobile deve essere affittato perché il flusso del primo anno sia nullo.

    Un valore sopra il 100% indica che il flusso è negativo anche senza sfitto.
    """

    def f(occ: float) -> float:
        return proiezione(inv.con(locazione__sfitto=1 - occ))["Flusso netto"].iat[1]

    valore = _bisezione(lambda o: -f(o), 0.0, 1.0)
    if np.isnan(valore) and f(1.0) < 0:
        return float("inf")
    return 0.0 if np.isnan(valore) else valore


def calcola(inv: Investimento, flussi: pd.DataFrame | None = None) -> dict[str, float]:
    """Tutti gli indicatori principali dell'investimento."""
    df = proiezione(inv) if flussi is None else flussi
    costo = costo_iniziale(inv)
    r = inv.scenario.tasso_sconto
    anno1 = df.loc[1]
    con_rata = df.loc[1:][df.loc[1:, "Rata"] > 0]
    netto = df["Flusso netto"]
    guadagni = netto.iloc[1:].sum()
    return {
        "Costo complessivo": costo.totale,
        "Capitale proprio": costo.capitale_proprio,
        "Importo mutuo": costo.importo_mutuo,
        "Rendimento lordo": anno1["Canone potenziale"] / inv.acquisto.prezzo,
        "Rendimento netto": (anno1["NOI"] - anno1["Imposte sul reddito"]) / costo.costo_immobile,
        "Cap rate": anno1["NOI"] / inv.acquisto.valore_iniziale,
        "Cash-on-cash": anno1["Flusso netto"] / costo.capitale_proprio,
        "DSCR minimo": float((con_rata["NOI"] / con_rata["Rata"]).min()) if len(con_rata) else float("nan"),
        "VAN": van(netto, r),
        "TIR": tir(netto),
        "TIR senza leva": tir(df["Flusso senza leva"]),
        "Moltiplicatore del capitale": guadagni / costo.capitale_proprio,
        "Anno di recupero": anno_recupero(netto),
        "Valore DCF": valore_dcf(inv),
        "Prezzo massimo": prezzo_massimo(inv),
        "Occupazione di pareggio": occupazione_pareggio(inv),
    }
