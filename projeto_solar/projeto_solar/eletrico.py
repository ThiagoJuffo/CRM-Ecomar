"""Cabos e proteções (critérios simplificados da NBR 16690 e NBR 5410).

Os valores servem de pré-dimensionamento e precisam da revisão do responsável técnico.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .modelos import Inversor, Modulo
from .strings import ArranjoEletrico

RESISTIVIDADE_CU = 0.0225  # ohm.mm²/m, cobre perto de 70 °C

# Cabo solar flexível 1,8 kV CC, eletroduto em telhado (valores conservadores)
AMPACIDADE_CC = {4: 41, 6: 53, 10: 73, 16: 98}
# NBR 5410 tab. 36, método B1, PVC 70 °C: 2 condutores carregados / 3 carregados
AMPACIDADE_CA_2 = {2.5: 24, 4: 32, 6: 41, 10: 57, 16: 76, 25: 101, 35: 125, 50: 151, 70: 192, 95: 232}
AMPACIDADE_CA_3 = {2.5: 21, 4: 28, 6: 36, 10: 50, 16: 68, 25: 89, 35: 110, 50: 134, 70: 171, 95: 207}
DISJUNTORES = [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160]
FUSIVEIS_PV = [10, 12, 15, 16, 20, 25, 30, 32]


@dataclass
class ParametrosEletricos:
    comprimento_cc_m: float = 25.0  # string até o inversor (ida)
    comprimento_ca_m: float = 15.0  # inversor até o quadro de conexão
    queda_max_cc_pct: float = 1.0
    queda_max_ca_pct: float = 2.0


@dataclass
class CircuitoCC:
    mppt: str
    strings: int
    modulos_por_string: int
    voc_max_v: float
    vmp_v: float
    corrente_projeto_a: float  # 1,25 x Isc
    secao_mm2: int
    queda_pct: float
    fusivel_a: int | None
    dps_ucpv_v: int
    seccionadora_v: int
    seccionadora_a: int


@dataclass
class CircuitoCA:
    inversor: str
    potencia_w: float
    fases: int
    tensao_v: float
    corrente_a: float
    disjuntor_a: int
    secao_mm2: float
    queda_pct: float
    dps_uc_v: int


@dataclass
class ProjetoEletrico:
    cc: list[CircuitoCC] = field(default_factory=list)
    ca: list[CircuitoCA] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)


def _queda_cc(l: float, i: float, s: float, v: float) -> float:
    return 2 * l * i * RESISTIVIDADE_CU / s / v * 100


def _queda_ca(l: float, i: float, s: float, v: float, fases: int) -> float:
    fator = math.sqrt(3) if fases == 3 else 2
    return fator * l * i * RESISTIVIDADE_CU / s / v * 100


def dimensionar_cc(arr: ArranjoEletrico, modulo: Modulo, p: ParametrosEletricos,
                   proj: ProjetoEletrico) -> None:
    for m in arr.mppts:
        if not m.strings:
            continue
        voc_max = arr.limites.voc_tmin * m.modulos_por_string
        vmp = modulo.vmp * m.modulos_por_string
        i_proj = 1.25 * modulo.isc
        secao = None
        for s, amp in AMPACIDADE_CC.items():
            if amp >= i_proj and _queda_cc(p.comprimento_cc_m, modulo.imp, s, vmp) <= p.queda_max_cc_pct:
                secao = s
                break
        if secao is None:
            secao = max(AMPACIDADE_CC)
            proj.alertas.append(f"{m.rotulo}: queda de tensão CC acima de {p.queda_max_cc_pct}% "
                                f"mesmo com {secao} mm²; reduza o comprimento.")
        # NBR 16690: fusível de string obrigatório com 3 ou mais strings em paralelo
        fusivel = None
        if m.strings >= 3:
            faixa = [f for f in FUSIVEIS_PV
                     if 1.5 * modulo.isc <= f <= min(2.4 * modulo.isc, modulo.fusivel_serie_max_a)]
            fusivel = faixa[0] if faixa else None
            if fusivel is None:
                proj.alertas.append(f"{m.rotulo}: nenhum fusível padrão atende 1,5 a 2,4 x Isc.")
        dps = next(v for v in (600, 1000, 1100, 1500) if v >= 1.2 * voc_max)
        sec_v = next(v for v in (600, 1000, 1100, 1500) if v >= voc_max)
        sec_a = next(a for a in (16, 25, 32, 40, 63) if a >= 1.25 * modulo.isc * m.strings)
        proj.cc.append(CircuitoCC(
            mppt=m.rotulo, strings=m.strings, modulos_por_string=m.modulos_por_string,
            voc_max_v=round(voc_max, 1), vmp_v=round(vmp, 1), corrente_projeto_a=round(i_proj, 1),
            secao_mm2=secao, queda_pct=round(_queda_cc(p.comprimento_cc_m, modulo.imp, secao, vmp), 2),
            fusivel_a=fusivel, dps_ucpv_v=dps, seccionadora_v=sec_v, seccionadora_a=sec_a,
        ))


def dimensionar_ca(inv: Inversor, quantidade: int, p: ParametrosEletricos,
                   proj: ProjetoEletrico) -> None:
    tabela = AMPACIDADE_CA_3 if inv.fases == 3 else AMPACIDADE_CA_2
    for i in range(1, quantidade + 1):
        corrente = inv.corrente_ca_max_a
        disjuntor = next(d for d in DISJUNTORES if d >= 1.25 * corrente)
        tensao_fase = inv.tensao_ca_v if inv.fases == 1 else inv.tensao_ca_v / math.sqrt(3)
        secao = None
        for s, amp in tabela.items():
            if amp >= disjuntor and _queda_ca(p.comprimento_ca_m, corrente, s, inv.tensao_ca_v,
                                               inv.fases) <= p.queda_max_ca_pct:
                secao = s
                break
        if secao is None:
            secao = max(tabela)
            proj.alertas.append(f"INV{i}: queda de tensão CA acima de {p.queda_max_ca_pct}%.")
        proj.ca.append(CircuitoCA(
            inversor=f"INV{i}", potencia_w=inv.potencia_ca_w, fases=inv.fases,
            tensao_v=inv.tensao_ca_v, corrente_a=corrente, disjuntor_a=disjuntor, secao_mm2=secao,
            queda_pct=round(_queda_ca(p.comprimento_ca_m, corrente, secao, inv.tensao_ca_v, inv.fases), 2),
            dps_uc_v=275 if tensao_fase <= 240 else 440,
        ))


def dimensionar(arr: ArranjoEletrico, modulo: Modulo, inv: Inversor, quantidade_inversores: int,
                p: ParametrosEletricos | None = None) -> ProjetoEletrico:
    p = p or ParametrosEletricos()
    proj = ProjetoEletrico()
    dimensionar_cc(arr, modulo, p, proj)
    dimensionar_ca(inv, quantidade_inversores, p, proj)
    return proj
