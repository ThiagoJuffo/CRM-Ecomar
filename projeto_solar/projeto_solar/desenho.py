"""Desenhos em DXF (abre no AutoCAD) com exportação para PDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import matplotlib as dxf_mpl
from ezdxf.enums import TextEntityAlignment

from .eletrico import ProjetoEletrico
from .modelos import Inversor, Modulo
from .paginacao import Paginacao
from .strings import ArranjoEletrico

CORES_STRING = [1, 3, 5, 6, 30, 140, 200, 40, 4, 2]


def _novo_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metros
    for nome, cor in [("TELHADO", 7), ("RECUO", 8), ("OBSTACULO", 1), ("MODULO", 5),
                      ("TEXTO", 7), ("ELETRICO", 7), ("CARIMBO", 7)]:
        doc.layers.add(nome, color=cor)
    return doc


def _texto(msp, txt, x, y, altura=0.15, alinhamento=TextEntityAlignment.MIDDLE_CENTER,
           camada="TEXTO", cor=None):
    attribs = {"height": altura, "layer": camada}
    if cor is not None:
        attribs["color"] = cor
    msp.add_text(txt, dxfattribs=attribs).set_placement((x, y), align=alinhamento)


def _carimbo(msp, x, y, largura, dados: dict, escala: float = 1.0):
    altura = 1.6 * escala
    msp.add_lwpolyline([(x, y), (x + largura, y), (x + largura, y + altura), (x, y + altura)],
                       close=True, dxfattribs={"layer": "CARIMBO"})
    linhas = [
        f"ECOMAR ENGENHARIA - {dados.get('titulo', '')}",
        f"Cliente: {dados.get('cliente', '-')}   Obra: {dados.get('nome', '-')}",
        f"Endereço: {dados.get('endereco', '-')}",
        f"Data: {date.today():%d/%m/%Y}   Folha: {dados.get('folha', '1/1')}   "
        f"PRÉ-PROJETO GERADO AUTOMATICAMENTE - REVISAR",
    ]
    for i, linha in enumerate(linhas):
        _texto(msp, linha, x + 0.15 * escala, y + altura - (0.35 + i * 0.35) * escala,
               altura=0.18 * escala, alinhamento=TextEntityAlignment.MIDDLE_LEFT, camada="CARIMBO")


def _salvar(doc, caminho_dxf: Path) -> Path:
    doc.saveas(caminho_dxf)
    pdf = caminho_dxf.with_suffix(".pdf")
    dxf_mpl.qsave(doc.modelspace(), str(pdf), bg="#FFFFFF", size_inches=(16.5, 11.7))
    return pdf


# --------------------------------------------------------------------- paginação

def desenhar_paginacao(paginacoes: list[Paginacao], modulo: Modulo, dados: dict,
                       caminho: Path) -> Path:
    doc = _novo_doc()
    msp = doc.modelspace()
    x0 = 0.0
    largura_total = 0.0
    cores: dict[str, int] = {}
    for pag in paginacoes:
        minx, miny, maxx, maxy = pag.plano.poligono.bounds
        dx = x0 - minx

        def pts(geom):
            return [(x + dx, y - miny) for x, y in geom.exterior.coords]

        msp.add_lwpolyline(pts(pag.plano.poligono), close=True, dxfattribs={"layer": "TELHADO"})
        areas = getattr(pag.area_util, "geoms", [pag.area_util])
        for a in areas:
            if not a.is_empty:
                msp.add_lwpolyline(pts(a), close=True,
                                   dxfattribs={"layer": "RECUO", "linetype": "DASHED"})
        for o in pag.plano.obstaculos:
            hatch = msp.add_hatch(color=1, dxfattribs={"layer": "OBSTACULO"})
            hatch.paths.add_polyline_path(pts(o), is_closed=True)
        for i, m in enumerate(pag.modulos):
            rotulo = pag.rotulos[i] if i < len(pag.rotulos) else ""
            chave = rotulo.rsplit(".", 1)[0] if rotulo else ""
            cor = cores.setdefault(chave, CORES_STRING[len(cores) % len(CORES_STRING)]) if chave else 8
            msp.add_lwpolyline(pts(m), close=True, dxfattribs={"layer": "MODULO", "color": cor})
            cx, cy = m.centroid.x + dx, m.centroid.y - miny
            _texto(msp, rotulo or "-", cx, cy, altura=0.14, cor=cor)
        titulo = (f"{pag.plano.nome} - incl. {pag.plano.inclinacao_graus:.0f}°, "
                  f"azimute {pag.plano.azimute_graus:.0f}° - {pag.quantidade} módulos "
                  f"({pag.orientacao})")
        if pag.cabem > pag.quantidade:
            titulo += f" - cabem {pag.cabem}, {pag.cabem - pag.quantidade} fora das strings"
        _texto(msp, titulo, x0, maxy - miny + 0.5, altura=0.25, alinhamento=TextEntityAlignment.LEFT)
        _texto(msp, "↑ sobe a inclinação (cumeeira)", x0, maxy - miny + 0.15, altura=0.15,
               alinhamento=TextEntityAlignment.LEFT)
        largura_total = x0 + (maxx - minx)
        x0 += (maxx - minx) + 2.0
    _texto(msp, f"Módulo: {modulo.fabricante} {modulo.modelo} "
                f"({modulo.comprimento_m:.3f} x {modulo.largura_m:.3f} m). "
                "Rótulo do módulo: inversor.MPPT.string.posição", 0, -0.6, altura=0.18,
           alinhamento=TextEntityAlignment.LEFT)
    _carimbo(msp, 0, -2.6, max(largura_total, 14.0), {**dados, "titulo": "PLANTA DE PAGINAÇÃO DOS MÓDULOS"})
    return _salvar(doc, caminho)


# --------------------------------------------------------------------- unifilar

def _caixa(msp, x, y, w, h, linhas: list[str], altura_txt=0.22):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True,
                       dxfattribs={"layer": "ELETRICO"})
    for i, l in enumerate(linhas):
        _texto(msp, l, x + w / 2, y + h - (i + 1) * h / (len(linhas) + 1), altura=altura_txt)


def _linha(msp, p1, p2, condutores: int | None = None, legenda: str | None = None):
    msp.add_line(p1, p2, dxfattribs={"layer": "ELETRICO"})
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    if condutores:
        # traços inclinados indicam o número de condutores (convenção de unifilar)
        for k in range(condutores):
            ox = mx - 0.12 * (condutores - 1) / 2 + 0.12 * k
            msp.add_line((ox - 0.08, my - 0.12), (ox + 0.08, my + 0.12), dxfattribs={"layer": "ELETRICO"})
    if legenda:
        _texto(msp, legenda, mx, my + 0.35, altura=0.16)


def _disjuntor(msp, x, y, rotulo):
    msp.add_line((x, y), (x + 0.3, y), dxfattribs={"layer": "ELETRICO"})
    msp.add_line((x + 0.3, y), (x + 0.75, y + 0.25), dxfattribs={"layer": "ELETRICO"})
    msp.add_line((x + 0.8, y), (x + 1.1, y), dxfattribs={"layer": "ELETRICO"})
    _texto(msp, rotulo, x + 0.55, y - 0.35, altura=0.16)


def desenhar_unifilar(arr: ArranjoEletrico, elet: ProjetoEletrico, modulo: Modulo, inv: Inversor,
                      quantidade_inv: int, dados: dict, caminho: Path) -> Path:
    doc = _novo_doc()
    msp = doc.modelspace()
    cc_por_mppt = {c.mppt: c for c in elet.cc}
    y = 0.0
    x_qgbt = 24.0
    pontos_ca = []
    for i in range(1, quantidade_inv + 1):
        mppts = [m for m in arr.mppts if m.inversor == i]
        altura_inv = max(2.4, 1.6 * len(mppts))
        y_inv = y
        for j, m in enumerate(mppts):
            ym = y_inv + altura_inv - (j + 0.5) * (altura_inv / len(mppts))
            if not m.strings:
                _texto(msp, f"{m.rotulo}: não utilizado", 4.0, ym, alinhamento=TextEntityAlignment.MIDDLE_LEFT)
                continue
            c = cc_por_mppt[m.rotulo]
            _caixa(msp, 0, ym - 0.6, 3.6, 1.2, [
                f"{m.strings} string(s) x {m.modulos_por_string} mód.",
                f"{m.plano}",
                f"{m.modulos * modulo.potencia_w / 1000:.2f} kWp  Voc máx {c.voc_max_v:.0f} V",
            ], altura_txt=0.17)
            protecoes = [f"Seccionadora CC {c.seccionadora_v} V / {c.seccionadora_a} A",
                         f"DPS CC classe II Ucpv ≥ {c.dps_ucpv_v} V"]
            if c.fusivel_a:
                protecoes.insert(0, f"Fusível gPV {c.fusivel_a} A (+ e -)")
            _linha(msp, (3.6, ym), (6.0, ym), condutores=2 * m.strings,
                   legenda=f"{2 * m.strings}x{c.secao_mm2} mm² 1,8 kV CC")
            _caixa(msp, 6.0, ym - 0.6, 4.4, 1.2, ["STRING BOX " + m.rotulo] + protecoes, altura_txt=0.15)
            _linha(msp, (10.4, ym), (12.5, ym), condutores=2)
        _caixa(msp, 12.5, y_inv, 4.2, altura_inv, [
            f"INVERSOR {i}", f"{inv.fabricante.split(' (')[0]}", inv.modelo,
            f"{inv.potencia_ca_w / 1000:.1f} kW  {inv.n_mppt} MPPT",
        ], altura_txt=0.17)
        ca = elet.ca[i - 1]
        y_ca = y_inv + altura_inv / 2
        n_cond = (3 if inv.fases == 3 else 1) + 2  # fases + neutro + PE
        _linha(msp, (16.7, y_ca), (19.0, y_ca), condutores=n_cond,
               legenda=f"{n_cond}x{ca.secao_mm2:g} mm² 0,6/1 kV")
        _caixa(msp, 19.0, y_ca - 0.9, 3.4, 1.8, [
            f"QUADRO CA INV{i}", f"Disjuntor {'3' if inv.fases == 3 else '2'}P {ca.disjuntor_a} A",
            f"DPS CA classe II Uc {ca.dps_uc_v} V", f"queda {ca.queda_pct}%",
        ], altura_txt=0.16)
        _linha(msp, (22.4, y_ca), (x_qgbt, y_ca), condutores=n_cond)
        pontos_ca.append(y_ca)
        y += altura_inv + 1.2

    y_min, y_max = min(pontos_ca), max(pontos_ca)
    msp.add_line((x_qgbt, y_min), (x_qgbt, y_max), dxfattribs={"layer": "ELETRICO"})
    y_mid = (y_min + y_max) / 2
    _texto(msp, "QGBT (existente)", x_qgbt, y_max + 0.5, altura=0.2)
    _disjuntor(msp, x_qgbt, y_mid, "Disj. geral (verificar)")
    _linha(msp, (x_qgbt + 1.1, y_mid), (x_qgbt + 2.5, y_mid))
    _caixa(msp, x_qgbt + 2.5, y_mid - 0.7, 2.6, 1.4, ["MEDIDOR", "BIDIRECIONAL", "(concessionária)"])
    _linha(msp, (x_qgbt + 5.1, y_mid), (x_qgbt + 6.6, y_mid))
    _texto(msp, "REDE", x_qgbt + 7.1, y_mid + 0.2, altura=0.25)
    _texto(msp, f"{inv.tensao_ca_v:.0f} V {'3F' if inv.fases == 3 else '1F'}",
           x_qgbt + 7.1, y_mid - 0.2, altura=0.18)

    notas = [
        "NOTAS:",
        "1. Pré-dimensionamento automático (NBR 16690 / NBR 5410). Revisar e assinar pelo responsável técnico.",
        "2. Conferir padrão de entrada e exigências da concessionária para o pedido de acesso.",
        "3. Aterramento das estruturas e módulos interligado ao BEP da edificação (condutor PE).",
    ] + [f"! {a}" for a in (arr.alertas + elet.alertas)]
    for k, n in enumerate(notas):
        _texto(msp, n, 0, -0.8 - k * 0.35, altura=0.18, alinhamento=TextEntityAlignment.MIDDLE_LEFT)
    _carimbo(msp, 0, -1.4 - len(notas) * 0.35 - 1.8, x_qgbt + 8.0,
             {**dados, "titulo": "DIAGRAMA UNIFILAR"})
    return _salvar(doc, caminho)
