# Design System do dbqm — "Plano"

Data: 2026-08-22
Guia de referência: `agents-defaults/DESIGN-SYSTEM.md`

## 1. Levantamento (o que existe hoje)

Medido antes de propor, como manda o §0 do guia.

| Achado | Medida |
|---|---|
| Tokens declarados e nunca usados | `text-dim`, `text-bright`, `panel-active` — **0 usos** |
| Token fantasma | `$text-muted` usado **28×**; vem do Textual, não do `theme.py` |
| Teste travando token morto | `test_dark_palette_matches_prototype` afirma `panel-active == "#21262d"` |
| Cor literal em markup | **210** (`[green]`, `[red]`, `[dim]`…) — 104 em `cli.py`, ~106 na TUI |
| Hex fora do tema na TUI | `#e3b341` em `query_list.py:68` e `group_run.py` |
| Segunda paleta independente | `core/html_report.py`: 14 hex próprios (`#00d4ff`, `#16213e`) |
| Chrome de dialog replicado | `border: thick $accent` — **24× em 13 arquivos** |
| Estados vazios | ~23 mensagens "Nenhum…"; **1** oferece a próxima ação |
| Testes de manutenção do §13 | **0 de 4** |
| Regras `:focus` | 3, em 58 blocos de CSS |

**Contraste calculado do tema atual** (piso 4.5:1 texto / 3:1 interface):

- `$text-muted`, o token de apoio realmente em uso, resolve para **6.84:1**
  (escuro) e **5.74:1** (claro). Passa. O `text-dim` declarado em `theme.py`
  fica em 3.8:1, mas tem **0 usos** — é dívida morta, não defeito ativo.
- `$text-disabled` no tema claro: **2.68:1**, abaixo do piso de interface de 3:1.
  Este é o defeito de contraste vivo hoje.
- Bordas de painel: **~1.4:1** nos dois temas. Não separam regiões por contraste.

Os tokens de apoio do Textual são `auto 60%` / `auto 38%` — resolvidos contra o
fundo no momento da renderização, não hexadecimais fixos. A paleta Plano os
substitui por valores explícitos, para que o contraste seja calculável a partir
do arquivo de tokens em vez de exigir renderização.

**O que já está saudável e não recebe sistema novo:** o espaçamento já é uma
escala de fato (130 usos de `1`, 49 de `0 1`, 36 de `1 2`, um único `2` solto).
Formalizar, não redesenhar.

## 2. A tese

O levantamento revelou **dois eixos de significado fundidos num só**. Hoje ambos
usam verde/amarelo/vermelho:

- **Veredito de comparação** — `OK` / `DIFERE` / `AUSENTE`. Resultados factuais.
- **Status de operação** — conexão, execução. Sucesso ou falha.

`DIFERE` não é um aviso; `AUSENTE` não é um erro. Separar os eixos é a decisão
estrutural da paleta.

O segundo achado é um desperdício: a cor mais saturada do produto (`$accent`
roxo `#bc8cff`) é gasta em **borda de dialog** — 24 usos, zero informação.
Enquanto isso, a única cor que alguém precisou escrever à mão foi um âmbar,
para marcar **conexão**. O código já apontava onde a cor importa.

**Tese: o chrome não tem cor; a tinta é reservada ao dado que discorda.**

### O risco assumido

**O dbqm não tem verde.** `OK` não recebe tinta — sai como `texto-apoio`.

Justificativa: num run de 10 mil chaves em que 9.990 batem, pintar todas de
verde cobre a tela com uma cor que significa "não olhe para mim". Conexão
conectada usa o âmbar de identidade, não um check verde. Sucesso é a ausência
de alarme.

É reversível num único token (`veredito-igual`) se não funcionar na prática.

## 3. Onde o guia não se aplica, e por quê

Declarado explicitamente para que ninguém procure depois:

- **§4 (três estados de tema).** Textual não tem "seguir o sistema"; o terminal
  não expõe preferência de esquema de forma confiável. Aqui são **dois** estados
  explícitos, persistidos em `settings.json`. A regra que sobrevive e vale é a
  outra: *nenhuma cor pode ter definição única dentro de um tema* — hoje isso é
  violado, e é o que o teste de paridade passa a guardar.
- **§5 (utilitários com resolução de conflito) e §7 (mobile).** Não há Tailwind,
  toque, `hover` nem safe area. Descartados.
- **§9 (movimento).** Textual não anima layout do modo descrito; a armadilha do
  arrastar-e-soltar sob ancestral transformado não existe aqui.

**§11 (acessibilidade) é o mais relevante deste projeto**, não o menos: teclado
é a única gramática de navegação do dbqm.

## 4. Arquitetura: uma fonte, três consumidores

O `html_report.py` ter paleta própria não é descuido — é consequência de os
tokens morarem em `ui/theme.py`, e `core/` não poder importar `ui/`
(regra de camadas do AGENTS.md).

Correção: um pacote-folha novo, **`dbqm/design/`**, que não importa nada do
`dbqm` e pode ser importado por todos:

```
dbqm/design/tokens.py      # camadas 1 e 2 — dados puros, sem dependência
        │
        ├─→ dbqm/ui/theme.py        constrói os Theme do Textual
        ├─→ dbqm/cli.py             constrói o Theme do Rich (104 markups)
        └─→ dbqm/core/html_report.py emite as custom properties do CSS
```

Isso adiciona uma camada **abaixo** de `core/` e `ui/`, sem violar a regra
existente. AGENTS.md precisa registrar a nova camada.

## 5. Camada 1 — primitivas

Valores brutos. Nomes descrevem o que a coisa **é**.

### Neutros (ardósia)

| Primitiva | Escuro | Claro |
|---|---|---|
| `ardosia-950` | `#0b0e14` | — |
| `ardosia-900` | `#0f131b` | — |
| `ardosia-850` | `#151a24` | — |
| `ardosia-800` | `#1e2531` | — |
| `ardosia-700` | `#2b3342` | — |
| `ardosia-500` | `#606e86` | — |
| `ardosia-450` | `#6b7688` | — |
| `ardosia-300` | `#9aa4b5` | — |
| `ardosia-100` | `#d5dae4` | — |
| `ardosia-050` | `#f2f5fa` | — |
| `neve-000` | — | `#ffffff` |
| `neve-050` | — | `#f4f6f9` |
| `neve-100` | — | `#f2f5f8` |
| `neve-150` | — | `#eaeef3` |
| `neve-300` | — | `#d3dae3` |
| `neve-500` | — | `#8a94a3` |
| `neve-600` | — | `#7b8798` |
| `neve-700` | — | `#5b6577` |
| `neve-900` | — | `#1c2230` |
| `neve-950` | — | `#0a0e16` |

Ambas as escalas são ordenadas pela luminância medida: número maior é sempre
mais escuro. O nome nunca contradiz o valor.

### Tintas

| Primitiva | Escuro | Claro | Origem |
|---|---|---|---|
| `ambar-400` / `ambar-800` | `#e3b341` | `#7d5600` | herdado do `#e3b341` já presente no código (linhagem SQL\*Plus) |
| `persimmon-400` / `persimmon-800` | `#ff8a5c` | `#a83a0c` | discordância — deliberadamente não é amarelo de aviso |
| `indigo-400` / `indigo-800` | `#8b9bff` | `#3f49c4` | ausência — lê como vazio, não como erro |
| `carmim-400` / `carmim-800` | `#ff6b72` | `#c02434` | falha real de operação |

### Escala de espaçamento

Formalizada a partir do que já existe. Quatro degraus, nada fora deles:
`0`, `1`, `2`, `1 2`. Valor arbitrário é dívida e o teste reprova.

### Bordas

Dois estilos, com regra de uso: `round` para superfície de conteúdo (painel,
cartão), `thick` para camada que flutua (dialog, modal). Nenhum terceiro.

## 6. Camada 2 — tokens semânticos

O que a coisa **significa**. Componentes consomem **apenas** esta camada.
Cada token de texto declara sobre quais fundos é válido (§3 do guia).

### Superfícies

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `$fundo` | `ardosia-950` | `neve-050` | tela |
| `$superficie` | `ardosia-900` | `neve-150` | recuado: barra de status, sidebar |
| `$painel` | `ardosia-850` | `neve-000` | superfície de conteúdo — **opaca** (§5) |
| `$superficie-elevada` | `ardosia-800` | `neve-100` | linha sob cursor, item ativo |

### Estrutura

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `$borda` | `ardosia-700` | `neve-300` | divisória entre superfícies |
| `$borda-forte` | `ardosia-500` | `neve-600` | contorno de controle, anel de foco |

`$borda` fica em ~1.4:1 por desenho: ela não separa regiões sozinha, o
preenchimento das superfícies faz isso. Onde o contorno **precisa** ser
percebido — controle de formulário, foco — o token é `$borda-forte`, calibrado
em ≥ 3:1.

### Texto

| Token | Escuro | Claro | Válido sobre |
|---|---|---|---|
| `$texto` | `ardosia-100` | `neve-900` | `$fundo`, `$superficie`, `$painel`, `$superficie-elevada` |
| `$texto-apoio` | `ardosia-300` | `neve-700` | idem |
| `$texto-forte` | `ardosia-050` | `neve-950` | idem |
| `$texto-desabilitado` | `ardosia-450` | `neve-500` | idem (piso de interface, 3:1) |

**Nenhum token de texto é válido sobre preenchimento translúcido.** Sobre
superfície translúcida, use o texto da superfície de baixo.

### Tinta — eixo de identidade

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `$identidade` | `ambar-400` | `ambar-800` | conexão/ambiente, favorito (`★`), anel de foco, ação primária |

### Tinta — eixo de veredito (dados)

Válidos **somente** sobre `$painel`, `$superficie` e `$superficie-elevada`.

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `$veredito-igual` | `ardosia-300` | `neve-700` | `OK` — **sem tinta** |
| `$veredito-difere` | `persimmon-400` | `persimmon-800` | `DIFERE` |
| `$veredito-ausente` | `indigo-400` | `indigo-800` | `AUSENTE` |

`$veredito-igual` é um token próprio, não um apelido de `$texto-apoio`: ele
tem a mesma cor hoje, mas precisa de chave própria para o teste de paridade e
para que reverter o risco assumido seja a troca de um valor.

`OK*` (normalizado) é `$veredito-igual` mais um glifo, nunca uma cor nova —
estado comunicado além da cor, como pede o §11.

### Tinta — eixo de operação

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `$op-falha` | `carmim-400` | `carmim-800` | conexão ou execução que falhou |

**Sucesso de operação não tem token.** É a ausência de alarme.

**`op-pendente` foi cortado do sistema.** Ele existiria para dois usos em
`settings.py` ("nenhum encontrado", "será gerada no primeiro uso"), ficaria
quase indistinguível de `$identidade`, e `$texto-apoio` mais redação resolve os
dois. Aplicação da pergunta 2 do §15.

### Contraste verificado

Calculado, não impressão. **Zero falhas** nos dois temas; paridade de chaves
entre escuro e claro confirmada. Menor margem: `$texto-apoio` claro sobre
`$superficie`, 5.04:1.

## 7. Camada 3 — componentes

Consomem só a camada 2. Nome por função. Variantes fechadas, sem porta dos
fundos para estilo arbitrário.

### `Dialog` (novo)

Substitui os 24 blocos `border: thick $accent` copiados em 13 arquivos.

- Props: `titulo`, `largura` ∈ `sm|md|lg`, `tom` ∈ `neutro|destrutivo`.
- Entrega o chrome, o cabeçalho, a área de ações e a prisão de foco.
- **Regra de uso:** qualquer camada que flutua sobre o conteúdo. Se não flutua,
  é `Panel`.

### `EmptyState` (novo)

Resolve os 22 estados vazios mudos.

- Props: `o_que` (o que é aquilo), `porque` (por que está vazio),
  `acao` (rótulo + callback) — **`acao` é obrigatório**.
- A obrigatoriedade é o ponto: torna impossível repetir "Nenhum X configurado"
  sem oferecer a saída.
- **Regra de uso:** toda lista, tabela e árvore, quando vazia.

### `Veredito` (novo)

Substitui `[green]OK[/]` / `[yellow]DIFF[/]` / `[red]ABSENT[/]`.

- Prop única: `status` ∈ `igual|igual-normalizado|difere|ausente`.
- Renderiza cor **e** glifo, para que o estado não dependa só da cor.
- **Regra de uso:** todo lugar que exibe resultado de comparação.

### `StatusOperacao` (novo)

- Prop: `estado` ∈ `ok|falha|executando`.
- `ok` renderiza sem tinta; `falha` usa `$op-falha`; `executando` usa
  `$identidade`.

### `Panel` (existente)

Mantido. Passa a consumir `$painel`/`$borda` em vez de `$surface`/`$accent`.

## 8. Estados obrigatórios (§8)

Nenhum componente de listagem ou formulário é considerado pronto sem os cinco:

| Estado | Regra no dbqm |
|---|---|
| Vazio | `EmptyState` com ação. Sem exceção. |
| Carregando | Esqueleto com a forma do conteúdo (linhas de tabela), não spinner centralizado. |
| Erro | Causa e saída. Nunca a mensagem crua do driver sozinha — o padrão já adotado em `db_manager` para o Instant Client é o modelo. |
| Desabilitado | Distinto visualmente **e** com o motivo alcançável (tooltip ou linha de apoio). |
| Somente leitura | Distinto de desabilitado: parece conteúdo, não formulário quebrado. Relevante no `package_editor` e no `browser`. |

## 9. Escrita da interface (§10)

- Rótulo de ação no imperativo, e o mesmo verbo atravessa o fluxo: botão
  "Exportar" → confirmação "Exportado".
- **Só confirmar o que a pessoa não vê acontecer.** Renomear uma consulta na
  lista à frente dela dispensa aviso; exportação concluída, importação de bundle
  e execução em grupo não.
- Validação de formulário fica ao lado do campo, nunca como notificação
  flutuante. O `OracleClientDirModal` já segue esse padrão e serve de referência.
- **Acentuação:** rótulos de UI seguem a convenção existente do projeto e
  **omitem acentos**. Isso é decisão registrada, não descuido — o design system
  não a altera.

## 10. Piso de acessibilidade (§11)

Critério de aceite de cada peça, não fase posterior.

- Contraste calculado: 4.5:1 texto, 3:1 interface. Garantido pelo teste 3.
- Foco visível em todo controle — hoje há 3 regras `:focus` em 58 blocos de CSS.
  O anel de foco passa a ser `$identidade`, definido uma vez no tema em vez de
  por tela; `$borda-forte` é o contorno em repouso.
- Ordem de foco segue a ordem visual.
- Estado comunicado além da cor: `Veredito` renderiza glifo junto da cor.
- `Dialog` prende o foco enquanto aberto e o devolve de onde veio.

## 11. Os quatro testes de manutenção (§13)

Cada um verificado **revertendo a regra que guarda** — um teste que passa nos
dois casos é pior que teste nenhum.

1. **Cor literal fora de token** (`tests/design/test_sem_cor_literal.py`)
   Varre `dbqm/` por hex e por nomes de cor em markup Rich, e falha apontando
   arquivo e linha. Lista de exceções explícita e vazia ao final da migração.
2. **Paridade de tokens entre temas** (`test_paridade_temas.py`)
   Todo token do tema escuro existe no claro e vice-versa. É o teste que impede
   a violação do §4 que hoje existe.
3. **Contraste calculado** (`test_contraste.py`)
   Percorre os pares declarados em "válido sobre" e falha abaixo do piso.
   Só é possível porque os tokens Plano são hex explícitos, não `auto %`.
   Substitui o atual `test_dark_palette_matches_prototype`, que trava valores em
   vez de garantir propriedades.
4. **Inventário de componentes** (`test_inventario.py`)
   Falha quando aparece um segundo componente com a mesma função, e quando um
   `Dialog`/`Veredito` é usado sem variante declarada.

## 12. Ordem de migração (§14)

A ordem é a garantia de que uma regressão seja atribuível. **1 e 4 nunca
invertem.**

1. **`dbqm/design/tokens.py` com os valores ATUAIS.** Camada semântica apontando
   para as cores de hoje, feias inclusive. Nada muda na tela.
2. **Teste 1 em modo de aviso.** Conta 210 e vira a métrica da migração.
3. **Substituir os 210 literais por token,** ainda sem redesenhar. Achar-e-trocar
   revisável, sem mudança visual.
4. **Trocar os valores dos tokens para a paleta Plano.** É aqui, e só aqui, que
   o produto muda de aparência — num único arquivo, reversível.
5. **Componentes,** do mais usado para o menos: `Dialog` (13 arquivos),
   `EmptyState` (23 pontos), `Veredito`, `StatusOperacao`.
6. **Teste 1 em modo de erro.** A dívida para de crescer.

Cada passo é um commit próprio, e cada um mantém a suíte verde.

## 13. Antipadrões específicos deste projeto

| Antipadrão | O que aconteceu / aconteceria aqui |
|---|---|
| Token declarado e não usado | `text-dim`, `text-bright`, `panel-active`: 3 de 6 variáveis do tema são mortas |
| Teste que trava valor em vez de propriedade | `test_dark_palette_matches_prototype` protege um token morto e impede olhar de novo |
| Paleta paralela por causa da regra de camadas | `html_report.py` inventou 14 hex porque não podia importar `ui/` |
| Cor saturada gasta em chrome | roxo `#bc8cff` em 24 bordas de dialog, zero informação |
| Estado vazio que só diz que está vazio | 22 de 23 ocorrências |
| Dois eixos de significado com a mesma paleta | veredito e status de operação ambos em verde/amarelo/vermelho |

## 14. Fora de escopo desta rodada

- Tema claro alternativo além do par Plano escuro/claro.
- Redesenho de layout de qualquer tela — o sistema muda cor, tipo de borda e
  componentes de chrome, não a disposição.
- Os 104 markups do `cli.py` entram no passo 3 da migração, mas o CLI não ganha
  componentes novos.
