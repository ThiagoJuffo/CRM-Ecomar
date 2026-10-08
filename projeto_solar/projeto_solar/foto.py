"""Telhado a partir de foto de drone (ortofoto, vista de cima) com medida de referência.

Cada água é marcada na foto em pixels, começando pelos dois vértices do beiral
(a borda mais baixa). A escala vem de dois pontos com distância conhecida.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon

from .modelos import PlanoTelhado


@dataclass
class Transformacao:
    """Leva coordenadas do plano inclinado (m) de volta para pixels da foto."""

    escala_m_px: float
    origem: np.ndarray  # beiral, em metros no referencial da foto (x leste-foto, y cima-foto)
    u: np.ndarray  # direção ao longo do beiral
    n: np.ndarray  # direção que sobe a inclinação (horizontal)
    cos_inclinacao: float
    deslocamento_x: float

    def para_pixels(self, x: float, y: float) -> tuple[float, float]:
        p = self.origem + (x + self.deslocamento_x) * self.u + y * self.cos_inclinacao * self.n
        return p[0] / self.escala_m_px, -p[1] / self.escala_m_px


def escala(referencia: dict) -> float:
    (x1, y1), (x2, y2) = referencia["p1"], referencia["p2"]
    distancia_px = math.hypot(x2 - x1, y2 - y1)
    if distancia_px < 1:
        raise ValueError("Os dois pontos da medida de referência estão no mesmo lugar")
    return referencia["metros"] / distancia_px


def _orientacao(pts: np.ndarray, azimute_foto: float | None):
    """Direções u (ao longo do beiral) e n (sobe a inclinação) e o ponto de origem.

    Sem azimute, o beiral são os dois primeiros vértices. Com azimute (rumo da queda
    d'água na foto), o beiral é a borda do polígono mais perpendicular a ele.
    """
    if azimute_foto is None:
        p0, p1 = pts[0], pts[1]
        u = (p1 - p0) / np.linalg.norm(p1 - p0)
        n = np.array([-u[1], u[0]])
        if np.dot(pts.mean(axis=0) - p0, n) < 0:  # n precisa apontar para dentro da água
            u, n = -u, -n
        return u, n, p0
    queda = np.array([math.sin(math.radians(azimute_foto)), math.cos(math.radians(azimute_foto))])
    n = -queda
    u = np.array([n[1], -n[0]])
    bordas = [(b - a) / np.linalg.norm(b - a) for a, b in zip(pts, np.roll(pts, -1, axis=0))
              if np.linalg.norm(b - a) > 1e-9]
    borda = max(bordas, key=lambda e: abs(e @ u))
    # o caimento da Solar API é a média da água; as paredes marcadas são mais confiáveis
    if abs(borda @ u) >= math.cos(math.radians(35)):  # alinha com a parede real
        u = borda if borda @ u > 0 else -borda
        n = np.array([-u[1], u[0]])
    return u, n, pts[np.argmin(pts @ n)]


def plano_da_foto(d: dict, escala_m_px: float, norte_graus: float = 0.0,
                  azimute: float | None = None, inclinacao: float | None = None) -> PlanoTelhado:
    """Converte uma água marcada em pixels para o plano inclinado em metros.

    azimute/inclinacao, quando passados (ex.: medidos pela Solar API), substituem o
    beiral marcado e a inclinação informada.
    """
    pts = np.array([(x * escala_m_px, -y * escala_m_px) for x, y in d["poligono_px"]])
    if len(pts) < 3:
        raise ValueError(f"{d['nome']}: o polígono precisa de pelo menos 3 vértices")
    u, n, p0 = _orientacao(pts, None if azimute is None else azimute + norte_graus)

    informada = d.get("inclinacao")
    if inclinacao is None:
        inclinacao = informada
    cos_i = math.cos(math.radians(inclinacao or 0.0))

    def local(p):
        v = np.asarray(p) - p0
        return float(np.dot(v, u)), float(np.dot(v, n)) / cos_i

    poligono = Polygon([local(p) for p in pts])
    desloc = poligono.bounds[0]
    poligono = translate(poligono, -desloc, 0)
    obstaculos = []
    for o in d.get("obstaculos_px", []):
        o_m = [(x * escala_m_px, -y * escala_m_px) for x, y in o]
        obstaculos.append(translate(Polygon([local(p) for p in o_m]), -desloc, 0))

    # azimute da queda d'água (-n), corrigido pela direção do norte na foto
    rumo_foto = math.degrees(math.atan2(-n[0], -n[1]))
    plano = PlanoTelhado(
        nome=d["nome"],
        inclinacao_graus=round(inclinacao, 1) if inclinacao is not None else 0.0,
        azimute_graus=round((rumo_foto - norte_graus) % 360, 1),
        poligono=poligono,
        obstaculos=obstaculos,
        horas_sol_ano=d.get("horas_sol_ano"),
        origem="foto",
    )
    plano.transformacao = Transformacao(escala_m_px, p0, u, n, cos_i, desloc)
    plano.inclinacao_informada = informada is not None
    plano.fonte_foto = (d, escala_m_px, norte_graus)
    return plano


def planos_da_foto(telhado: dict) -> list[PlanoTelhado]:
    s = escala(telhado["referencia"])
    return [plano_da_foto(p, s, telhado.get("norte_graus", 0.0)) for p in telhado["planos"]]


def _diferenca(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def completar_com_solar_api(planos: list[PlanoTelhado], insights: dict) -> list[PlanoTelhado]:
    """Completa as águas da foto com a Solar API: inclinação, insolação e, se o beiral
    marcado não bater com nenhuma água do Google, o caimento medido pela elevação.
    O contorno continua sendo o da foto (mais preciso). Devolve a nova lista."""
    segmentos = insights.get("solarPotential", {}).get("roofSegmentStats", [])
    if not segmentos:
        return planos
    resultado = []
    for p in planos:
        d, escala_m_px, norte = p.fonte_foto
        seg = min(segmentos, key=lambda s: _diferenca(s.get("azimuthDegrees", 0), p.azimute_graus))
        avisos = list(p.observacoes)
        azimute = None
        if _diferenca(seg.get("azimuthDegrees", 0), p.azimute_graus) > 30:
            # beiral marcado provavelmente na borda errada: usa a maior água do Google
            seg = max(segmentos, key=lambda s: s["stats"]["areaMeters2"])
            azimute = seg.get("azimuthDegrees", 0)
            avisos.append(f"O beiral marcado indica caimento para {p.azimute_graus:.0f}°, mas a elevação da "
                          f"Solar API indica {azimute:.0f}°; usado o caimento da Solar API.")
        inclinacao = None if p.inclinacao_informada else seg.get("pitchDegrees", 0.0)
        novo = plano_da_foto(d, escala_m_px, norte, azimute=azimute, inclinacao=inclinacao)
        quantis = seg["stats"].get("sunshineQuantiles") or []
        if novo.horas_sol_ano is None and quantis:
            novo.horas_sol_ano = round(quantis[len(quantis) // 2])
        if inclinacao is not None:
            avisos.append("Inclinação obtida da Solar API; confirmar no local.")
        novo.observacoes = avisos
        resultado.append(novo)
    return resultado


def desenhar_sobreposicao(paginacoes, caminho_foto: str, caminho: Path) -> Path:
    """Foto do drone com as águas, obstáculos e módulos desenhados por cima."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon

    img = plt.imread(caminho_foto)
    altura, largura = img.shape[:2]
    fig, ax = plt.subplots(figsize=(16.5, 16.5 * altura / largura))
    ax.imshow(img)
    cores = plt.get_cmap("tab10")
    chaves: dict[str, int] = {}
    for pag in paginacoes:
        t = getattr(pag.plano, "transformacao", None)
        if t is None:
            continue

        def px(geom):
            return [t.para_pixels(x, y) for x, y in geom.exterior.coords]

        ax.add_patch(MplPolygon(px(pag.plano.poligono), fill=False, ec="yellow", lw=2))
        for o in pag.plano.obstaculos:
            ax.add_patch(MplPolygon(px(o), fc="red", alpha=0.35, ec="red"))
        for i, m in enumerate(pag.modulos):
            rotulo = pag.rotulos[i] if i < len(pag.rotulos) else ""
            chave = rotulo.rsplit(".", 1)[0]
            cor = cores(chaves.setdefault(chave, len(chaves)) % 10)
            ax.add_patch(MplPolygon(px(m), fc=cor, alpha=0.45, ec="white", lw=0.8))
        cx, cy = t.para_pixels(*pag.plano.poligono.centroid.coords[0])
        ax.text(cx, cy, f"{pag.plano.nome}\n{pag.quantidade} mód.", color="white", ha="center",
                va="center", fontsize=11, weight="bold",
                bbox={"facecolor": "black", "alpha": 0.5, "pad": 3})
    ax.set_axis_off()
    ax.set_title("Sobreposição dos módulos na foto (conferência)")
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho
