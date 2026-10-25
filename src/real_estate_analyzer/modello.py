"""Ipotesi dell'investimento: immobile, locazione, spese, mutuo e scenario di uscita."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class Acquisto:
    """Prezzo e costi di acquisto dell'immobile."""

    prezzo: float
    rendita_catastale: float
    prima_casa: bool = False
    da_impresa: bool = False  # vendita soggetta a IVA (costruttore o impresa)
    aliquota_iva: float = 0.10
    agenzia: float = 0.03  # provvigione in % del prezzo, IVA esclusa
    notaio: float = 2_500.0
    ristrutturazione: float = 0.0
    arredo: float = 0.0
    valore_mercato: float | None = None  # valore dell'immobile (dopo i lavori); se assente, è il prezzo

    @property
    def valore_iniziale(self) -> float:
        return self.prezzo if self.valore_mercato is None else self.valore_mercato


@dataclass(frozen=True)
class Locazione:
    """Canone e regime fiscale del contratto."""

    canone_mensile: float
    crescita_canone: float = 0.02  # adeguamento annuo (ISTAT)
    sfitto: float = 0.04  # quota dell'anno senza inquilino o con canoni non incassati
    canone_concordato: bool = False
    regime: Literal["cedolare", "ordinario"] = "cedolare"
    aliquota_irpef: float = 0.35  # aliquota marginale, usata nel regime ordinario
    addizionali: float = 0.02  # addizionali regionale e comunale


@dataclass(frozen=True)
class Spese:
    """Costi annui a carico del proprietario (valori del primo anno)."""

    condominio: float = 600.0  # quota non ripetibile all'inquilino
    manutenzione: float = 800.0
    assicurazione: float = 250.0
    gestione: float = 0.0  # compenso dell'agenzia di gestione in % del canone incassato
    aliquota_imu: float = 0.0106
    inflazione: float = 0.02


@dataclass(frozen=True)
class Mutuo:
    """Finanziamento con piano di ammortamento alla francese (rate mensili)."""

    ltv: float = 0.0  # quota del prezzo finanziata
    tasso: float = 0.032
    durata_anni: int = 25
    spese_istruttoria: float = 1_000.0
    perizia: float = 300.0

    @property
    def attivo(self) -> bool:
        return self.ltv > 0


@dataclass(frozen=True)
class Scenario:
    """Orizzonte, rivalutazione e tasso di attualizzazione."""

    orizzonte: int = 10
    crescita_valore: float = 0.02
    costi_vendita: float = 0.03  # provvigione e spese in % del prezzo di vendita
    tasso_sconto: float = 0.06  # rendimento minimo richiesto sul capitale proprio


@dataclass(frozen=True)
class Investimento:
    """Insieme completo delle ipotesi di un investimento immobiliare."""

    acquisto: Acquisto
    locazione: Locazione
    spese: Spese = field(default_factory=Spese)
    mutuo: Mutuo = field(default_factory=Mutuo)
    scenario: Scenario = field(default_factory=Scenario)
    nome: str = "Immobile"

    def con(self, **modifiche: Any) -> Investimento:
        """Copia con alcune ipotesi cambiate, indicate come ``sezione__campo``.

        Esempio: ``inv.con(acquisto__prezzo=280_000, mutuo__ltv=0)``.
        """
        sezioni: dict[str, dict[str, Any]] = {}
        semplici: dict[str, Any] = {}
        for chiave, valore in modifiche.items():
            if "__" in chiave:
                sezione, campo = chiave.split("__", 1)
                sezioni.setdefault(sezione, {})[campo] = valore
            else:
                semplici[chiave] = valore
        for sezione, valori in sezioni.items():
            semplici[sezione] = replace(getattr(self, sezione), **valori)
        return replace(self, **semplici)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Investimento:
        classi = {"acquisto": Acquisto, "locazione": Locazione, "spese": Spese, "mutuo": Mutuo,
                  "scenario": Scenario}
        nomi_validi = {f.name for f in fields(cls)}
        sconosciute = set(d) - nomi_validi
        if sconosciute:
            raise ValueError(f"Sezioni non riconosciute: {', '.join(sorted(sconosciute))}")
        kwargs: dict[str, Any] = {"nome": d.get("nome", "Immobile")}
        for nome, classe in classi.items():
            if nome in d:
                kwargs[nome] = classe(**d[nome])
        return cls(**kwargs)


def load_toml(path: str | Path) -> Investimento:
    """Legge le ipotesi da un file TOML con sezioni [acquisto], [locazione], [spese], [mutuo], [scenario]."""
    with open(path, "rb") as f:
        return Investimento.from_dict(tomllib.load(f))


def esempio_milano() -> Investimento:
    """Bilocale di 60 m² a Milano, acquistato da privato, ristrutturato e finanziato al 60%."""
    return Investimento(
        nome="Bilocale Milano, zona Città Studi",
        acquisto=Acquisto(prezzo=280_000, rendita_catastale=950, agenzia=0.03, notaio=2_800,
                          ristrutturazione=20_000, arredo=8_000, valore_mercato=315_000),
        locazione=Locazione(canone_mensile=1_300, crescita_canone=0.02, sfitto=0.04),
        spese=Spese(condominio=700, manutenzione=900, assicurazione=250, aliquota_imu=0.0106),
        mutuo=Mutuo(ltv=0.60, tasso=0.030, durata_anni=25),
        scenario=Scenario(orizzonte=10, crescita_valore=0.02, costi_vendita=0.03, tasso_sconto=0.05),
    )
