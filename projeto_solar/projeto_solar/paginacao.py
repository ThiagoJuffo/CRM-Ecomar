"""Estudo de paginação: encaixa o máximo de módulos em cada plano do telhado."""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely.affinity import translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

from .modelos import Modulo, PlanoTelhado


@dataclass
class ParametrosPaginacao:
    recuo_borda_m: float = 0.30  # afastamento das bordas da água
    afastamento_obstaculo_m: float = 0.30
    folga_entre_modulos_m: float = 0.02  # entre módulos vizinhos na fileira
    folga_entre_fileiras_m: float = 0.02
    passo_busca_m: float = 0.05  # resolução da busca de posição
    orientacoes: tuple[str, ...] = ("retrato", "paisagem")


@dataclass
class Paginacao:
    plano: PlanoTelhado
    orientacao: str
    area_util: Polygon
    modulos: list[Polygon] = field(default_factory=list)
    # string atribuída a cada módulo (preenchido no dimensionamento)
    rotulos: list[str] = field(default_factory=list)
    cabem: int = 0  # quantos couberam no estudo (antes de formar as strings)

    @property
    def quantidade(self) -> int:
        return len(self.modulos)


def area_util(plano: PlanoTelhado, p: ParametrosPaginacao):
    util = plano.poligono.buffer(-p.recuo_borda_m, join_style="mitre")
    if plano.obstaculos:
        obst = unary_union([o.buffer(p.afastamento_obstaculo_m, join_style="mitre")
                            for o in plano.obstaculos])
        util = util.difference(obst)
    return util


def _encaixar(util, w: float, h: float, p: ParametrosPaginacao, deslocamento_y: float) -> list[Polygon]:
    """Preenche fileira por fileira, de baixo para cima; em cada fileira avança da
    esquerda para a direita colocando um módulo sempre que ele cabe inteiro."""
    if util.is_empty:
        return []
    alvo = prep(util)
    minx, miny, maxx, maxy = util.bounds
    modulos = []
    y = miny + deslocamento_y
    while y + h <= maxy + 1e-9:
        x = minx
        colocou_na_fileira = False
        while x + w <= maxx + 1e-9:
            candidato = box(x, y, x + w, y + h)
            if alvo.contains(candidato):
                modulos.append(candidato)
                colocou_na_fileira = True
                x += w + p.folga_entre_modulos_m
            else:
                x += p.passo_busca_m
        y += h + p.folga_entre_fileiras_m if colocou_na_fileira else p.passo_busca_m
    return modulos


def paginar_plano(plano: PlanoTelhado, modulo: Modulo,
                  p: ParametrosPaginacao | None = None) -> Paginacao:
    """Testa cada orientação e vários deslocamentos e fica com a que cabe mais módulos."""
    p = p or ParametrosPaginacao()
    util = area_util(plano, p)
    melhor = Paginacao(plano=plano, orientacao="-", area_util=util)
    for orientacao in p.orientacoes:
        if orientacao == "retrato":
            w, h = modulo.largura_m, modulo.comprimento_m
        else:
            w, h = modulo.comprimento_m, modulo.largura_m
        n_desloc = max(1, int(h / p.passo_busca_m / 4))
        for k in range(n_desloc):
            mods = _encaixar(util, w, h, p, deslocamento_y=k * p.passo_busca_m)
            if len(mods) > melhor.quantidade:
                melhor = Paginacao(plano=plano, orientacao=orientacao, area_util=util, modulos=mods)
    melhor.modulos = _ordenar_serpentina(_centralizar(melhor.modulos, util))
    melhor.cabem = melhor.quantidade
    return melhor


def _centralizar(modulos: list[Polygon], util) -> list[Polygon]:
    """Desloca o conjunto para o centro da área útil, se continuar cabendo."""
    if not modulos:
        return modulos
    alvo = prep(util)
    uminx, uminy, umaxx, umaxy = util.bounds
    xs = [c for m in modulos for c in (m.bounds[0], m.bounds[2])]
    ys = [c for m in modulos for c in (m.bounds[1], m.bounds[3])]
    dx = ((umaxx - max(xs)) - (min(xs) - uminx)) / 2
    dy = ((umaxy - max(ys)) - (min(ys) - uminy)) / 2
    for ddx, ddy in ((dx, dy), (dx, 0), (0, dy)):
        movidos = [translate(m, ddx, ddy) for m in modulos]
        if all(alvo.contains(m) for m in movidos):
            return movidos
    return modulos


def _ordenar_serpentina(modulos: list[Polygon]) -> list[Polygon]:
    fileiras: dict[float, list[Polygon]] = {}
    for m in modulos:
        fileiras.setdefault(round(m.bounds[1], 3), []).append(m)
    ordenados = []
    for i, y in enumerate(sorted(fileiras)):
        fileira = sorted(fileiras[y], key=lambda m: m.bounds[0], reverse=bool(i % 2))
        ordenados.extend(fileira)
    return ordenados
