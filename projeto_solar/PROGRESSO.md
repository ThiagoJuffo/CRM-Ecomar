# Andamento do projeto solar

Atualizado em 08/10/2026.

## Pronto
- Paginação, strings, cabos e proteções, unifilar (DXF/PDF), memorial e resultado.json.
- Solar API: endereço ou link do Google Maps (`--maps`), com marcação automática do
  telhado pela elevação (águas, prédio do ponto, módulos existentes como obstáculo).
- Foto de drone + medida de referência (`ferramenta/marcador_telhado.html`) — etapa 2.
- Orientação dos módulos configurável (`parametros.paginacao.orientacoes`).

## Obras de teste (`projetos/`)
| Obra | Situação |
|---|---|
| Boizera Prime (Serra/ES) | 94 × 620 W em retrato, 3 × Solplanet 15 kW 220 V 3F, área marcada na foto da Solar API. Falta datasheet do módulo e do inversor. |
| Due Pizzaria (Serra/ES) | Obra já executada; falta saber módulos e inversor instalados para comparar. |

Para rodar (precisa de `GOOGLE_MAPS_API_KEY` no ambiente):

```bash
cd projeto_solar
python -m projeto_solar projetos/boizera_prime/entrada.json --saida saida/boizera
python -m projeto_solar projetos/due_pizzaria/entrada.json --saida saida/due
```

## Pendências
1. Datasheets: módulo 620 W e Solplanet 15 kW 220 V (hoje com valores típicos
   marcados "A CONFIRMAR" em `projeto_solar/catalogo/`).
2. Trocar a chave do Google (a atual foi exposta no chat) e cadastrá-la como
   `GOOGLE_MAPS_API_KEY` nas configurações do ambiente.
3. Separar automaticamente unidades vizinhas no mesmo telhado contínuo.
4. Próximas etapas: multifilar, padrões das concessionárias, integração com o CRM.
