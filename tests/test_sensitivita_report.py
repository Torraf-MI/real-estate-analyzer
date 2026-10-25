import numpy as np

from real_estate_analyzer import esempio_milano
from real_estate_analyzer import sensitivita as s
from real_estate_analyzer.cli import main
from real_estate_analyzer.modello import Investimento, load_toml
from real_estate_analyzer.report import analizza, build_report


def test_griglia_monotona():
    g = s.griglia(esempio_milano(), "TIR")
    assert g.shape == (7, 7)
    # prezzo più alto -> TIR più basso; canone più alto -> TIR più alto
    assert (np.diff(g.to_numpy(), axis=0) < 0).all()
    assert (np.diff(g.to_numpy(), axis=1) > 0).all()


def test_tornado_ordinato_e_coerente():
    inv = esempio_milano()
    t = s.tornado(inv)
    assert t["Ampiezza"].is_monotonic_decreasing
    assert (t["Favorevole"] > t["Sfavorevole"]).all()


def test_simulazione_riproducibile():
    inv = esempio_milano()
    a, b = s.simulazione(inv, 50, seed=1), s.simulazione(inv, 50, seed=1)
    assert a.equals(b)


def test_report_html(tmp_path):
    a = analizza(esempio_milano(), n_simulazioni=50)
    path = build_report(a, tmp_path / "r.html", client_name="Famiglia Verdi")
    html = path.read_text(encoding="utf-8")
    assert "Famiglia Verdi" in html
    assert "Prezzo massimo d&#39;offerta" in html
    assert html.count("plotly-graph-div") >= 6


def test_config_toml_e_cli(tmp_path):
    inv = load_toml("examples/trilocale_torino.toml")
    assert isinstance(inv, Investimento)
    assert inv.locazione.canone_concordato
    out = tmp_path / "report.html"
    assert main(["--config", "examples/trilocale_torino.toml", "--simulazioni", "20", "--output", str(out)]) == 0
    assert out.exists()


def test_modifica_ipotesi():
    inv = esempio_milano().con(acquisto__prezzo=250_000, mutuo__ltv=0, nome="Variante")
    assert inv.acquisto.prezzo == 250_000 and inv.mutuo.ltv == 0 and inv.nome == "Variante"
    assert esempio_milano().acquisto.prezzo == 280_000  # l'originale non cambia
