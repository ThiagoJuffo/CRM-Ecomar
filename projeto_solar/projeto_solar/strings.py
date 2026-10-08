"""Dimensionamento de strings: quantos módulos em série e em paralelo por MPPT."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .modelos import Inversor, Modulo


@dataclass
class CondicoesLocais:
    temp_min_c: float = 5.0  # menor temperatura ambiente registrada no local
    temp_max_amb_c: float = 38.0
    acrescimo_celula_c: float = 30.0  # célula acima do ambiente, sol pleno em telhado


@dataclass
class LimitesString:
    voc_tmin: float  # Voc do módulo na temperatura mínima
    vmp_tmin: float
    vmp_tmax: float  # Vmp do módulo na temperatura máxima de célula
    n_min: int
    n_max: int
    motivo_n_max: str


@dataclass
class Mppt:
    inversor: int  # índice do inversor (1, 2, ...)
    numero: int  # MPPT dentro do inversor (1, 2, ...)
    plano: str | None = None
    strings: int = 0
    modulos_por_string: int = 0

    @property
    def modulos(self) -> int:
        return self.strings * self.modulos_por_string

    @property
    def rotulo(self) -> str:
        return f"INV{self.inversor}-MPPT{self.numero}"


@dataclass
class ArranjoEletrico:
    limites: LimitesString
    mppts: list[Mppt]
    modulos_disponiveis: dict[str, int]
    alertas: list[str] = field(default_factory=list)

    @property
    def modulos_usados(self) -> int:
        return sum(m.modulos for m in self.mppts)

    def potencia_cc_w(self, modulo: Modulo) -> float:
        return self.modulos_usados * modulo.potencia_w


def limites_da_string(modulo: Modulo, inv: Inversor, cond: CondicoesLocais) -> LimitesString:
    t_cel_max = cond.temp_max_amb_c + cond.acrescimo_celula_c
    voc_tmin = modulo.voc * (1 + modulo.coef_voc / 100 * (cond.temp_min_c - 25))
    # Vmp varia aproximadamente com o coeficiente de Pmax (a corrente quase não muda)
    vmp_tmin = modulo.vmp * (1 + modulo.coef_pmax / 100 * (cond.temp_min_c - 25))
    vmp_tmax = modulo.vmp * (1 + modulo.coef_pmax / 100 * (t_cel_max - 25))

    candidatos = {
        "tensão CC máxima do inversor (Voc a frio)": math.floor(inv.vcc_max / voc_tmin),
        "tensão máxima do sistema do módulo": math.floor(modulo.tensao_max_sistema_v / voc_tmin),
        "limite superior do MPPT (Vmp a frio)": math.floor(inv.vmppt_max / vmp_tmin),
    }
    motivo, n_max = min(candidatos.items(), key=lambda kv: kv[1])
    n_min = math.ceil(max(inv.vmppt_min, inv.vpartida) / vmp_tmax)
    return LimitesString(voc_tmin, vmp_tmin, vmp_tmax, n_min, n_max, motivo)


def _opcoes_por_mppt(modulo: Modulo, inv: Inversor, lim: LimitesString) -> list[tuple[int, int]]:
    """(strings, módulos por string) válidos para um MPPT, incluindo vazio."""
    opcoes = [(0, 0)]
    # cada MPPT recebe no máximo sua fração da potência CC máxima do inversor,
    # o que distribui a carga entre MPPTs e entre inversores
    potencia_max_mppt = inv.potencia_cc_max_w / inv.n_mppt
    for s in range(1, inv.strings_por_mppt + 1):
        # Acima da Imp máx. o inversor só limita a corrente; o limite rígido é a Isc máx.
        if s * modulo.isc > inv.isc_max_por_mppt:
            continue
        for n in range(lim.n_min, lim.n_max + 1):
            if s * n * modulo.potencia_w <= potencia_max_mppt:
                opcoes.append((s, n))
    return opcoes


def _melhor_combinacao(n_disp: int, mppts: int, opcoes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Mochila: escolhe uma opção por MPPT maximizando módulos usados (<= n_disp).
    Desempate: menos strings, depois strings de tamanho igual."""
    # estado: módulos usados -> (n_strings, escolhas)
    estados: dict[int, tuple[int, list[tuple[int, int]]]] = {0: (0, [])}
    for _ in range(mppts):
        novos: dict[int, tuple[int, list[tuple[int, int]]]] = {}
        for usados, (n_str, escolhas) in estados.items():
            for s, n in opcoes:
                total = usados + s * n
                if total > n_disp:
                    continue
                cand = (n_str + s, escolhas + [(s, n)])
                atual = novos.get(total)
                if atual is None or _melhor(cand, atual):
                    novos[total] = cand
        estados = novos
    melhor_total = max(estados)
    return estados[melhor_total][1]


def _melhor(a, b) -> bool:
    """Menos strings; depois strings de tamanhos parecidos; depois menos tamanhos distintos."""
    if a[0] != b[0]:
        return a[0] < b[0]

    def dispersao(escolhas):
        tamanhos = [n for s, n in escolhas if s]
        return (max(tamanhos) - min(tamanhos)) if tamanhos else 0

    if dispersao(a[1]) != dispersao(b[1]):
        return dispersao(a[1]) < dispersao(b[1])
    return len({n for s, n in a[1] if s}) < len({n for s, n in b[1] if s})


def dimensionar(modulo: Modulo, inv: Inversor, quantidade_inversores: int,
                modulos_por_plano: dict[str, int], cond: CondicoesLocais) -> ArranjoEletrico:
    """Distribui os MPPTs entre os planos (nunca mistura orientações no mesmo MPPT)
    e escolhe a configuração de strings que aproveita mais módulos."""
    lim = limites_da_string(modulo, inv, cond)
    alertas: list[str] = []
    if lim.n_min > lim.n_max:
        raise ValueError(
            f"Módulo e inversor incompatíveis: string mínima de {lim.n_min} módulos "
            f"é maior que a máxima de {lim.n_max} ({lim.motivo_n_max})."
        )

    mppts = [Mppt(inversor=i + 1, numero=j + 1)
             for i in range(quantidade_inversores) for j in range(inv.n_mppt)]
    planos = sorted((p for p, n in modulos_por_plano.items() if n >= lim.n_min),
                    key=lambda p: -modulos_por_plano[p])
    ignorados = [p for p, n in modulos_por_plano.items() if 0 < n < lim.n_min]
    for p in ignorados:
        alertas.append(f"{p}: só cabem {modulos_por_plano[p]} módulos, abaixo da string mínima "
                       f"({lim.n_min}); plano não utilizado.")
    if len(planos) > len(mppts):
        for p in planos[len(mppts):]:
            alertas.append(f"{p}: sem MPPT livre; plano não utilizado (aumente inversores).")
        planos = planos[:len(mppts)]

    # MPPTs proporcionais à quantidade de módulos de cada plano (mínimo 1 por plano)
    alocacao = {p: 1 for p in planos}
    livres = len(mppts) - len(planos)
    while livres > 0 and planos:
        p = max(planos, key=lambda q: modulos_por_plano[q] / alocacao[q])
        alocacao[p] += 1
        livres -= 1

    opcoes = _opcoes_por_mppt(modulo, inv, lim)
    idx = 0
    for p in planos:
        escolha = _melhor_combinacao(modulos_por_plano[p], alocacao[p], opcoes)
        for s, n in sorted(escolha, reverse=True):  # MPPTs usados primeiro
            m = mppts[idx]
            m.plano, m.strings, m.modulos_por_string = p, s, n
            idx += 1

    arranjo = ArranjoEletrico(lim, mppts, dict(modulos_por_plano), alertas)
    _verificar(arranjo, modulo, inv, quantidade_inversores)
    return arranjo


def _verificar(arr: ArranjoEletrico, modulo: Modulo, inv: Inversor, qtd_inv: int) -> None:
    for m in arr.mppts:
        if m.strings and m.strings * modulo.imp > inv.imp_max_por_mppt:
            arr.alertas.append(
                f"{m.rotulo}: corrente de operação {m.strings * modulo.imp:.1f} A acima de "
                f"{inv.imp_max_por_mppt} A; haverá limitação (clipping) de corrente.")
    for i in range(1, qtd_inv + 1):
        pcc = sum(m.modulos for m in arr.mppts if m.inversor == i) * modulo.potencia_w
        if pcc > inv.potencia_cc_max_w:
            arr.alertas.append(f"INV{i}: potência CC {pcc / 1000:.2f} kWp acima do máximo "
                               f"do inversor ({inv.potencia_cc_max_w / 1000:.2f} kWp).")
        razao = pcc / inv.potencia_ca_w
        if pcc and not 0.8 <= razao <= 1.5:
            arr.alertas.append(f"INV{i}: relação CC/CA {razao:.2f} fora da faixa usual (0,80 a 1,50).")
    sobra = sum(arr.modulos_disponiveis.values()) - arr.modulos_usados
    if sobra:
        arr.alertas.append(f"{sobra} módulo(s) que cabem no telhado ficaram fora das strings.")
