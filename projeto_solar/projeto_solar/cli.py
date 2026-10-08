"""Linha de comando: python -m projeto_solar <entrada.json> [--saida pasta]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .projeto import executar
from .solar_api import ErroSolarApi, coordenadas_do_link


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="projeto_solar", description=__doc__)
    ap.add_argument("entrada", type=Path, help="arquivo JSON do projeto (veja exemplos/)")
    ap.add_argument("--saida", type=Path, help="pasta de saída (padrão: saida/<nome do projeto>)")
    ap.add_argument("--endereco", help="sobrescreve o endereço e força a Solar API")
    ap.add_argument("--maps", help="link do Google Maps da obra (usa as coordenadas do local)")
    args = ap.parse_args(argv)

    entrada = json.loads(args.entrada.read_text(encoding="utf-8"))
    if args.endereco:
        entrada.setdefault("projeto", {})["endereco"] = args.endereco
        entrada["telhado"] = {"origem": "solar_api"}
    if args.maps:
        coords = coordenadas_do_link(args.maps)
        if not coords:
            sys.exit("Erro: não encontrei coordenadas no link do Google Maps")
        entrada["telhado"] = {**entrada.get("telhado", {}), "origem": "solar_api",
                              "lat": coords[0], "lng": coords[1]}
    nome = entrada.get("projeto", {}).get("nome", args.entrada.stem)
    saida = args.saida or Path("saida") / nome.replace(" ", "_")

    try:
        res = executar(entrada, saida)
    except (ErroSolarApi, ValueError, KeyError) as e:
        sys.exit(f"Erro: {e}")

    kwp = res.arranjo.potencia_cc_w(res.modulo) / 1000
    print(f"{res.arranjo.modulos_usados} módulos | {kwp:.2f} kWp | "
          f"{res.quantidade_inversores} x {res.inversor.modelo}")
    for m in res.arranjo.mppts:
        if m.strings:
            print(f"  {m.rotulo}: {m.strings} x {m.modulos_por_string} módulos ({m.plano})")
    for a in res.arranjo.alertas + res.eletrico.alertas:
        print(f"  ! {a}")
    print("Arquivos:")
    for f in res.arquivos:
        print(f"  {f}")
