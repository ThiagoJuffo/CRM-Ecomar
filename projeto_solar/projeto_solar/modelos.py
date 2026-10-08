"""Estruturas de dados do projeto: módulos, inversores, planos de telhado."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import Polygon

CATALOGO_DIR = Path(__file__).parent / "catalogo"


@dataclass
class Modulo:
    id: str
    fabricante: str
    modelo: str
    potencia_w: float
    voc: float  # tensão de circuito aberto (V) em STC
    vmp: float  # tensão de máxima potência (V) em STC
    isc: float  # corrente de curto-circuito (A) em STC
    imp: float  # corrente de máxima potência (A) em STC
    coef_voc: float  # coeficiente de temperatura de Voc (%/°C), negativo
    coef_pmax: float  # coeficiente de temperatura de Pmax (%/°C), negativo
    comprimento_m: float
    largura_m: float
    fusivel_serie_max_a: float = 25.0
    tensao_max_sistema_v: float = 1500.0


@dataclass
class Inversor:
    id: str
    fabricante: str
    modelo: str
    potencia_ca_w: float
    potencia_cc_max_w: float
    vcc_max: float  # tensão CC máxima de entrada (V)
    vmppt_min: float
    vmppt_max: float
    vpartida: float
    n_mppt: int
    strings_por_mppt: int
    imp_max_por_mppt: float  # corrente máxima de operação por MPPT (A)
    isc_max_por_mppt: float  # corrente máxima de curto-circuito por MPPT (A)
    fases: int  # 1 = monofásico, 3 = trifásico
    tensao_ca_v: float  # tensão de linha (trifásico) ou fase-neutro (monofásico)
    corrente_ca_max_a: float


@dataclass
class PlanoTelhado:
    """Uma água do telhado, em coordenadas locais no próprio plano inclinado.

    Eixo x: horizontal, ao longo da cumeeira. Eixo y: sobe pela inclinação.
    """

    nome: str
    inclinacao_graus: float
    azimute_graus: float  # 0 = norte, 90 = leste, sentido horário
    poligono: Polygon
    obstaculos: list[Polygon] = field(default_factory=list)
    horas_sol_ano: float | None = None  # kWh/kWp/ano estimado pela Solar API
    origem: str = "manual"
    observacoes: list[str] = field(default_factory=list)
    transformacao: object | None = None  # volta do plano para a foto (origem "foto")
    inclinacao_informada: bool = True


def _carregar(nome_arquivo: str) -> list[dict]:
    return json.loads((CATALOGO_DIR / nome_arquivo).read_text(encoding="utf-8"))


def carregar_modulo(id_: str) -> Modulo:
    for item in _carregar("modulos.json"):
        if item["id"] == id_:
            return Modulo(**item)
    raise KeyError(f"Módulo '{id_}' não está no catálogo")


def carregar_inversor(id_: str) -> Inversor:
    for item in _carregar("inversores.json"):
        if item["id"] == id_:
            return Inversor(**item)
    raise KeyError(f"Inversor '{id_}' não está no catálogo")


def plano_de_dict(d: dict) -> PlanoTelhado:
    return PlanoTelhado(
        nome=d["nome"],
        inclinacao_graus=d.get("inclinacao", 0.0),
        azimute_graus=d.get("azimute", 0.0),
        poligono=Polygon(d["poligono"]),
        obstaculos=[Polygon(o) for o in d.get("obstaculos", [])],
        horas_sol_ano=d.get("horas_sol_ano"),
        origem="manual",
    )
