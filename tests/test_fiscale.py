import pytest

from real_estate_analyzer import fiscale


def test_registro_seconda_casa_su_valore_catastale():
    # rendita 1.000 € -> valore catastale 1.000 × 1,05 × 120 = 126.000 €, registro 9% = 11.340 €
    imp = fiscale.imposte_acquisto(prezzo=300_000, rendita=1_000)
    assert imp.registro == pytest.approx(11_340)
    assert imp.ipotecaria + imp.catastale == 100
    assert imp.iva == 0


def test_registro_prima_casa_con_minimo():
    # 300 × 1,05 × 110 × 2% = 693 €, sotto il minimo di 1.000 €
    assert fiscale.imposte_acquisto(200_000, 300, prima_casa=True).registro == 1_000


def test_acquisto_da_impresa_con_iva():
    imp = fiscale.imposte_acquisto(250_000, 900, da_impresa=True)
    assert imp.iva == pytest.approx(25_000)
    assert imp.totale == pytest.approx(25_600)


def test_imu_e_riduzione_concordato():
    # 1.000 × 1,05 × 160 × 1,06% = 1.780,80 €
    assert fiscale.imu(1_000, 0.0106) == pytest.approx(1_780.8)
    assert fiscale.imu(1_000, 0.0106, canone_concordato=True) == pytest.approx(1_780.8 * 0.75)
    assert fiscale.imu(1_000, 0.0106, prima_casa=True) == 0


def test_cedolare_secca():
    assert fiscale.imposte_locazione(12_000, 800, "cedolare") == pytest.approx(2_520)
    assert fiscale.imposte_locazione(12_000, 800, "cedolare", canone_concordato=True) == pytest.approx(1_200)


def test_irpef_ordinaria_sul_95_per_cento_piu_registro():
    imposta = fiscale.imposte_locazione(12_000, 800, "ordinario", aliquota_irpef=0.35, addizionali=0.02)
    assert imposta == pytest.approx(12_000 * 0.95 * 0.37 + 120)


def test_irpef_usa_la_rendita_se_maggiore_del_canone_ridotto():
    imposta = fiscale.imposte_locazione(1_000, 2_000, "ordinario", aliquota_irpef=0.23, addizionali=0.0)
    assert imposta == pytest.approx(2_000 * 1.05 * 0.23 + 10)


def test_regime_sconosciuto():
    with pytest.raises(ValueError):
        fiscale.imposte_locazione(12_000, 800, "forfettario")


def test_plusvalenza_esente_dopo_cinque_anni():
    assert fiscale.imposta_plusvalenza(400_000, 300_000, anni_possesso=5) == 0
    assert fiscale.imposta_plusvalenza(400_000, 300_000, anni_possesso=3) == pytest.approx(26_000)
    assert fiscale.imposta_plusvalenza(250_000, 300_000, anni_possesso=3) == 0
