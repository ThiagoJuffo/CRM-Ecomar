"""Orquestra o estudo completo: telhado -> paginação -> strings -> elétrica -> desenhos."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from . import eletrico, solar_api, strings
from .desenho import desenhar_paginacao, desenhar_unifilar
from .modelos import (Inversor, Modulo, PlanoTelhado, carregar_inversor, carregar_modulo,
                      plano_de_dict)
from .paginacao import Paginacao, ParametrosPaginacao, paginar_plano

PERFORMANCE_RATIO = 0.80


@dataclass
class Resultado:
    paginacoes: list[Paginacao]
    arranjo: strings.ArranjoEletrico
    eletrico: eletrico.ProjetoEletrico
    modulo: Modulo
    inversor: Inversor
    quantidade_inversores: int
    arquivos: list[Path]
    edificacao: dict | None = None


def obter_planos(entrada: dict) -> tuple[list[PlanoTelhado], dict | None]:
    telhado = entrada.get("telhado", {})
    if telhado.get("origem") == "solar_api":
        if "insights_arquivo" in telhado:  # resposta já salva (testes / reprocessamento)
            insights = json.loads(Path(telhado["insights_arquivo"]).read_text(encoding="utf-8"))
        else:
            lat, lng = telhado.get("lat"), telhado.get("lng")
            if lat is None or lng is None:
                lat, lng = solar_api.geocodificar(entrada["projeto"]["endereco"])
            insights = _buscar_com_fallback(lat, lng, telhado.get("qualidade", "HIGH"))
        planos = solar_api.planos_do_telhado(insights)
        if insights.get("imageryQuality") == "LOW":
            for p in planos:
                p.observacoes.append("Imagem da Solar API de qualidade LOW: inclinação e área podem "
                                     "ter erro maior; medir no local antes do projeto executivo.")
        return planos, insights
    return [plano_de_dict(p) for p in telhado["planos"]], None


def _buscar_com_fallback(lat: float, lng: float, qualidade: str) -> dict:
    """Tenta a qualidade pedida e, se o Google não tiver dados, as inferiores."""
    niveis = ["HIGH", "MEDIUM", "LOW"]
    for nivel in niveis[niveis.index(qualidade):]:
        try:
            return solar_api.buscar_edificacao(lat, lng, qualidade_minima=nivel)
        except solar_api.SemDadosSolarApi:
            continue
    raise solar_api.ErroSolarApi("A Solar API não tem dados deste telhado; desenhe o telhado manualmente.")


def _selecionar_planos(planos: list[PlanoTelhado], fracao_min_sol: float) -> list[PlanoTelhado]:
    """Descarta águas com muito menos sol que a melhor (ex.: voltadas para o sul)."""
    com_sol = [p.horas_sol_ano for p in planos if p.horas_sol_ano]
    if not com_sol:
        return planos
    melhor = max(com_sol)
    return [p for p in planos if not p.horas_sol_ano or p.horas_sol_ano >= fracao_min_sol * melhor]


def _rotular(paginacoes: list[Paginacao], arr: strings.ArranjoEletrico) -> None:
    for pag in paginacoes:
        pag.rotulos = []
        for m in (m for m in arr.mppts if m.plano == pag.plano.nome):
            for s in range(1, m.strings + 1):
                for k in range(1, m.modulos_por_string + 1):
                    pag.rotulos.append(f"{m.inversor}.{m.numero}.{s}.{k}")


def _quantidade_inversores(inv: Inversor, modulo: Modulo, n_modulos: int, razao_alvo: float) -> int:
    return max(1, math.ceil(n_modulos * modulo.potencia_w / (inv.potencia_ca_w * razao_alvo)))


def executar(entrada: dict, pasta_saida: Path) -> Resultado:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    modulo = carregar_modulo(entrada["modulo"])
    inv = carregar_inversor(entrada["inversor"]["id"])
    parametros = entrada.get("parametros", {})
    p_pag = ParametrosPaginacao(**parametros.get("paginacao", {}))
    cond = strings.CondicoesLocais(**entrada.get("local", {}))
    p_ele = eletrico.ParametrosEletricos(**entrada.get("eletrico", {}))

    planos, insights = obter_planos(entrada)
    planos = _selecionar_planos(planos, parametros.get("fracao_min_sol", 0.75))
    paginacoes = [paginar_plano(p, modulo, p_pag) for p in planos]
    paginacoes = [pg for pg in paginacoes if pg.quantidade]

    limite = parametros.get("max_modulos")
    disponiveis = {pg.plano.nome: pg.quantidade for pg in paginacoes}
    if limite:  # potência-alvo do cliente: corta das águas com menos sol
        restante = limite
        for pg in sorted(paginacoes, key=lambda pg: -(pg.plano.horas_sol_ano or 0)):
            disponiveis[pg.plano.nome] = min(disponiveis[pg.plano.nome], restante)
            restante -= disponiveis[pg.plano.nome]

    qtd_inv = entrada["inversor"].get("quantidade") or _quantidade_inversores(
        inv, modulo, sum(disponiveis.values()), parametros.get("razao_cc_ca_alvo", 1.25))
    arr = strings.dimensionar(modulo, inv, qtd_inv, disponiveis, cond)
    elet = eletrico.dimensionar(arr, modulo, inv, qtd_inv, p_ele)
    _rotular(paginacoes, arr)
    # módulos que couberam mas não entraram em string não são desenhados
    for pg in paginacoes:
        pg.modulos = pg.modulos[:len(pg.rotulos)]

    dados = entrada.get("projeto", {})
    arquivos = [
        desenhar_paginacao(paginacoes, modulo, dados, pasta_saida / "01_paginacao.dxf"),
        desenhar_unifilar(arr, elet, modulo, inv, qtd_inv, dados, pasta_saida / "02_unifilar.dxf"),
    ]
    resultado = Resultado(paginacoes, arr, elet, modulo, inv, qtd_inv, arquivos,
                          solar_api.resumo_edificacao(insights) if insights else None)
    arquivos += [pdf.with_suffix(".dxf") for pdf in list(arquivos)]
    arquivos.append(escrever_memorial(resultado, dados, pasta_saida / "03_memorial.md"))
    arquivos.append(escrever_json(resultado, pasta_saida / "resultado.json"))
    return resultado


def _energia_anual_kwh(res: Resultado) -> float | None:
    horas = {pg.plano.nome: pg.plano.horas_sol_ano for pg in res.paginacoes}
    total = 0.0
    for m in res.arranjo.mppts:
        if m.modulos:
            if not horas.get(m.plano):
                return None
            total += m.modulos * res.modulo.potencia_w / 1000 * horas[m.plano] * PERFORMANCE_RATIO
    return total


def escrever_memorial(res: Resultado, dados: dict, caminho: Path) -> Path:
    mod, inv, arr = res.modulo, res.inversor, res.arranjo
    kwp = arr.potencia_cc_w(mod) / 1000
    energia = _energia_anual_kwh(res)
    l = [
        f"# Memorial de pré-projeto fotovoltaico - {dados.get('nome', '')}",
        "",
        f"**Cliente:** {dados.get('cliente', '-')}  ",
        f"**Endereço:** {dados.get('endereco', '-')}",
        "",
        "> Documento gerado automaticamente. Valores de pré-dimensionamento: revisar e "
        "validar pelo responsável técnico antes de emitir o projeto executivo.",
        "",
        "## Resumo",
        f"- Potência CC instalada: **{kwp:.2f} kWp** ({arr.modulos_usados} módulos de {mod.potencia_w:.0f} W)",
        f"- Inversor(es): **{res.quantidade_inversores} x {inv.modelo}** "
        f"({res.quantidade_inversores * inv.potencia_ca_w / 1000:.1f} kW CA, "
        f"relação CC/CA {arr.potencia_cc_w(mod) / (res.quantidade_inversores * inv.potencia_ca_w):.2f})",
    ]
    if energia:
        l.append(f"- Geração estimada: **{energia:,.0f} kWh/ano** (~{energia / 12:,.0f} kWh/mês), "
                 f"PR {PERFORMANCE_RATIO:.0%} sobre a insolação da Solar API".replace(",", "."))
    if res.edificacao:
        e = res.edificacao
        d = e.get("data_imagem") or {}
        data = f"{d.get('day', 0):02}/{d.get('month', 0):02}/{d.get('year', 0)}" if d else "-"
        l.append(f"- Solar API: imagem de {data}, qualidade {e.get('qualidade_imagem')}; "
                 f"o Google estima até {e.get('max_modulos_google')} módulos no telhado")
    l += ["", "## Paginação", "| Água | Inclinação | Azimute | Orientação | Cabem | Usados | Insolação (kWh/kWp/ano) |",
          "|---|---|---|---|---|---|---|"]
    for pg in res.paginacoes:
        l.append(f"| {pg.plano.nome} | {pg.plano.inclinacao_graus:.0f}° | {pg.plano.azimute_graus:.0f}° | "
                 f"{pg.orientacao} | {pg.cabem} | {pg.quantidade} | {pg.plano.horas_sol_ano or '-'} |")
    lim = arr.limites
    l += ["", "## Strings",
          f"- Voc do módulo a frio: {lim.voc_tmin:.1f} V; Vmp a quente: {lim.vmp_tmax:.1f} V",
          f"- Faixa válida: **{lim.n_min} a {lim.n_max} módulos por string** (limite superior: {lim.motivo_n_max})",
          "", "| MPPT | Água | Strings | Módulos/string | Voc máx (V) | Vmp (V) | Cabo CC | Queda | Fusível | DPS CC | Seccionadora |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in res.eletrico.cc:
        plano = next(m.plano for m in arr.mppts if m.rotulo == c.mppt)
        l.append(f"| {c.mppt} | {plano} | {c.strings} | {c.modulos_por_string} | {c.voc_max_v} | {c.vmp_v} | "
                 f"{c.secao_mm2} mm² | {c.queda_pct}% | {f'{c.fusivel_a} A gPV' if c.fusivel_a else 'não exigido'} | "
                 f"Ucpv ≥ {c.dps_ucpv_v} V | {c.seccionadora_v} V / {c.seccionadora_a} A |")
    l += ["", "## Lado CA", "| Inversor | Corrente | Disjuntor | Cabo | Queda | DPS CA |", "|---|---|---|---|---|---|"]
    for c in res.eletrico.ca:
        l.append(f"| {c.inversor} | {c.corrente_a} A | {c.disjuntor_a} A | {c.secao_mm2:g} mm² | "
                 f"{c.queda_pct}% | Uc {c.dps_uc_v} V |")
    alertas = arr.alertas + res.eletrico.alertas + [o for pg in res.paginacoes for o in pg.plano.observacoes]
    if alertas:
        l += ["", "## Pontos de atenção"] + [f"- {a}" for a in dict.fromkeys(alertas)]
    l += ["", "## Lista de materiais (principal)",
          f"- {arr.modulos_usados} x módulo {mod.fabricante} {mod.modelo}",
          f"- {res.quantidade_inversores} x inversor {inv.fabricante} {inv.modelo}",
          f"- {sum(1 for c in res.eletrico.cc)} x string box / proteção CC (uma por MPPT em uso)",
          f"- {sum(c.strings for c in res.eletrico.cc)} x par de conectores MC4 por string + extensões",
          f"- {res.quantidade_inversores} x quadro CA com disjuntor e DPS"]
    caminho.write_text("\n".join(l) + "\n", encoding="utf-8")
    return caminho


def escrever_json(res: Resultado, caminho: Path) -> Path:
    dados = {
        "potencia_kwp": res.arranjo.potencia_cc_w(res.modulo) / 1000,
        "modulos": res.arranjo.modulos_usados,
        "quantidade_inversores": res.quantidade_inversores,
        "energia_anual_kwh": _energia_anual_kwh(res),
        "planos": [{"nome": pg.plano.nome, "inclinacao": pg.plano.inclinacao_graus,
                    "azimute": pg.plano.azimute_graus, "orientacao": pg.orientacao,
                    "modulos_cabem": pg.cabem, "modulos": pg.quantidade, "horas_sol_ano": pg.plano.horas_sol_ano}
                   for pg in res.paginacoes],
        "mppts": [asdict(m) for m in res.arranjo.mppts],
        "cc": [asdict(c) for c in res.eletrico.cc],
        "ca": [asdict(c) for c in res.eletrico.ca],
        "alertas": res.arranjo.alertas + res.eletrico.alertas,
        "edificacao": res.edificacao,
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho
