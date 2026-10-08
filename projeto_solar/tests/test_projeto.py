import json
import math
from pathlib import Path

import pytest
from shapely.geometry import box

from projeto_solar import solar_api, strings
from projeto_solar.modelos import PlanoTelhado, carregar_inversor, carregar_modulo
from projeto_solar.paginacao import ParametrosPaginacao, paginar_plano
from projeto_solar.projeto import executar

DADOS = Path(__file__).parent / "dados"
EXEMPLOS = Path(__file__).parent.parent / "exemplos"


@pytest.fixture
def modulo():
    return carregar_modulo("exemplo-550")


@pytest.fixture
def insights():
    return json.loads((DADOS / "building_insights_exemplo.json").read_text(encoding="utf-8"))


def test_planos_da_solar_api_recuperam_dimensoes(insights):
    planos = solar_api.planos_do_telhado(insights)
    norte = planos[0]
    minx, miny, maxx, maxy = norte.poligono.bounds
    # água norte de 12 m (cumeeira) x 5 m (na inclinação) no fixture
    assert maxx - minx == pytest.approx(12.0, rel=0.02)
    assert maxy - miny == pytest.approx(5.0, rel=0.02)
    assert norte.azimute_graus == 0 and norte.inclinacao_graus == 17
    assert norte.horas_sol_ano == 1650


def test_paginacao_respeita_recuo_e_obstaculo(modulo):
    plano = PlanoTelhado("A", 15, 0, box(0, 0, 12, 6), obstaculos=[box(7.5, 2, 9, 3.5)])
    p = ParametrosPaginacao(recuo_borda_m=0.3, afastamento_obstaculo_m=0.3)
    pag = paginar_plano(plano, modulo, p)
    assert pag.quantidade == 16
    obst = plano.obstaculos[0].buffer(0.3)
    for m in pag.modulos:
        assert pag.area_util.contains(m)
        assert not m.intersects(obst.buffer(-1e-6))
    for a, b in zip(pag.modulos, pag.modulos[1:]):
        assert not a.buffer(-1e-6).intersects(b)


def test_limites_de_string(modulo):
    inv = carregar_inversor("exemplo-10k-tri")
    lim = strings.limites_da_string(modulo, inv, strings.CondicoesLocais(temp_min_c=5, temp_max_amb_c=36))
    voc_frio = 49.6 * (1 - 0.0027 * (5 - 25))
    assert lim.voc_tmin == pytest.approx(voc_frio)
    assert lim.n_max == math.floor(1100 / voc_frio)
    assert lim.n_max * lim.voc_tmin <= inv.vcc_max
    assert lim.n_min * lim.vmp_tmax >= inv.vpartida


def test_strings_nao_misturam_planos_e_respeitam_corrente(modulo):
    inv = carregar_inversor("exemplo-10k-tri")
    arr = strings.dimensionar(modulo, inv, 1, {"Norte": 14, "Leste": 9}, strings.CondicoesLocais())
    planos = {m.plano for m in arr.mppts if m.strings}
    assert planos == {"Norte", "Leste"}
    for m in arr.mppts:
        assert m.strings * modulo.isc <= inv.isc_max_por_mppt
        if m.strings:
            assert arr.limites.n_min <= m.modulos_por_string <= arr.limites.n_max
    # cada MPPT recebe no máximo metade da potência CC máx. (15 kWp / 2 = 13 módulos)
    for m in arr.mppts:
        assert m.modulos * modulo.potencia_w <= inv.potencia_cc_max_w / inv.n_mppt
    assert arr.modulos_usados == 22
    assert any("fora das strings" in a for a in arr.alertas)


def test_carga_dividida_entre_inversores(modulo):
    inv = carregar_inversor("exemplo-10k-tri")
    arr = strings.dimensionar(modulo, inv, 2, {"A": 32, "B": 12}, strings.CondicoesLocais())
    for i in (1, 2):
        pcc = sum(m.modulos for m in arr.mppts if m.inversor == i) * modulo.potencia_w
        assert pcc <= inv.potencia_cc_max_w
    tamanhos = [m.modulos_por_string for m in arr.mppts if m.plano == "A" and m.strings]
    assert max(tamanhos) - min(tamanhos) <= 1  # strings equilibradas


def test_inversor_incompativel_gera_erro():
    modulo = carregar_modulo("exemplo-610-topcon")
    inv = carregar_inversor("exemplo-5k-mono")
    inv.vmppt_min, inv.vpartida = 590, 590  # string mínima maior que a máxima
    with pytest.raises(ValueError):
        strings.dimensionar(modulo, inv, 1, {"A": 20}, strings.CondicoesLocais())


def test_fluxo_completo_com_solar_api_simulada(tmp_path):
    entrada = json.loads((EXEMPLOS / "solar_api.json").read_text(encoding="utf-8"))
    entrada["telhado"]["insights_arquivo"] = str(DADOS / "building_insights_exemplo.json")
    res = executar(entrada, tmp_path)
    nomes = {pg.plano.nome for pg in res.paginacoes}
    assert "Água 2" not in nomes  # água sul descartada por ter pouco sol
    assert res.arranjo.modulos_usados > 0
    for nome in ("01_paginacao.dxf", "01_paginacao.pdf", "02_unifilar.dxf", "02_unifilar.pdf",
                 "03_memorial.md", "resultado.json"):
        assert (tmp_path / nome).stat().st_size > 0
    resultado = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    assert resultado["energia_anual_kwh"] > 0


def test_exemplo_manual(tmp_path):
    entrada = json.loads((EXEMPLOS / "telhado_manual.json").read_text(encoding="utf-8"))
    res = executar(entrada, tmp_path)
    assert res.arranjo.modulos_usados == 16
    assert res.quantidade_inversores == 1


def test_coordenadas_do_link_do_maps():
    link = ("https://www.google.com/maps/place/Due+%7C+Pizza+e+Esfiha/@-20.1986768,-40.2580338,51m/"
            "data=!3m1!1e3!4m6!3m5!1s0xb81ff750afe56d:0x9bdfb4436508cd1b!8m2!3d-20.1986799!4d-40.2580866")
    assert solar_api.coordenadas_do_link(link) == (-20.1986799, -40.2580866)
    assert solar_api.coordenadas_do_link("https://maps.google.com/@-23.5,-46.6,17z") == (-23.5, -46.6)
    assert solar_api.coordenadas_do_link("sem coordenadas") is None


def _foto_sintetica(caminho):
    import numpy as np
    from PIL import Image
    img = np.full((400, 700, 3), 60, dtype=np.uint8)
    img[50:350, 50:650] = (200, 200, 200)  # telhado de 600 x 300 px
    Image.fromarray(img).save(caminho)


def test_plano_da_foto_escala_inclinacao_e_azimute():
    from projeto_solar import foto
    # beiral em baixo (y=350), sobe para o topo da foto: queda d'água para o sul
    d = {"nome": "A", "inclinacao": 17, "poligono_px": [[50, 350], [650, 350], [650, 50], [50, 50]],
         "obstaculos_px": [[[300, 150], [350, 150], [350, 200], [300, 200]]]}
    plano = foto.plano_da_foto(d, escala_m_px=0.02)
    minx, miny, maxx, maxy = plano.poligono.bounds
    assert maxx - minx == pytest.approx(12.0)
    assert maxy - miny == pytest.approx(6.0 / math.cos(math.radians(17)))
    assert plano.azimute_graus == pytest.approx(180.0)
    # ida e volta: o canto do beiral volta para o mesmo pixel
    x, y = plano.transformacao.para_pixels(0, 0)
    assert (round(x), round(y)) in {(50, 350), (650, 350)}
    # foto girada: norte 90° à direita do topo -> a queda (topo->baixo) aponta para oeste
    assert foto.plano_da_foto(d, 0.02, norte_graus=90).azimute_graus == pytest.approx(90.0)


def test_fluxo_com_foto_e_solar_api(tmp_path):
    caminho_foto = tmp_path / "drone.png"
    _foto_sintetica(caminho_foto)
    entrada = json.loads((EXEMPLOS / "telhado_manual.json").read_text(encoding="utf-8"))
    entrada["telhado"] = {
        "origem": "foto", "foto": str(caminho_foto),
        "referencia": {"p1": [50, 350], "p2": [650, 350], "metros": 12.0},
        "norte_graus": 180,  # foto tirada com o sul no topo -> queda para o norte
        "planos": [{"nome": "Norte", "poligono_px": [[50, 350], [650, 350], [650, 50], [50, 50]]}],
        "insights_arquivo": str(DADOS / "building_insights_exemplo.json"),
    }
    res = executar(entrada, tmp_path)
    plano = res.paginacoes[0].plano
    assert plano.azimute_graus == pytest.approx(0.0)
    assert plano.inclinacao_graus == 17  # veio da Solar API (água norte do fixture)
    assert plano.horas_sol_ano == 1650
    assert (tmp_path / "00_sobreposicao_foto.png").stat().st_size > 0
    assert res.arranjo.modulos_usados > 0
