"""Grafici interattivi (plotly) e report HTML per il cliente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, PackageLoader, select_autoescape
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from . import sensitivita
from .flussi import CostoIniziale, costo_iniziale, proiezione
from .metriche import calcola
from .modello import Investimento

BLU, ARANCIO, ACQUA = "#2a78d6", "#eb6834", "#1baf7a"
BLU_SCURO, ROSSO, GRIGIO_NEUTRO = "#1c5cab", "#e34948", "#f0efec"
TESTO, TESTO_SECONDARIO, GRIGLIA = "#222222", "#52514e", "#e6e5e1"
PLOTLY_CDN = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"


def _layout(fig: go.Figure, titolo: str, altezza: int = 420) -> go.Figure:
    fig.update_layout(
        title={"text": titolo, "x": 0, "font": {"size": 15, "color": TESTO}},
        height=altezza,
        template="plotly_white",
        font={"family": "Segoe UI, Helvetica, Arial, sans-serif", "size": 12, "color": TESTO_SECONDARIO},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
        separators=",.",
        hoverlabel={"bgcolor": "white", "font_color": TESTO},
        legend={"orientation": "h", "y": -0.18, "x": 0},
    )
    fig.update_xaxes(gridcolor=GRIGLIA, zeroline=False)
    fig.update_yaxes(gridcolor=GRIGLIA, zerolinecolor="#bdbcb6")
    return fig


@dataclass
class Analisi:
    """Risultato completo dell'analisi, usato per grafici e report."""

    investimento: Investimento
    costo: CostoIniziale
    flussi: pd.DataFrame
    indicatori: dict[str, float]
    griglia_tir: pd.DataFrame
    tornado: pd.DataFrame
    scenari: pd.DataFrame
    simulazione: pd.Series


def analizza(inv: Investimento, n_simulazioni: int = 1_000) -> Analisi:
    flussi = proiezione(inv)
    return Analisi(
        investimento=inv,
        costo=costo_iniziale(inv),
        flussi=flussi,
        indicatori=calcola(inv, flussi),
        griglia_tir=sensitivita.griglia(inv, "TIR"),
        tornado=sensitivita.tornado(inv, "TIR"),
        scenari=sensitivita.confronta_scenari(sensitivita.scenari_standard(inv)),
        simulazione=sensitivita.simulazione(inv, n_simulazioni),
    )


# --------------------------------------------------------------------------- #
# Grafici
# --------------------------------------------------------------------------- #
def grafico_cascata(a: Analisi) -> go.Figure:
    """Dal canone al flusso netto del primo anno."""
    r = a.flussi.loc[1]
    spese = r[["Condominio", "Manutenzione", "Assicurazione", "Gestione"]].sum()
    voci = [
        ("Canone annuo", r["Canone potenziale"], "absolute"),
        ("Sfitto", -r["Sfitto"], "relative"),
        ("Spese", -spese, "relative"),
        ("IMU", -r["IMU"], "relative"),
        ("Imposte sul reddito", -r["Imposte sul reddito"], "relative"),
        ("Interessi mutuo", -r["Interessi"], "relative"),
        ("Quota capitale", -r["Quota capitale"], "relative"),
        ("Flusso netto", r["Flusso netto"], "total"),
    ]
    if not a.investimento.mutuo.attivo:
        voci = [v for v in voci if v[0] not in ("Interessi mutuo", "Quota capitale")]
    fig = go.Figure(
        go.Waterfall(
            x=[v[0] for v in voci],
            y=[v[1] if v[2] != "total" else 0 for v in voci],
            measure=[v[2] for v in voci],
            text=[_eur(v[1]) for v in voci],
            textposition="outside",
            increasing={"marker": {"color": BLU}},
            decreasing={"marker": {"color": ARANCIO}},
            totals={"marker": {"color": BLU_SCURO}},
            connector={"line": {"color": "#bdbcb6", "width": 1}},
            hovertemplate="%{x}: € %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f")
    return _layout(fig, "Primo anno: dal canone al flusso di cassa netto")


def grafico_flussi(a: Analisi) -> go.Figure:
    """Flusso di cassa annuo della gestione: redditi meno spese, imposte e rata (esclusi rogito e vendita)."""
    df = a.flussi.loc[1:]
    gestione = df["NOI"] - df["Imposte sul reddito"] - df["Rata"]
    fig = go.Figure(
        go.Bar(
            x=df.index, y=gestione, name="Flusso della gestione",
            marker={"color": [ARANCIO if v < 0 else BLU for v in gestione]},
            text=[_eur(v) for v in gestione], textposition="outside",
            hovertemplate="Anno %{x}<br>Flusso della gestione € %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_xaxes(title="Anno", dtick=1)
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f")
    fig.update_layout(showlegend=False)
    return _layout(fig, "Flusso di cassa annuo della gestione, dopo imposte e rata (esclusi acquisto e vendita)")


def grafico_patrimonio(a: Analisi) -> go.Figure:
    """Valore dell'immobile, debito residuo e patrimonio netto nel tempo."""
    df = a.flussi
    fig = go.Figure()
    fig.add_scatter(x=df.index, y=df["Valore immobile"], name="Valore dell'immobile",
                    line={"color": BLU, "width": 2}, hovertemplate="€ %{y:,.0f}")
    fig.add_scatter(x=df.index, y=df["Debito residuo"], name="Debito residuo del mutuo",
                    line={"color": ARANCIO, "width": 2}, hovertemplate="€ %{y:,.0f}")
    fig.add_scatter(x=df.index, y=df["Patrimonio netto"], name="Patrimonio netto (valore − debito)",
                    line={"color": ACQUA, "width": 2}, fill="tozeroy",
                    fillcolor="rgba(27,175,122,0.12)", hovertemplate="€ %{y:,.0f}")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(title="Anno", dtick=1)
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f", rangemode="tozero")
    return _layout(fig, "Crescita del patrimonio netto")


def grafico_griglia(a: Analisi) -> go.Figure:
    """Mappa del TIR al variare di prezzo e canone, centrata sul rendimento richiesto."""
    g = a.griglia_tir
    obiettivo = a.investimento.scenario.tasso_sconto
    z = g.to_numpy()
    ampiezza = max(np.nanmax(np.abs(z - obiettivo)), 0.01)
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[_eur(c) for c in g.columns],
            y=[_eur(p) for p in g.index],
            zmin=obiettivo - ampiezza,
            zmax=obiettivo + ampiezza,
            colorscale=[[0, ROSSO], [0.5, GRIGIO_NEUTRO], [1, BLU]],
            text=[[_pct(v) for v in riga] for riga in z],
            texttemplate="%{text}",
            textfont={"size": 11, "color": TESTO},
            xgap=2,
            ygap=2,
            colorbar={"title": "TIR", "tickformat": ".0%"},
            hovertemplate="Prezzo %{y}<br>Canone %{x}/mese<br>TIR %{text}<extra></extra>",
        )
    )
    fig.update_xaxes(title="Canone mensile", side="bottom", showgrid=False)
    fig.update_yaxes(title="Prezzo d'acquisto", autorange="reversed", showgrid=False)
    return _layout(fig, f"TIR del capitale proprio per prezzo e canone (in blu: sopra il {_pct(obiettivo)} "
                        "richiesto)", altezza=460)


def grafico_tornado(a: Analisi) -> go.Figure:
    t = a.tornado.iloc[::-1]
    base = t.attrs.get("base", a.indicatori["TIR"])
    fig = go.Figure()
    etichette = [f"{n} ({b} → {f})" for n, b, f in zip(t["Ipotesi"], t["Valore sfavorevole"], t["Valore favorevole"])]
    fig.add_bar(
        y=etichette, x=t["Sfavorevole"] - base, base=base, orientation="h", name="Scenario sfavorevole",
        marker={"color": ARANCIO}, customdata=np.c_[t["Valore sfavorevole"], t["Sfavorevole"]],
        hovertemplate="%{customdata[0]}<br>TIR %{customdata[1]:.2%}<extra></extra>",
    )
    fig.add_bar(
        y=etichette, x=t["Favorevole"] - base, base=base, orientation="h", name="Scenario favorevole",
        marker={"color": BLU}, customdata=np.c_[t["Valore favorevole"], t["Favorevole"]],
        hovertemplate="%{customdata[0]}<br>TIR %{customdata[1]:.2%}<extra></extra>",
    )
    fig.add_vline(x=base, line={"color": TESTO, "width": 1, "dash": "dot"},
                  annotation_text=f"Base {_pct(base)}", annotation_position="top")
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_xaxes(tickformat=".1%", title="TIR del capitale proprio")
    return _layout(fig, "Quali ipotesi pesano di più sul rendimento", altezza=400)


def grafico_simulazione(a: Analisi) -> go.Figure:
    s = a.simulazione.dropna()
    obiettivo = a.investimento.scenario.tasso_sconto
    fig = go.Figure(
        go.Histogram(x=s, nbinsx=40, marker={"color": BLU, "line": {"color": "white", "width": 1}},
                     hovertemplate="TIR %{x}<br>%{y} simulazioni<extra></extra>", name="Simulazioni")
    )
    fig.add_vline(x=obiettivo, line={"color": ROSSO, "width": 2, "dash": "dash"},
                  annotation_text=f"Rendimento richiesto {_pct(obiettivo)}", annotation_position="top right")
    fig.update_xaxes(tickformat=".0%", title="TIR del capitale proprio")
    fig.update_yaxes(title="Numero di simulazioni")
    fig.update_layout(showlegend=False)
    return _layout(fig, f"Distribuzione del TIR su {len(s):,} scenari simulati".replace(",", "."), altezza=380)


GRAFICI = {
    "cascata": grafico_cascata,
    "flussi": grafico_flussi,
    "patrimonio": grafico_patrimonio,
    "griglia": grafico_griglia,
    "tornado": grafico_tornado,
    "simulazione": grafico_simulazione,
}


def salva_grafici(a: Analisi, cartella: str | Path, scala: float = 2.0) -> list[Path]:
    """Esporta i grafici in PNG (richiede ``kaleido`` e un browser Chrome/Chromium)."""
    out = Path(cartella)
    out.mkdir(parents=True, exist_ok=True)
    percorsi = []
    for nome, funzione in GRAFICI.items():
        percorso = out / f"{nome}.png"
        funzione(a).write_image(percorso, width=900, scale=scala)
        percorsi.append(percorso)
    return percorsi


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _pct(x: float, decimali: int = 1) -> str:
    if pd.isna(x):
        return "–"
    if np.isinf(x):
        return "oltre 100%"
    return f"{x:.{decimali}%}".replace(".", ",")


def _num(x: float) -> str:
    return "–" if pd.isna(x) else f"{x:.2f}".replace(".", ",")


def _eur(x: float) -> str:
    if pd.isna(x):
        return "–"
    testo = f"{abs(x):,.0f}".replace(",", ".")
    return f"−€ {testo}" if x < -0.5 else f"€ {testo}"


def _giudizio(ind: dict[str, float], obiettivo: float) -> tuple[str, str]:
    """Una frase di sintesi e una classe CSS per il riquadro di esito."""
    van, tir_ = ind["VAN"], ind["TIR"]
    if van >= 0:
        return (f"L'investimento rende il {_pct(tir_)} annuo sul capitale proprio, sopra il {_pct(obiettivo)} "
                f"richiesto: crea valore per {_eur(van)} in termini attuali.", "ok")
    if tir_ > 0:
        return (f"L'investimento rende il {_pct(tir_)} annuo sul capitale proprio, sotto il {_pct(obiettivo)} "
                f"richiesto. Per raggiungerlo il prezzo non dovrebbe superare "
                f"{_eur(ind['Prezzo massimo'])}.", "attenzione")
    return ("Con queste ipotesi l'investimento non recupera il capitale investito.", "ko")


def _tabella_flussi(df: pd.DataFrame) -> tuple[list[str], list[dict]]:
    voci = ["Canone incassato", "Condominio", "Manutenzione", "Assicurazione", "Gestione", "IMU", "NOI",
            "Imposte sul reddito", "Interessi", "Quota capitale", "Vendita netta", "Flusso netto",
            "Flusso cumulato"]
    costi = {"Condominio", "Manutenzione", "Assicurazione", "Gestione", "IMU", "Imposte sul reddito",
             "Interessi", "Quota capitale"}
    voci = [v for v in voci if df[v].abs().sum() > 0.5]
    righe = []
    for v in voci:
        valori = -df[v] if v in costi else df[v]
        righe.append({"voce": v, "valori": [_eur(x) if abs(x) > 0.5 else "–" for x in valori],
                      "forte": v in ("NOI", "Flusso netto")})
    return [str(a) for a in df.index], righe


def build_report(
    a: Analisi,
    output: str | Path,
    client_name: str = "Cliente",
    data_note: str = "",
    offline: bool = False,
) -> Path:
    """Scrive il report HTML. Con ``offline=True`` include plotly.js nel file (circa 4 MB)."""
    inv, ind = a.investimento, a.indicatori
    obiettivo = inv.scenario.tasso_sconto
    sintesi, esito = _giudizio(ind, obiettivo)
    config = {"displaylogo": False, "responsive": True}
    grafici = {nome: f(a).to_html(full_html=False, include_plotlyjs=False, config=config)
               for nome, f in GRAFICI.items()}

    loc, m, sc, acq = inv.locazione, inv.mutuo, inv.scenario, inv.acquisto
    regime = ("cedolare secca al " + _pct(0.10 if loc.canone_concordato else 0.21, 0)
              if loc.regime == "cedolare" else f"IRPEF ordinaria (aliquota marginale {_pct(loc.aliquota_irpef, 0)})")
    ipotesi = [
        ("Prezzo d'acquisto", _eur(acq.prezzo)),
        ("Valore di mercato iniziale", _eur(acq.valore_iniziale)),
        ("Rendita catastale", _eur(acq.rendita_catastale)),
        ("Canone mensile", f"{_eur(loc.canone_mensile)}{' (concordato)' if loc.canone_concordato else ''}"),
        ("Crescita del canone", f"{_pct(loc.crescita_canone)} annuo"),
        ("Sfitto atteso", _pct(loc.sfitto)),
        ("Regime fiscale", regime),
        ("Mutuo", f"{_pct(m.ltv, 0)} del prezzo, tasso {_pct(m.tasso, 2)}, {m.durata_anni} anni"
         if m.attivo else "nessuno, acquisto in contanti"),
        ("Orizzonte e rivalutazione", f"vendita dopo {sc.orizzonte} anni, valore +{_pct(sc.crescita_valore)} annuo"),
        ("Rendimento richiesto", _pct(obiettivo)),
    ]
    sim = a.simulazione.dropna()
    anni, righe_flussi = _tabella_flussi(a.flussi)
    scenari = [
        {"nome": nome, "capitale": _eur(r["Capitale proprio"]), "netto": _pct(r["Rendimento netto"]),
         "coc": _pct(r["Cash-on-cash"]), "van": _eur(r["VAN"]), "tir": _pct(r["TIR"]),
         "multiplo": _num(r["Moltiplicatore del capitale"]) + "×"}
        for nome, r in a.scenari.iterrows()
    ]

    env = Environment(loader=PackageLoader("real_estate_analyzer", "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template("report.html.j2").render(
        client=client_name,
        nome=inv.nome,
        today=date.today().strftime("%d/%m/%Y"),
        plotly_inline=get_plotlyjs() if offline else None,
        plotly_cdn=PLOTLY_CDN,
        sintesi=sintesi,
        esito=esito,
        kpi=[
            ("TIR del capitale proprio", _pct(ind["TIR"])),
            ("VAN al " + _pct(obiettivo), _eur(ind["VAN"])),
            ("Capitale proprio", _eur(ind["Capitale proprio"])),
            ("Prezzo massimo d'offerta", _eur(ind["Prezzo massimo"])),
        ],
        indicatori=[
            ("Rendimento lordo", _pct(ind["Rendimento lordo"]), "canone annuo / prezzo"),
            ("Rendimento netto", _pct(ind["Rendimento netto"]), "reddito netto di spese e imposte / costo complessivo"),
            ("Cap rate", _pct(ind["Cap rate"]), "reddito operativo netto (NOI) / valore dell'immobile"),
            ("Cash-on-cash", _pct(ind["Cash-on-cash"]), "flusso netto del primo anno / capitale proprio"),
            ("TIR senza leva", _pct(ind["TIR senza leva"]), "rendimento se l'acquisto fosse in contanti"),
            ("DSCR minimo", _num(ind["DSCR minimo"]), "NOI / rata del mutuo: sotto 1,2 le banche sono caute"),
            ("Moltiplicatore del capitale", _num(ind["Moltiplicatore del capitale"]) + "×",
             "euro restituiti per ogni euro investito"),
            ("Occupazione di pareggio", _pct(ind["Occupazione di pareggio"]),
             "quota dell'anno da affittare per non andare in perdita di cassa"),
            ("Valore DCF", _eur(ind["Valore DCF"]), "spesa complessiva massima pagando in contanti"),
        ],
        costi=[(v, _eur(x)) for v, x in a.costo.voci().items() if x > 0.5],
        costo_totale=_eur(a.costo.totale),
        importo_mutuo=_eur(a.costo.importo_mutuo),
        capitale_proprio=_eur(a.costo.capitale_proprio),
        ipotesi=ipotesi,
        anni=anni,
        righe_flussi=righe_flussi,
        scenari=scenari,
        tornado_top=a.tornado.iloc[0]["Ipotesi"].lower(),
        sim_mediana=_pct(sim.median()),
        sim_p10=_pct(sim.quantile(0.10)),
        sim_p90=_pct(sim.quantile(0.90)),
        sim_sopra=_pct((sim >= obiettivo).mean(), 0),
        grafici=grafici,
        data_note=data_note,
    )
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
