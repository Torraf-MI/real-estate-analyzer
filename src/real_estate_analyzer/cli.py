"""Riga di comando: valuta un investimento immobiliare e genera il report per il cliente.

Esempi::

    real-estate-analyzer --demo --cliente "Mario Rossi"
    real-estate-analyzer --config examples/trilocale_torino.toml --offline
    real-estate-analyzer --demo --prezzo 265000 --senza-mutuo --regime ordinario
"""

from __future__ import annotations

import argparse
import sys

from .metriche import calcola
from .modello import esempio_milano, load_toml
from .report import _eur, _pct, analizza, build_report, salva_grafici


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="real-estate-analyzer", description=__doc__.splitlines()[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--config", help="File TOML con le ipotesi dell'investimento")
    src.add_argument("--demo", action="store_true", help="Usa l'esempio di un bilocale a Milano")
    p.add_argument("--prezzo", type=float, help="Sostituisce il prezzo d'acquisto")
    p.add_argument("--canone", type=float, help="Sostituisce il canone mensile")
    p.add_argument("--regime", choices=["cedolare", "ordinario"], help="Regime fiscale della locazione")
    p.add_argument("--senza-mutuo", action="store_true", help="Acquisto interamente in contanti")
    p.add_argument("--simulazioni", type=int, default=1_000, help="Scenari Monte Carlo (default 1000)")
    p.add_argument("--cliente", default="Cliente", help="Nome del cliente nel report")
    p.add_argument("--output", default="output/report.html", help="Percorso del report HTML")
    p.add_argument("--offline", action="store_true", help="Include plotly.js nel report (file autonomo, ~4 MB)")
    p.add_argument("--grafici", help="Cartella dove salvare anche i grafici PNG (richiede kaleido)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inv = load_toml(args.config) if args.config else esempio_milano()
    modifiche = {}
    if args.prezzo is not None:
        modifiche["acquisto__prezzo"] = args.prezzo
    if args.canone is not None:
        modifiche["locazione__canone_mensile"] = args.canone
    if args.regime:
        modifiche["locazione__regime"] = args.regime
    if args.senza_mutuo:
        modifiche["mutuo__ltv"] = 0.0
    if modifiche:
        inv = inv.con(**modifiche)

    a = analizza(inv, n_simulazioni=args.simulazioni)
    note = "Esempio dimostrativo con valori plausibili, non riferiti a un immobile reale." if args.demo else ""
    path = build_report(a, args.output, client_name=args.cliente, data_note=note, offline=args.offline)
    if args.grafici:
        salva_grafici(a, args.grafici)

    ind = calcola(inv, a.flussi)
    print(inv.nome)
    for nome in ("Capitale proprio", "Rendimento lordo", "Rendimento netto", "Cap rate", "Cash-on-cash", "VAN",
                 "TIR", "TIR senza leva", "Prezzo massimo"):
        v = ind[nome]
        testo = _eur(v) if abs(v) > 10 else _pct(v, 2)
        print(f"  {nome:<20} {testo}")
    print(f"\nReport salvato in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
