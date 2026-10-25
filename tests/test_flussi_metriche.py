import numpy as np
import pytest

from real_estate_analyzer import calcola, costo_iniziale, esempio_milano, prezzo_massimo, proiezione, tir, van
from real_estate_analyzer.metriche import con_prezzo
from real_estate_analyzer.modello import Acquisto, Investimento, Locazione, Mutuo, Scenario, Spese


def investimento_semplice(**scenario) -> Investimento:
    """Nessun costo, nessuna imposta, nessuna crescita: i risultati si calcolano a mano."""
    return Investimento(
        acquisto=Acquisto(prezzo=100_000, rendita_catastale=0, agenzia=0, notaio=0, prima_casa=True),
        locazione=Locazione(canone_mensile=500, crescita_canone=0, sfitto=0, regime="cedolare"),
        spese=Spese(condominio=0, manutenzione=0, assicurazione=0, aliquota_imu=0, inflazione=0),
        scenario=Scenario(**{"orizzonte": 10, "crescita_valore": 0, "costi_vendita": 0, **scenario}),
    )


def test_registro_minimo_e_flussi_noti():
    inv = investimento_semplice()
    df = proiezione(inv)
    # registro minimo 1.000 € + 100 € di ipotecaria e catastale
    assert costo_iniziale(inv).totale == pytest.approx(101_100)
    assert df.loc[1, "NOI"] == pytest.approx(6_000)
    assert df.loc[1, "Imposte sul reddito"] == pytest.approx(1_260)  # cedolare 21%
    assert df.loc[10, "Vendita netta"] == pytest.approx(100_000)
    assert df.loc[0, "Flusso netto"] == pytest.approx(-101_100)


def test_van_nullo_al_tir():
    flussi = proiezione(esempio_milano())["Flusso netto"]
    r = tir(flussi)
    assert van(flussi, r) == pytest.approx(0, abs=1e-4)


def test_tir_di_una_rendita_perpetua_approssimata():
    # Senza costi d'acquisto il TIR coincide col rendimento netto annuo (4.740 / 100.000)
    inv = investimento_semplice().con(acquisto__rendita_catastale=0)
    flussi = proiezione(inv)["Flusso netto"].copy()
    flussi.iloc[0] = -100_000
    assert tir(flussi) == pytest.approx(0.0474)


def test_mutuo_rimborsato_alla_vendita():
    inv = esempio_milano()
    df = proiezione(inv)
    ultimo = df.iloc[-1]
    atteso = (ultimo["NOI"] - ultimo["Imposte sul reddito"] - ultimo["Rata"] + ultimo["Vendita netta"]
              - ultimo["Debito residuo"])
    assert ultimo["Flusso netto"] == pytest.approx(atteso)
    assert df.loc[0, "Debito residuo"] == pytest.approx(inv.acquisto.prezzo * inv.mutuo.ltv)


def test_leva_e_capitale_proprio():
    inv = esempio_milano()
    con_leva = calcola(inv)
    contanti = calcola(inv.con(mutuo__ltv=0))
    assert con_leva["Capitale proprio"] < contanti["Capitale proprio"]
    assert contanti["TIR"] == pytest.approx(contanti["TIR senza leva"])
    assert np.isnan(contanti["DSCR minimo"])


def test_cedolare_conviene_con_aliquota_marginale_alta():
    inv = esempio_milano()
    ordinario = inv.con(locazione__regime="ordinario", locazione__aliquota_irpef=0.43)
    assert calcola(inv)["TIR"] > calcola(ordinario)["TIR"]


def test_prezzo_massimo_azzera_il_van():
    inv = esempio_milano()
    p = prezzo_massimo(inv)
    flussi = proiezione(con_prezzo(inv, p))["Flusso netto"]
    assert van(flussi, inv.scenario.tasso_sconto) == pytest.approx(0, abs=1)
    assert (p < inv.acquisto.prezzo) == (calcola(inv)["VAN"] < 0)


def test_vendita_entro_cinque_anni_paga_la_plusvalenza():
    inv = esempio_milano().con(scenario__orizzonte=3, scenario__crescita_valore=0.08)
    assert proiezione(inv)["Imposta plusvalenza"].sum() > 0
    assert proiezione(inv.con(scenario__orizzonte=5))["Imposta plusvalenza"].sum() == 0


def test_occupazione_di_pareggio():
    inv = esempio_milano().con(mutuo__ltv=0)
    occ = calcola(inv)["Occupazione di pareggio"]
    assert 0 < occ < 1
    flusso = proiezione(inv.con(locazione__sfitto=1 - occ))["Flusso netto"].iat[1]
    assert flusso == pytest.approx(0, abs=0.01)


def test_mutuo_piu_breve_dell_orizzonte():
    inv = esempio_milano().con(mutuo=Mutuo(ltv=0.5, tasso=0.03, durata_anni=5), scenario__orizzonte=8)
    df = proiezione(inv)
    assert df.loc[6:, "Rata"].sum() == 0
    assert df.loc[5:, "Debito residuo"].abs().max() == pytest.approx(0, abs=1e-6)
