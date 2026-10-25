"""Fiscalità immobiliare italiana per persone fisiche.

Regole semplificate ma fedeli alla normativa per un immobile abitativo (categorie A, escluse A/1, A/8,
A/9 e A/10) posseduto da un privato:

* imposte d'acquisto con il criterio del prezzo-valore (da privato) o con IVA (da impresa);
* IMU sulla rendita catastale rivalutata, ridotta del 25% per i contratti a canone concordato;
* cedolare secca al 21% (10% a canone concordato), in alternativa all'IRPEF ordinaria sul 95%
  del canone, con imposta di registro sul contratto;
* imposta sostitutiva sul mutuo;
* plusvalenza tassata al 26% solo se l'immobile è rivenduto entro cinque anni.
"""

from __future__ import annotations

from dataclasses import dataclass

RIVALUTAZIONE_RENDITA = 1.05
MOLTIPLICATORE_REGISTRO = 120  # seconda casa
MOLTIPLICATORE_REGISTRO_PRIMA_CASA = 110
MOLTIPLICATORE_IMU = 160
IVA_AGENZIA = 0.22
CEDOLARE_ORDINARIA = 0.21
CEDOLARE_CONCORDATO = 0.10
RIDUZIONE_IMU_CONCORDATO = 0.25
RIDUZIONE_IRPEF_CONCORDATO = 0.30
REGISTRO_CONTRATTO_LOCATORE = 0.01  # 2% annuo diviso a metà con l'inquilino
IMPOSTA_PLUSVALENZA = 0.26
ANNI_ESENZIONE_PLUSVALENZA = 5


@dataclass(frozen=True)
class ImposteAcquisto:
    iva: float
    registro: float
    ipotecaria: float
    catastale: float

    @property
    def totale(self) -> float:
        return self.iva + self.registro + self.ipotecaria + self.catastale


def valore_catastale(rendita: float, prima_casa: bool = False) -> float:
    """Base imponibile dell'imposta di registro con il criterio del prezzo-valore."""
    molt = MOLTIPLICATORE_REGISTRO_PRIMA_CASA if prima_casa else MOLTIPLICATORE_REGISTRO
    return rendita * RIVALUTAZIONE_RENDITA * molt


def imposte_acquisto(
    prezzo: float,
    rendita: float,
    prima_casa: bool = False,
    da_impresa: bool = False,
    aliquota_iva: float = 0.10,
) -> ImposteAcquisto:
    """Imposte dovute al rogito."""
    if da_impresa:
        iva = prezzo * (0.04 if prima_casa else aliquota_iva)
        return ImposteAcquisto(iva=iva, registro=200, ipotecaria=200, catastale=200)
    aliquota = 0.02 if prima_casa else 0.09
    registro = max(valore_catastale(rendita, prima_casa) * aliquota, 1_000)
    return ImposteAcquisto(iva=0, registro=registro, ipotecaria=50, catastale=50)


def imu(rendita: float, aliquota: float = 0.0106, canone_concordato: bool = False,
        prima_casa: bool = False) -> float:
    """IMU annua. L'abitazione principale non di lusso è esente."""
    if prima_casa:
        return 0.0
    base = rendita * RIVALUTAZIONE_RENDITA * MOLTIPLICATORE_IMU
    imposta = base * aliquota
    return imposta * (1 - RIDUZIONE_IMU_CONCORDATO) if canone_concordato else imposta


def imposte_locazione(
    canone_annuo: float,
    rendita: float,
    regime: str = "cedolare",
    canone_concordato: bool = False,
    aliquota_irpef: float = 0.35,
    addizionali: float = 0.02,
) -> float:
    """Imposte annue sul reddito da locazione.

    * ``cedolare``: imposta sostitutiva sul canone lordo, senza registro sul contratto.
    * ``ordinario``: IRPEF marginale più addizionali sul maggiore tra canone ridotto del 5% (e di un
      ulteriore 30% se concordato) e rendita rivalutata, più la metà dell'imposta di registro.
    """
    if canone_annuo <= 0:
        return 0.0
    if regime == "cedolare":
        return canone_annuo * (CEDOLARE_CONCORDATO if canone_concordato else CEDOLARE_ORDINARIA)
    if regime != "ordinario":
        raise ValueError(f"Regime fiscale sconosciuto: {regime!r} (usa 'cedolare' o 'ordinario')")
    riduzione = 0.95 * ((1 - RIDUZIONE_IRPEF_CONCORDATO) if canone_concordato else 1)
    imponibile = max(canone_annuo * riduzione, rendita * RIVALUTAZIONE_RENDITA)
    registro = canone_annuo * REGISTRO_CONTRATTO_LOCATORE * (0.7 if canone_concordato else 1)
    return imponibile * (aliquota_irpef + addizionali) + registro


def imposta_sostitutiva_mutuo(importo: float, prima_casa: bool = False) -> float:
    return importo * (0.0025 if prima_casa else 0.02)


def imposta_plusvalenza(prezzo_vendita_netto: float, costo_fiscale: float, anni_possesso: int) -> float:
    """Imposta sostitutiva sulla plusvalenza, dovuta solo per vendite entro cinque anni."""
    if anni_possesso >= ANNI_ESENZIONE_PLUSVALENZA:
        return 0.0
    return max(prezzo_vendita_netto - costo_fiscale, 0.0) * IMPOSTA_PLUSVALENZA
