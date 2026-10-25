import pytest

from real_estate_analyzer.mutuo import piano_ammortamento, piano_annuale, rata_mensile


def test_rata_formula_chiusa():
    # 100.000 € al 3% per 20 anni: rata = P·i / (1 − (1+i)^−n)
    i, n = 0.03 / 12, 240
    attesa = 100_000 * i / (1 - (1 + i) ** -n)
    assert rata_mensile(100_000, 0.03, 20) == pytest.approx(attesa)
    assert rata_mensile(100_000, 0.03, 20) == pytest.approx(554.60, abs=0.01)


def test_piano_rimborsa_tutto_il_capitale():
    piano = piano_ammortamento(150_000, 0.035, 25)
    assert len(piano) == 300
    assert piano["Capitale"].sum() == pytest.approx(150_000)
    assert piano["Debito residuo"].iat[-1] == 0
    assert piano["Rata"].std() == pytest.approx(0, abs=1e-8)  # rata costante
    assert piano["Interessi"].is_monotonic_decreasing


def test_tasso_zero_e_importo_nullo():
    assert rata_mensile(120_000, 0.0, 10) == pytest.approx(1_000)
    assert rata_mensile(0, 0.03, 10) == 0
    assert piano_ammortamento(0, 0.03, 10)["Rata"].sum() == 0


def test_piano_annuale_esteso_oltre_la_durata():
    annuale = piano_annuale(50_000, 0.03, 5, anni=8)
    assert list(annuale.index) == list(range(1, 9))
    assert annuale.loc[6:, "Rata"].sum() == 0
    assert annuale.loc[1, "Rata"] == pytest.approx(12 * rata_mensile(50_000, 0.03, 5))
