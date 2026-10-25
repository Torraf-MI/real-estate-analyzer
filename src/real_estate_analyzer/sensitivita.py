"""Analisi di sensitività: griglia prezzo × canone, tornado sulle ipotesi chiave, scenari a confronto."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .flussi import proiezione
from .metriche import calcola, con_prezzo, tir, van
from .modello import Investimento

VARIAZIONI = (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15)


def _metrica(inv: Investimento, nome: str) -> float:
    """TIR e VAN si calcolano dalla sola proiezione, molto più rapidamente di ``calcola``."""
    if nome == "TIR":
        return tir(proiezione(inv)["Flusso netto"])
    if nome == "VAN":
        return van(proiezione(inv)["Flusso netto"], inv.scenario.tasso_sconto)
    return calcola(inv)[nome]


def griglia(
    inv: Investimento,
    metrica: str = "TIR",
    variazioni_prezzo: Sequence[float] = VARIAZIONI,
    variazioni_canone: Sequence[float] = VARIAZIONI,
) -> pd.DataFrame:
    """Metrica al variare di prezzo d'acquisto (righe) e canone mensile (colonne)."""
    prezzi = [inv.acquisto.prezzo * (1 + v) for v in variazioni_prezzo]
    canoni = [inv.locazione.canone_mensile * (1 + v) for v in variazioni_canone]
    valori = [
        [_metrica(con_prezzo(inv, p).con(locazione__canone_mensile=c), metrica) for c in canoni]
        for p in prezzi
    ]
    return pd.DataFrame(valori, index=pd.Index(prezzi, name="Prezzo"), columns=pd.Index(canoni, name="Canone"))


@dataclass(frozen=True)
class Leva:
    """Ipotesi da far variare tra uno scenario sfavorevole e uno favorevole."""

    nome: str
    applica: Callable[[Investimento, float], Investimento]
    basso: float
    alto: float
    formato: str = "{:,.0f}"

    def etichetta(self, valore: float) -> str:
        return self.formato.format(valore).replace(",", "X").replace(".", ",").replace("X", ".")


def leve_standard(inv: Investimento) -> list[Leva]:
    a, loc, sp, m, sc = inv.acquisto, inv.locazione, inv.spese, inv.mutuo, inv.scenario

    def spese(i: Investimento, f: float) -> Investimento:
        return i.con(spese__condominio=sp.condominio * f, spese__manutenzione=sp.manutenzione * f,
                     spese__assicurazione=sp.assicurazione * f)

    leve = [
        Leva("Prezzo d'acquisto", con_prezzo, a.prezzo * 1.10, a.prezzo * 0.90, "€ {:,.0f}"),
        Leva("Canone mensile", lambda i, x: i.con(locazione__canone_mensile=x),
             loc.canone_mensile * 0.90, loc.canone_mensile * 1.10, "€ {:,.0f}"),
        Leva("Sfitto", lambda i, x: i.con(locazione__sfitto=x), max(loc.sfitto * 2.5, 0.10), 0.0, "{:.0%}"),
        Leva("Crescita annua del valore", lambda i, x: i.con(scenario__crescita_valore=x),
             sc.crescita_valore - 0.02, sc.crescita_valore + 0.02, "{:.1%}"),
        Leva("Crescita annua del canone", lambda i, x: i.con(locazione__crescita_canone=x),
             loc.crescita_canone - 0.015, loc.crescita_canone + 0.015, "{:.1%}"),
        Leva("Spese di gestione", spese, 1.3, 0.7, "{:.0%}"),
    ]
    if m.attivo:
        leve.append(Leva("Tasso del mutuo", lambda i, x: i.con(mutuo__tasso=x), m.tasso + 0.015,
                         max(m.tasso - 0.01, 0.0), "{:.1%}"))
    return leve


def tornado(inv: Investimento, metrica: str = "TIR", leve: list[Leva] | None = None) -> pd.DataFrame:
    """Effetto di ciascuna leva sulla metrica, ordinato dalla più influente."""
    base = _metrica(inv, metrica)
    righe = []
    for leva in leve or leve_standard(inv):
        basso = _metrica(leva.applica(inv, leva.basso), metrica)
        alto = _metrica(leva.applica(inv, leva.alto), metrica)
        righe.append(
            {
                "Ipotesi": leva.nome,
                "Valore sfavorevole": leva.etichetta(leva.basso),
                "Valore favorevole": leva.etichetta(leva.alto),
                "Sfavorevole": basso,
                "Favorevole": alto,
                "Ampiezza": abs(alto - basso),
            }
        )
    out = pd.DataFrame(righe).sort_values("Ampiezza", ascending=False).reset_index(drop=True)
    out.attrs["base"] = base
    out.attrs["metrica"] = metrica
    return out


def scenari_standard(inv: Investimento) -> dict[str, Investimento]:
    """Alternative tipiche da discutere con il cliente."""
    loc, m = inv.locazione, inv.mutuo
    altro_regime = "ordinario" if loc.regime == "cedolare" else "cedolare"
    scenari = {
        "Ipotesi base": inv,
        "Senza mutuo" if m.attivo else "Con mutuo al 60%": inv.con(mutuo__ltv=0.0 if m.attivo else 0.60),
        f"Regime {'IRPEF ordinario' if altro_regime == 'ordinario' else 'cedolare secca'}":
            inv.con(locazione__regime=altro_regime),
    }
    if not loc.canone_concordato:
        scenari["Canone concordato (−15%)"] = inv.con(locazione__canone_concordato=True,
                                                      locazione__canone_mensile=loc.canone_mensile * 0.85)
    scenari["Stress: sfitto 10%, valore fermo"] = inv.con(locazione__sfitto=0.10, scenario__crescita_valore=0.0)
    return scenari


INDICATORI_SCENARI = ("Capitale proprio", "Rendimento netto", "Cash-on-cash", "VAN", "TIR",
                      "Moltiplicatore del capitale")


def confronta_scenari(scenari: dict[str, Investimento],
                      indicatori: Sequence[str] = INDICATORI_SCENARI) -> pd.DataFrame:
    righe = {nome: calcola(i) for nome, i in scenari.items()}
    return pd.DataFrame(righe).T.loc[:, list(indicatori)]


def simulazione(inv: Investimento, n: int = 1_000, seed: int = 0) -> pd.Series:
    """Distribuzione del TIR con incertezza su canone, sfitto, crescita del valore e tassi (Monte Carlo)."""
    rng = np.random.default_rng(seed)
    loc, sc, m = inv.locazione, inv.scenario, inv.mutuo
    risultati = np.empty(n)
    for k in range(n):
        variante = inv.con(
            locazione__canone_mensile=loc.canone_mensile * rng.normal(1, 0.07),
            locazione__sfitto=float(np.clip(rng.normal(loc.sfitto, 0.03), 0, 0.5)),
            locazione__crescita_canone=rng.normal(loc.crescita_canone, 0.01),
            scenario__crescita_valore=rng.normal(sc.crescita_valore, 0.02),
            mutuo__tasso=max(rng.normal(m.tasso, 0.0075), 0.0),
        )
        risultati[k] = tir(proiezione(variante)["Flusso netto"])
    return pd.Series(risultati, name="TIR")
