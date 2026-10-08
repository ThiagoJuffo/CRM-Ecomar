"""Cliente da Google Solar API e conversão dos segmentos de telhado em planos.

A chave é lida da variável de ambiente GOOGLE_MAPS_API_KEY (nunca fica no código).
"""

from __future__ import annotations

import math
import os

import requests
from shapely.geometry import box

from .modelos import PlanoTelhado

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
SOLAR_URL = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
RAIO_TERRA_M = 6_371_000.0


class ErroSolarApi(RuntimeError):
    pass


def _chave(chave: str | None) -> str:
    chave = chave or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not chave:
        raise ErroSolarApi("Defina a variável de ambiente GOOGLE_MAPS_API_KEY")
    return chave


def geocodificar(endereco: str, chave: str | None = None) -> tuple[float, float]:
    resp = requests.get(
        GEOCODE_URL,
        params={"address": endereco, "region": "br", "language": "pt-BR", "key": _chave(chave)},
        timeout=30,
    )
    resp.raise_for_status()
    dados = resp.json()
    if dados.get("status") != "OK" or not dados.get("results"):
        raise ErroSolarApi(f"Endereço não encontrado ({dados.get('status')}): {endereco}")
    loc = dados["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def buscar_edificacao(lat: float, lng: float, chave: str | None = None,
                      qualidade_minima: str = "MEDIUM") -> dict:
    """Chama buildingInsights:findClosest e devolve o JSON bruto."""
    resp = requests.get(
        SOLAR_URL,
        params={
            "location.latitude": f"{lat:.7f}",
            "location.longitude": f"{lng:.7f}",
            "requiredQuality": qualidade_minima,
            "key": _chave(chave),
        },
        timeout=60,
    )
    if resp.status_code == 404:
        raise ErroSolarApi(
            "A Solar API não tem dados deste telhado na qualidade pedida. "
            "Tente qualidade_minima='LOW' ou desenhe o telhado manualmente."
        )
    if not resp.ok:
        raise ErroSolarApi(f"Solar API respondeu {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _bbox_em_metros(bbox: dict) -> tuple[float, float]:
    """Largura (leste-oeste) e altura (norte-sul) em metros de um bounding box lat/lng."""
    sw, ne = bbox["sw"], bbox["ne"]
    lat_media = math.radians((sw["latitude"] + ne["latitude"]) / 2)
    dx = math.radians(ne["longitude"] - sw["longitude"]) * RAIO_TERRA_M * math.cos(lat_media)
    dy = math.radians(ne["latitude"] - sw["latitude"]) * RAIO_TERRA_M
    return abs(dx), abs(dy)


def _dimensoes_do_segmento(seg: dict) -> tuple[float, float]:
    """Estima as dimensões (largura ao longo da cumeeira, comprimento na inclinação)
    do segmento, já no plano inclinado.

    A Solar API só fornece o retângulo envolvente horizontal (alinhado ao norte),
    a área e a orientação. Assumimos uma água retangular girada pelo azimute e
    resolvemos as dimensões que geram aquele retângulo envolvente.
    """
    largura_bb, altura_bb = _bbox_em_metros(seg["boundingBox"])
    az = math.radians(seg.get("azimuthDegrees", 0.0))
    inclinacao = math.radians(seg.get("pitchDegrees", 0.0))
    s, c = abs(math.sin(az)), abs(math.cos(az))
    area_chao = seg["stats"].get("groundAreaMeters2") or seg["stats"]["areaMeters2"] * math.cos(inclinacao)

    # a = projeção horizontal na direção da queda d'água; b = ao longo da cumeeira
    # largura_bb = a*s + b*c ; altura_bb = a*c + b*s
    det = s * s - c * c
    a = b = None
    if abs(det) > 0.2:
        a = (largura_bb * s - altura_bb * c) / det
        b = (altura_bb * s - largura_bb * c) / det
    if not a or not b or a <= 0.5 or b <= 0.5:
        a = b = math.sqrt(area_chao)

    # O retângulo envolvente superestima águas não retangulares: ajusta pela área real.
    if a * b > area_chao:
        k = math.sqrt(area_chao / (a * b))
        a, b = a * k, b * k

    comprimento_inclinado = a / max(math.cos(inclinacao), 0.2)
    return b, comprimento_inclinado


def planos_do_telhado(insights: dict, inclinacao_max: float = 60.0,
                      area_min_m2: float = 8.0) -> list[PlanoTelhado]:
    """Converte roofSegmentStats em planos retangulares aproximados."""
    potencial = insights.get("solarPotential", {})
    planos: list[PlanoTelhado] = []
    for i, seg in enumerate(potencial.get("roofSegmentStats", [])):
        area = seg["stats"]["areaMeters2"]
        if area < area_min_m2 or seg.get("pitchDegrees", 0) > inclinacao_max:
            continue
        largura, comprimento = _dimensoes_do_segmento(seg)
        quantis = seg["stats"].get("sunshineQuantiles") or []
        horas = quantis[len(quantis) // 2] if quantis else None
        planos.append(PlanoTelhado(
            nome=f"Água {i + 1}",
            inclinacao_graus=round(seg.get("pitchDegrees", 0.0), 1),
            azimute_graus=round(seg.get("azimuthDegrees", 0.0), 1),
            poligono=box(0, 0, largura, comprimento),
            horas_sol_ano=horas,
            origem="solar_api",
            observacoes=[
                "Contorno retangular aproximado a partir da Solar API: confirmar medidas e "
                "obstáculos (caixa d'água, claraboias, platibanda) na visita técnica.",
            ],
        ))
    return planos


def resumo_edificacao(insights: dict) -> dict:
    potencial = insights.get("solarPotential", {})
    return {
        "centro": insights.get("center"),
        "qualidade_imagem": insights.get("imageryQuality"),
        "data_imagem": insights.get("imageryDate"),
        "max_modulos_google": potencial.get("maxArrayPanelsCount"),
        "max_horas_sol_ano": potencial.get("maxSunshineHoursPerYear"),
        "area_telhado_m2": potencial.get("wholeRoofStats", {}).get("areaMeters2"),
    }
