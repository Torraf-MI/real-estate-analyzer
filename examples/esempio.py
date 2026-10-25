"""Esempio d'uso come libreria: dalle ipotesi al report per il cliente.

Esegui dalla cartella del progetto:  python examples/esempio.py
"""

from real_estate_analyzer import calcola, esempio_milano, load_toml, piano_ammortamento, proiezione
from real_estate_analyzer.report import analizza, build_report
from real_estate_analyzer.sensitivita import confronta_scenari, griglia, tornado

inv = esempio_milano()

# 1. Indicatori principali
for nome, valore in calcola(inv).items():
    print(f"{nome:<28} {valore:,.4f}")

# 2. Flussi di cassa anno per anno e piano del mutuo
print(proiezione(inv)[["Canone incassato", "NOI", "Imposte sul reddito", "Rata", "Flusso netto"]].round(0))
print(piano_ammortamento(168_000, 0.03, 25).head(12).round(2))

# 3. Cosa succede se il cliente paga in contanti e sceglie il regime ordinario?
varianti = {
    "Base": inv,
    "Contanti": inv.con(mutuo__ltv=0),
    "IRPEF 43%": inv.con(locazione__regime="ordinario", locazione__aliquota_irpef=0.43),
}
print(confronta_scenari(varianti).round(3))

# 4. Sensitività del TIR a prezzo e canone, e ipotesi più influenti
print(griglia(inv, "TIR").round(3))
print(tornado(inv)[["Ipotesi", "Sfavorevole", "Favorevole"]].round(3))

# 5. Report HTML da un file di ipotesi
torino = load_toml("examples/trilocale_torino.toml")
print(build_report(analizza(torino), "output/report_torino.html", client_name="Famiglia Bianchi"))
