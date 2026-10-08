# Projeto Solar (pré-projeto automatizado)

Gera, a partir do endereço do cliente ou do contorno do telhado:

1. **Estudo de paginação** dos módulos em cada água do telhado (retrato x paisagem,
   recuos de borda, obstáculos), escolhendo o arranjo que cabe mais módulos.
2. **Dimensionamento de strings** por MPPT: faixa de módulos em série pela Voc a frio
   e Vmp a quente, limites de corrente por MPPT e relação CC/CA. Nunca mistura águas
   com orientações diferentes no mesmo MPPT.
3. **Cabos e proteções** (pré-dimensionamento NBR 16690 / NBR 5410): seção CC e CA por
   ampacidade e queda de tensão, fusível de string, DPS CC/CA, seccionadora e disjuntor.
4. **Desenhos em DXF e PDF**: planta de paginação com a identificação de cada string e
   diagrama unifilar, com carimbo da Ecomar.
5. **Memorial** (`03_memorial.md`) com resumo, tabelas, pontos de atenção e lista de
   materiais, e `resultado.json` para integração com o CRM.

> Tudo que sai daqui é pré-projeto: precisa da revisão e da assinatura do responsável técnico.

## Instalação

```bash
cd projeto_solar
pip install -e ".[test]"
```

## Uso

### Com a Google Solar API

1. No Google Cloud Console, ative **Solar API** e **Geocoding API** e crie uma chave
   restrita a elas.
2. Defina a chave como variável de ambiente (nunca coloque a chave no repositório):

   ```bash
   export GOOGLE_MAPS_API_KEY="sua-chave"
   ```

3. Rode com o endereço do cliente:

   ```bash
   python -m projeto_solar exemplos/solar_api.json --endereco "Rua X, 123 - Cidade/UF"
   # ou com o link do Google Maps da obra:
   python -m projeto_solar exemplos/solar_api.json --maps "https://www.google.com/maps/place/...!3d-20.19!4d-40.25"
   ```

Com o link do Google Maps (ou lat/lng), a ferramenta **marca o telhado sozinha** pelas
camadas de dados da Solar API: separa as águas pela elevação (DSM), fica só com o prédio
do ponto, detecta módulos já instalados (de vizinhos, por exemplo) e os trata como
obstáculo, e alinha o beiral com as paredes do prédio. Gera `00_sobreposicao_foto.png`
para conferência. Para usar só o retângulo equivalente, ponha `"contorno": "retangulo"`
no campo `telhado`.

Sem as camadas, a Solar API devolve, para cada água do telhado, inclinação, azimute,
área e insolação anual. Ela **não** devolve o contorno exato nem os obstáculos: a ferramenta monta um
retângulo equivalente. Confirme as medidas na visita técnica e, se precisar, ajuste o
contorno no modo manual.

Águas com insolação abaixo de `fracao_min_sol` (padrão 75%) da melhor água são
descartadas (por exemplo, águas voltadas para o sul).

### Com foto de drone e medida de referência (etapa 2)

A foto (vista de cima) dá o contorno real de cada água e dos obstáculos. A Solar API,
quando informada pelo link do Google Maps, completa a inclinação e a insolação.

1. Abra `ferramenta/marcador_telhado.html` no navegador e carregue a foto.
2. Marque a escala: clique nas duas pontas de uma medida conhecida e informe os metros
   (ou digite a escala em m/pixel, se a souber).
3. Em "Nova água", clique **primeiro nos dois vértices do beiral** (borda mais baixa) e
   depois nos demais; conclua o polígono. Marque os obstáculos da água selecionada.
4. Informe o norte da foto (graus no sentido horário a partir do topo) e, se souber,
   a inclinação de cada água. Em branco, a inclinação vem da Solar API.
5. Copie o JSON para o campo `"telhado"` do projeto e rode:

   ```bash
   python -m projeto_solar projeto.json --maps "<link do Google Maps da obra>"
   ```

Sai também `00_sobreposicao_foto.png`, com os módulos desenhados sobre a foto.

### Com o telhado medido (modo manual)

Descreva cada água em metros, no próprio plano inclinado (x ao longo da cumeeira,
y subindo pela inclinação), com os obstáculos:

```bash
python -m projeto_solar exemplos/telhado_manual.json
```

Os arquivos saem em `saida/<nome do projeto>/`:
`01_paginacao.dxf/.pdf`, `02_unifilar.dxf/.pdf`, `03_memorial.md` e `resultado.json`.

## Arquivo de entrada

| Campo | Descrição |
|---|---|
| `projeto` | `nome`, `cliente`, `endereco` (vão para o carimbo e o memorial) |
| `telhado.origem` | `"solar_api"`, `"foto"` (JSON do marcador) ou `"manual"` (com `planos`) |
| `modulo` | `id` do módulo em `projeto_solar/catalogo/modulos.json` |
| `inversor.id` / `inversor.quantidade` | `id` em `catalogo/inversores.json`; quantidade `null` = automática pela relação CC/CA alvo |
| `local` | `temp_min_c`, `temp_max_amb_c` do local da obra |
| `eletrico` | `comprimento_cc_m`, `comprimento_ca_m`, `queda_max_cc_pct`, `queda_max_ca_pct` |
| `parametros.paginacao` | `recuo_borda_m`, `afastamento_obstaculo_m`, folgas entre módulos, `orientacoes` (`["retrato"]`, `["paisagem"]` ou as duas) |
| `parametros.max_modulos` | limita a quantidade pela potência que o cliente contratou |

## Catálogo de equipamentos

Os itens em `catalogo/` são **exemplos genéricos**. Cadastre os módulos e inversores que
a Ecomar usa copiando os dados do datasheet (Voc, Vmp, Isc, Imp, coeficientes de
temperatura, dimensões; faixa de MPPT, tensão máxima, correntes por MPPT).

## Próximas etapas

- Diagrama multifilar.
- Inversores com MPPTs de capacidades diferentes, microinversores e otimizadores.
- Integração com o CRM: gerar o projeto a partir do negócio e anexar os arquivos.
- Formulários e padrões de cada concessionária.

## Testes

```bash
python -m pytest
```
