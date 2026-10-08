"""Marcação automática do telhado com as camadas de dados da Solar API.

Usa o modelo de superfície (DSM), a máscara de telhado, a foto aérea e o mapa de
insolação (todos em UTM, ~0,25 m/pixel) para:
- separar as águas como planos contínuos de elevação (crescimento de região);
- ficar só com o prédio do ponto informado (águas encostadas e na mesma altura);
- detectar módulos já instalados (áreas escuras) e tratá-los como obstáculo.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from scipy import ndimage as ndi
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from . import solar_api
from .foto import Transformacao
from .modelos import PlanoTelhado

DATA_LAYERS_URL = "https://solar.googleapis.com/v1/dataLayers:get"
logging.getLogger("tifffile").setLevel(logging.ERROR)


@dataclass
class Camadas:
    dsm: np.ndarray
    mascara: np.ndarray
    rgb: np.ndarray
    fluxo: np.ndarray | None
    pixel_m: float
    semente: tuple[int, int]  # linha, coluna do ponto da obra
    data_imagem: dict | None = None
    qualidade: str | None = None


# ----------------------------------------------------------------- download

def _ler_tiff(conteudo: bytes) -> tuple[np.ndarray, tuple]:
    import io

    import tifffile
    with tifffile.TiffFile(io.BytesIO(conteudo)) as t:
        dados = t.asarray()
        transf = t.pages[0].tags["ModelTransformationTag"].value
    return dados, transf


def latlng_para_utm(lat: float, lng: float) -> tuple[float, float]:
    """Projeção UTM (WGS84) pela série de Krüger; erro de milímetros."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    zona = int((lng + 180) // 6) + 1
    lng0 = math.radians((zona - 1) * 6 - 180 + 3)
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    alfa = [n / 2 - 2 * n ** 2 / 3 + 5 * n ** 3 / 16, 13 * n ** 2 / 48 - 3 * n ** 3 / 5, 61 * n ** 3 / 240]
    fi, lam = math.radians(lat), math.radians(lng) - lng0
    t = math.sinh(math.atanh(math.sin(fi)) - 2 * math.sqrt(n) / (1 + n) * math.atanh(2 * math.sqrt(n) / (1 + n) * math.sin(fi)))
    xi, eta = math.atan2(t, math.cos(lam)), math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    E = 500000 + k0 * A * (eta + sum(al * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, al in enumerate(alfa, 1)))
    N = k0 * A * (xi + sum(al * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, al in enumerate(alfa, 1)))
    if lat < 0:
        N += 10_000_000
    return E, N


def baixar_camadas(lat: float, lng: float, chave: str | None = None, raio_m: float = 40,
                   qualidade: str = "LOW") -> Camadas:
    chave = solar_api._chave(chave)
    resp = requests.get(DATA_LAYERS_URL, params={
        "location.latitude": f"{lat:.7f}", "location.longitude": f"{lng:.7f}",
        "radiusMeters": raio_m, "view": "IMAGERY_AND_ANNUAL_FLUX_LAYERS",
        "requiredQuality": qualidade, "pixelSizeMeters": 0.25, "key": chave,
    }, timeout=60)
    if not resp.ok:
        raise solar_api.ErroSolarApi(f"dataLayers respondeu {resp.status_code}: {resp.text[:200]}")
    info = resp.json()

    def baixar(url):
        r = requests.get(url, params={"key": chave}, timeout=120)
        r.raise_for_status()
        return _ler_tiff(r.content)

    dsm, transf = baixar(info["dsmUrl"])
    mascara, _ = baixar(info["maskUrl"])
    rgb, _ = baixar(info["rgbUrl"])
    fluxo = baixar(info["annualFluxUrl"])[0] if info.get("annualFluxUrl") else None
    pixel_m, x0, y0 = transf[0], transf[3], transf[7]
    E, N = latlng_para_utm(lat, lng)
    semente = (int(round((y0 - N) / pixel_m)), int(round((E - x0) / pixel_m)))
    return Camadas(dsm.astype(float), mascara > 0, rgb, fluxo, pixel_m, semente,
                   info.get("imageryDate"), info.get("imageryQuality"))


# ----------------------------------------------------------------- análise

def _ajustar_plano(z, E, N, sel):
    A = np.c_[E[sel], N[sel], np.ones(int(sel.sum()))]
    coef, *_ = np.linalg.lstsq(A, z[sel], rcond=None)
    return coef


def _crescer(z, E, N, livre, semente, raio_px=8, tol_m=0.25):
    """Cresce uma região plana a partir da semente: ajusta o plano, pega os pixels
    conectados com resíduo pequeno e repete até estabilizar."""
    r, c = semente
    rr, cc = np.ogrid[: z.shape[0], : z.shape[1]]
    sel = livre & ((rr - r) ** 2 + (cc - c) ** 2 <= raio_px ** 2)
    if sel.sum() < 20:
        return None, None
    for _ in range(6):
        coef = _ajustar_plano(z, E, N, sel)
        candidatos = livre & (np.abs(z - (coef[0] * E + coef[1] * N + coef[2])) < tol_m)
        rotulos, _ = ndi.label(candidatos)
        if rotulos[r, c] == 0:
            return None, None
        novo = rotulos == rotulos[r, c]
        aberto = ndi.binary_opening(novo)
        novo = aberto if aberto[r, c] else novo
        if novo.sum() == sel.sum():
            break
        sel = novo
    return sel, _ajustar_plano(z, E, N, sel)


def segmentar_aguas(cam: Camadas, area_min_m2: float = 10.0) -> list[dict]:
    """Divide o telhado que contém o ponto da obra em águas planas."""
    H, W = cam.mascara.shape
    px = cam.pixel_m
    rotulos, _ = ndi.label(cam.mascara)
    r, c = cam.semente
    r, c = min(max(r, 0), H - 1), min(max(c, 0), W - 1)
    if rotulos[r, c] == 0:  # ponto caiu fora do telhado: usa o pixel de telhado mais próximo
        _, (ir, ic) = ndi.distance_transform_edt(rotulos == 0, return_indices=True)
        r, c = ir[r, c], ic[r, c]
    componente = rotulos == rotulos[r, c]
    z = ndi.median_filter(cam.dsm, 3)
    rr, cc = np.mgrid[0:H, 0:W]
    E, N = cc * px, -rr * px

    livre = componente.copy()
    aguas: list[dict] = []
    proxima = (r, c)
    for _ in range(20):
        regiao, coef = _crescer(z, E, N, livre, proxima)
        if regiao is not None and regiao.sum() * px * px >= area_min_m2:
            gE, gN = coef[0], coef[1]
            aguas.append({
                "mascara": regiao,
                "inclinacao": math.degrees(math.atan(math.hypot(gE, gN))),
                "azimute": (math.degrees(math.atan2(-gE, -gN)) + 360) % 360,
                "altura": float(np.median(z[regiao])),
                "contem_ponto": bool(regiao[r, c]),
            })
            livre &= ~regiao
        else:
            livre[proxima] = False
        distancia = ndi.distance_transform_edt(livre)
        if distancia.max() < 4:
            break
        proxima = np.unravel_index(np.argmax(distancia), distancia.shape)
    return aguas


def aguas_do_predio(aguas: list[dict], pixel_m: float, desnivel_max_m: float = 1.0) -> list[dict]:
    """Fica com a água do ponto e as águas encostadas nela na mesma altura
    (descarta prédios vizinhos ligados na máscara do Google)."""
    base = next((a for a in aguas if a["contem_ponto"]), None)
    if base is None:
        return aguas[:1]
    escolhidas = [base]
    vizinhanca = ndi.binary_dilation(base["mascara"], iterations=max(1, int(1.0 / pixel_m)))
    for a in aguas:
        if a is base:
            continue
        if (a["mascara"] & vizinhanca).any() and abs(a["altura"] - base["altura"]) <= desnivel_max_m:
            escolhidas.append(a)
    return escolhidas


def detectar_modulos_existentes(rgb: np.ndarray, regiao: np.ndarray, pixel_m: float,
                                area_min_m2: float = 4.0) -> np.ndarray:
    """Módulos já instalados aparecem como blocos bem mais escuros que o telhado."""
    lum = rgb[..., :3].astype(float).mean(axis=2)
    referencia = np.median(lum[regiao]) if regiao.any() else 128
    escuro = regiao & (lum < min(90, 0.5 * referencia))
    escuro = ndi.binary_closing(escuro, iterations=2)
    escuro = ndi.binary_opening(escuro, iterations=1)
    rotulos, n = ndi.label(escuro)
    if not n:
        return escuro
    areas = ndi.sum(escuro, rotulos, range(1, n + 1)) * pixel_m * pixel_m
    grandes = np.isin(rotulos, 1 + np.flatnonzero(areas >= area_min_m2))
    return ndi.binary_closing(grandes, iterations=3)


def _mascara_para_poligono(m: np.ndarray, pixel_m: float, simplificar_m: float = 0.3):
    """Contorno de uma máscara em metros (x = coluna, y = -linha)."""
    caixas = []
    for linha in range(m.shape[0]):
        cols = np.flatnonzero(m[linha])
        if not len(cols):
            continue
        quebras = np.flatnonzero(np.diff(cols) > 1)
        inicios = np.r_[cols[0], cols[quebras + 1]]
        fins = np.r_[cols[quebras], cols[-1]]
        for c0, c1 in zip(inicios, fins):
            caixas.append(box(c0 * pixel_m, -(linha + 1) * pixel_m, (c1 + 1) * pixel_m, -linha * pixel_m))
    if not caixas:
        return None
    geom = unary_union(caixas).simplify(simplificar_m)
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def _eixo_principal(m: np.ndarray) -> np.ndarray:
    """Direção do maior eixo da água (análise de componentes principais da máscara)."""
    r, c = np.nonzero(m)
    pts = np.c_[c, -r].astype(float)
    pts -= pts.mean(axis=0)
    _, vetores = np.linalg.eigh(np.cov(pts.T))
    return vetores[:, -1]


def _para_plano(nome: str, poligono_h: Polygon, obstaculos_h: list[Polygon], inclinacao: float,
                azimute: float, pixel_m: float, eixos: list[np.ndarray] | None = None) -> PlanoTelhado:
    """Leva o polígono horizontal (m, norte para cima) para o plano inclinado."""
    queda = np.array([math.sin(math.radians(azimute)), math.cos(math.radians(azimute))])
    n = -queda  # sobe a inclinação
    u = np.array([n[1], -n[0]])  # ao longo da cumeeira, (u, n) com mesma orientação de (x, y)
    # O beiral real é paralelo a uma parede do prédio: alinha u com o eixo da água
    # (ou o perpendicular) mais próximo da direção calculada pela elevação (até 20°).
    bordas = []
    for e in eixos or []:
        e = e / np.linalg.norm(e)
        bordas += [e, np.array([-e[1], e[0]])]
    if bordas:
        borda = max(bordas, key=lambda e: abs(e @ u))
        if abs(borda @ u) >= math.cos(math.radians(20)):
            borda = borda if borda @ u > 0 else -borda
            u, n = borda, np.array([-borda[1], borda[0]])
            azimute = (math.degrees(math.atan2(-n[0], -n[1])) + 360) % 360
    cos_i = math.cos(math.radians(inclinacao))
    pts = np.array(poligono_h.exterior.coords)
    origem = pts[np.argmin(pts @ n)]  # ponto mais baixo: y começa em 0

    def local(geom):
        ext = [(float((p - origem) @ u), float((p - origem) @ n) / cos_i) for p in np.array(geom.exterior.coords)]
        furos = [[(float((p - origem) @ u), float((p - origem) @ n) / cos_i) for p in np.array(i.coords)]
                 for i in geom.interiors]
        return Polygon(ext, furos)

    poligono = local(poligono_h)
    desloc = poligono.bounds[0]
    poligono = translate(poligono, -desloc, 0)
    obstaculos = [translate(local(o), -desloc, 0) for o in obstaculos_h]
    plano = PlanoTelhado(nome=nome, inclinacao_graus=round(inclinacao, 1), azimute_graus=round(azimute, 1),
                         poligono=poligono, obstaculos=obstaculos, origem="solar_api_auto")
    plano.transformacao = Transformacao(pixel_m, origem, u, n, cos_i, desloc)
    return plano


def planos_automaticos(cam: Camadas, area_min_m2: float = 10.0) -> list[PlanoTelhado]:
    aguas = aguas_do_predio(segmentar_aguas(cam, area_min_m2), cam.pixel_m)
    predio = np.zeros_like(cam.mascara)
    for a in aguas:
        predio |= a["mascara"]
    existentes = detectar_modulos_existentes(cam.rgb, predio, cam.pixel_m)
    planos = []
    for i, a in enumerate(sorted(aguas, key=lambda a: -a["mascara"].sum()), 1):
        poligono = _mascara_para_poligono(a["mascara"], cam.pixel_m)
        if poligono is None or poligono.area < area_min_m2 * math.cos(math.radians(a["inclinacao"])):
            continue
        obst = _mascara_para_poligono(existentes & ndi.binary_dilation(a["mascara"], iterations=2),
                                      cam.pixel_m, simplificar_m=0.2)
        obstaculos = []
        if obst is not None and obst.intersects(poligono):
            obstaculos = [obst.buffer(0.1)]
        eixos = [_eixo_principal(a["mascara"])]
        plano = _para_plano(f"Água {i}", poligono, obstaculos, a["inclinacao"], a["azimute"], cam.pixel_m, eixos)
        if cam.fluxo is not None:
            valores = cam.fluxo[a["mascara"]]
            valores = valores[np.isfinite(valores) & (valores > 0)]
            if len(valores):
                plano.horas_sol_ano = round(float(np.median(valores)))
        plano.observacoes.append("Contorno e inclinação detectados automaticamente pela elevação "
                                 "da Solar API: conferir na visita técnica.")
        if obstaculos:
            plano.observacoes.append(f"{plano.nome}: módulos já existentes detectados na imagem e "
                                     "excluídos da paginação.")
        planos.append(plano)
    return planos


def salvar_foto(cam: Camadas, caminho: Path) -> Path:
    from PIL import Image
    Image.fromarray(cam.rgb[..., :3].astype(np.uint8)).save(caminho)
    return caminho
