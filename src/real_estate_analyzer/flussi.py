"""Costo iniziale e proiezione annua dei flussi di cassa."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import fiscale
from .modello import Investimento
from .mutuo import piano_annuale


@dataclass(frozen=True)
class CostoIniziale:
    """Esborso al rogito, scomposto per voce."""

    prezzo: float
    imposte: fiscale.ImposteAcquisto
    agenzia: float
    notaio: float
    ristrutturazione: float
    arredo: float
    importo_mutuo: float
    oneri_mutuo: float

    @property
    def costo_immobile(self) -> float:
        """Prezzo più oneri, lavori e arredo: il costo dell'investimento senza il finanziamento."""
        return (self.prezzo + self.imposte.totale + self.agenzia + self.notaio + self.ristrutturazione
                + self.arredo)

    @property
    def costo_fiscale(self) -> float:
        """Costo riconosciuto ai fini della plusvalenza (l'arredo non vi rientra)."""
        return self.costo_immobile - self.arredo

    @property
    def totale(self) -> float:
        return self.costo_immobile + self.oneri_mutuo

    @property
    def capitale_proprio(self) -> float:
        return self.totale - self.importo_mutuo

    def voci(self) -> pd.Series:
        return pd.Series(
            {
                "Prezzo": self.prezzo,
                "IVA": self.imposte.iva,
                "Imposta di registro": self.imposte.registro,
                "Imposte ipotecaria e catastale": self.imposte.ipotecaria + self.imposte.catastale,
                "Agenzia (IVA inclusa)": self.agenzia,
                "Notaio": self.notaio,
                "Ristrutturazione": self.ristrutturazione,
                "Arredo": self.arredo,
                "Oneri del mutuo": self.oneri_mutuo,
            }
        )


def costo_iniziale(inv: Investimento) -> CostoIniziale:
    a, m = inv.acquisto, inv.mutuo
    importo = a.prezzo * m.ltv
    oneri = 0.0
    if m.attivo:
        oneri = fiscale.imposta_sostitutiva_mutuo(importo, a.prima_casa) + m.spese_istruttoria + m.perizia
    return CostoIniziale(
        prezzo=a.prezzo,
        imposte=fiscale.imposte_acquisto(a.prezzo, a.rendita_catastale, a.prima_casa, a.da_impresa,
                                         a.aliquota_iva),
        agenzia=a.prezzo * a.agenzia * (1 + fiscale.IVA_AGENZIA),
        notaio=a.notaio,
        ristrutturazione=a.ristrutturazione,
        arredo=a.arredo,
        importo_mutuo=importo,
        oneri_mutuo=oneri,
    )


def proiezione(inv: Investimento) -> pd.DataFrame:
    """Flussi annui dall'anno 0 (rogito) all'anno di vendita.

    Le voci di costo sono positive; i flussi (``Flusso senza leva``, ``Flusso netto``) hanno segno.
    Il ``Flusso netto`` è quello del capitale proprio, dopo rata del mutuo e imposte.
    """
    a, loc, sp, m, sc = inv.acquisto, inv.locazione, inv.spese, inv.mutuo, inv.scenario
    if sc.orizzonte < 1:
        raise ValueError("L'orizzonte deve essere di almeno un anno")
    n = sc.orizzonte
    anni = np.arange(1, n + 1)
    costo = costo_iniziale(inv)

    canone = loc.canone_mensile * 12 * (1 + loc.crescita_canone) ** (anni - 1)
    sfitto = canone * loc.sfitto
    incassato = canone - sfitto
    inflaz = (1 + sp.inflazione) ** (anni - 1)
    imu = fiscale.imu(a.rendita_catastale, sp.aliquota_imu, loc.canone_concordato, a.prima_casa)
    df = pd.DataFrame(
        {
            "Canone potenziale": canone,
            "Sfitto": sfitto,
            "Canone incassato": incassato,
            "Condominio": sp.condominio * inflaz,
            "Manutenzione": sp.manutenzione * inflaz,
            "Assicurazione": sp.assicurazione * inflaz,
            "Gestione": incassato * sp.gestione,
            "IMU": np.full(n, imu),
        },
        index=pd.Index(anni, name="Anno"),
    )
    spese = df[["Condominio", "Manutenzione", "Assicurazione", "Gestione", "IMU"]].sum(axis=1)
    df["NOI"] = incassato - spese
    df["Imposte sul reddito"] = [
        fiscale.imposte_locazione(c, a.rendita_catastale, loc.regime, loc.canone_concordato,
                                  loc.aliquota_irpef, loc.addizionali)
        for c in incassato
    ]

    piano = piano_annuale(costo.importo_mutuo, m.tasso, m.durata_anni, anni=n)
    df["Interessi"] = piano["Interessi"].to_numpy()
    df["Quota capitale"] = piano["Capitale"].to_numpy()
    df["Rata"] = df["Interessi"] + df["Quota capitale"]
    df["Debito residuo"] = piano["Debito residuo"].to_numpy() if m.attivo else 0.0

    df["Valore immobile"] = a.valore_iniziale * (1 + sc.crescita_valore) ** anni
    vendita = df["Valore immobile"].iat[-1] * (1 - sc.costi_vendita)
    tassa = fiscale.imposta_plusvalenza(vendita, costo.costo_fiscale, n)
    df["Vendita netta"] = 0.0
    df.loc[n, "Vendita netta"] = vendita - tassa
    df["Imposta plusvalenza"] = 0.0
    df.loc[n, "Imposta plusvalenza"] = tassa

    rimborso = np.where(anni == n, df["Debito residuo"], 0.0)
    df["Flusso senza leva"] = df["NOI"] - df["Imposte sul reddito"] + df["Vendita netta"]
    df["Flusso netto"] = df["Flusso senza leva"] - df["Rata"] - rimborso

    anno0 = pd.DataFrame(
        {
            "Valore immobile": [a.valore_iniziale],
            "Debito residuo": [costo.importo_mutuo],
            "Flusso senza leva": [-costo.costo_immobile],
            "Flusso netto": [-costo.capitale_proprio],
        },
        index=pd.Index([0], name="Anno"),
    )
    df = pd.concat([anno0.reindex(columns=df.columns), df]).fillna(0.0)
    df["Flusso cumulato"] = df["Flusso netto"].cumsum()
    df["Patrimonio netto"] = df["Valore immobile"] - df["Debito residuo"]
    return df
