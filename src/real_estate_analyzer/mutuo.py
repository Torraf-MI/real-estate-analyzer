"""Piano di ammortamento alla francese."""

from __future__ import annotations

import numpy as np
import numpy_financial as npf
import pandas as pd


def rata_mensile(importo: float, tasso_annuo: float, durata_anni: int) -> float:
    """Rata costante mensile (positiva)."""
    if importo <= 0:
        return 0.0
    n = durata_anni * 12
    if tasso_annuo == 0:
        return importo / n
    return float(-npf.pmt(tasso_annuo / 12, n, importo))


def piano_ammortamento(importo: float, tasso_annuo: float, durata_anni: int) -> pd.DataFrame:
    """Piano mensile: rata, quota interessi, quota capitale e debito residuo."""
    n = durata_anni * 12
    mesi = np.arange(1, n + 1)
    if importo <= 0:
        zeri = np.zeros(n)
        return pd.DataFrame({"Rata": zeri, "Interessi": zeri, "Capitale": zeri, "Debito residuo": zeri},
                            index=pd.Index(mesi, name="Mese"))
    i = tasso_annuo / 12
    if tasso_annuo == 0:
        capitale = np.full(n, importo / n)
        interessi = np.zeros(n)
    else:
        interessi = -npf.ipmt(i, mesi, n, importo)
        capitale = -npf.ppmt(i, mesi, n, importo)
    residuo = importo - np.cumsum(capitale)
    residuo[np.isclose(residuo, 0, atol=1e-6)] = 0.0
    return pd.DataFrame(
        {"Rata": interessi + capitale, "Interessi": interessi, "Capitale": capitale, "Debito residuo": residuo},
        index=pd.Index(mesi, name="Mese"),
    )


def piano_annuale(importo: float, tasso_annuo: float, durata_anni: int, anni: int | None = None) -> pd.DataFrame:
    """Piano aggregato per anno, esteso con zeri oltre la durata del mutuo se ``anni`` è maggiore."""
    mensile = piano_ammortamento(importo, tasso_annuo, durata_anni)
    anno = (mensile.index - 1) // 12 + 1
    annuale = mensile[["Rata", "Interessi", "Capitale"]].groupby(anno).sum()
    annuale["Debito residuo"] = mensile["Debito residuo"].groupby(anno).last()
    annuale.index.name = "Anno"
    if anni is not None:
        annuale = annuale.reindex(range(1, anni + 1), fill_value=0.0)
    return annuale
