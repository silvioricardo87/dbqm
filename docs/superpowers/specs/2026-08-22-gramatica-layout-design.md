# Gramática de layout do dbqm

Data: 2026-08-22
Fase 1 (sistema de cor): `docs/superpowers/specs/2026-08-22-design-system-design.md`

## 1. Por que esta fase existe

A fase 1 entregou o sistema de **cor** — 15 tokens semânticos, contraste calculado,
dois eixos que não se confundem, e sete guardas que impedem a dívida de voltar.

Ela não tocou em **estrutura**. O resultado é um produto com paleta disciplinada e
layout improvisado: cada uma das 16 telas respondeu por conta própria a quatro
perguntas que nunca foram decididas.

Isto veio de uso real, não de auditoria: o mantenedor relatou que a lista de
conexões com mais de duas linhas fica impossível de ler, que as abas de pasta não
fazem sentido para muitas consultas, e que a tela de configurações "está horrível,
com um monte de botão alinhado no centro".

## 2. Levantamento

Medido no código e nas telas renderizadas, antes de qualquer proposta.

| Medida | Valor |
|---|---|
| Botões no produto | **103**, em 16 arquivos de tela |
| Telas usando `Panel` como moldura de seção | 6 de 16 |
| Telas **sem nenhuma** moldura de seção | **10 de 16** |
| `border:` cru desenhado fora de um componente | 6 ocorrências |
| Mecanismos de navegação distintos | **5** (abas-botão, `Select`, `OptionList`, `ListView`, `DataTable`) |
| Telas com `align: center` em cluster de botão | 8 — piores: `package_editor` (11), `query_manage` (11), `group_manage` (10) |
| Colunas por consulta salva | mediana **9**, mínimo 1, máximo **36** (57 de 68 com colunas explícitas) |
| Pastas de consulta | **16**, todas com o prefixo `Mapfre Sustentacao/`, em abas-botão com scroll lateral |

**Três defeitos concretos que o levantamento expôs:**

1. **A tela de Configurações esconde uma seção inteira.** A seção Oracle Instant
   Client existe no código e não renderiza — cai abaixo da dobra, sem indicação
   de que há mais conteúdo.
2. **A tabela de resultado é ilegível a 7 colunas** — abaixo da mediana. Cabeçalhos
   e datas truncados (`last_ana…`, `2018-03-…`), com a hora numa segunda linha.
   Verificado executando consulta real contra `MGORA7ORA9`.
3. **`query_list.py` trunca descrição em 35 caracteres** com o comentário
   *"keep line readable"* — um remendo em volta da causa, não a correção dela.

**Uma correção de instrumento, registrada porque afeta a confiança nos números:**
a primeira tentativa de medir transbordo contava linhas ocupadas no SVG e deu
"cheia" para todas as telas. A métrica estava errada — o SVG sempre preenche a altura
do terminal. Foi descartada e o transbordo verificado caso a caso.

## 3. O diagnóstico

Não são 16 telas com problemas próprios. São **quatro perguntas nunca respondidas**:

1. O que é uma seção?
2. Como se navega num conjunto?
3. Qual a densidade de uma linha?
4. Onde ficam as ações?

Cada tela respondeu sozinha, e é por isso que o produto tem três vocabulários de
moldura, cinco de navegação e 103 botões sem regra de ancoragem.

## 4. Decisão — o que é uma seção

**`Panel` é a única moldura de seção do produto.** Toda tela é composta de painéis;
nada fica solto no fundo. `border:` cru fora de um componente de moldura vira erro
de teste.

**Descartado:** deixar telas simples sem moldura "porque não precisam". Foi
exatamente assim que se chegou a três vocabulários — cada tela decidindo sozinha se
precisava. A regra existe para **remover** a decisão, não para otimizá-la caso a caso.

**Dependência:** as 10 telas sem moldura ganham estrutura visível, e isso consome
altura. Como a tela de Configurações já transborda hoje, esta decisão **só fecha
junto com a de densidade** (§6), que resolve o que acontece quando não cabe.

## 5. Decisão — como se navega num conjunto

O mecanismo sai da **cardinalidade**, não do gosto:

| Quantos itens | Mecanismo | Razão |
|---|---|---|
| até ~7, fixos | abas | cabem na largura, e a escolha fica visível |
| número variável | `Select` com contagem | 16 pastas não cabem em aba nenhuma |
| coisas escolhíveis | `OptionList` com hierarquia de 2–3 linhas | conexões, consultas, objetos |
| dados tabulares | `DataTable` | resultado de consulta, histórico |

**`ListView` sai do vocabulário.** Hoje faz o mesmo que `OptionList` em dois lugares,
e dois componentes para uma função é o que o teste de inventário reprova.

### Hierarquia do item de lista

Um item de lista **nunca é uma string concatenada**. Ele tem até três linhas:

1. **Identidade** — o que a pessoa procura, em negrito, sozinha na primeira linha.
2. **Desambiguação** — tipo, alvo, conexão; recuada, em `$texto-apoio`.
3. **Contexto** — descrição; recuada, em `$texto-desabilitado`, opcional.

A hierarquia faz o trabalho que um separador faria, e faz melhor: também diz *o que
é cada coisa*. Torna a truncagem de 35 caracteres do `query_list.py` desnecessária.

## 6. Decisão — qual a densidade de uma linha

**A tabela nunca trunca para caber.** Colunas na largura real, com:

- **coluna-chave fixa** (`fixed_columns=1`), que nunca sai de vista ao rolar
- **zebra nas linhas** (`zebra_stripes=True`)
- **rolagem lateral** para as demais colunas
- **modo registro** por atalho, um registro por tela, campos empilhados

A tecla do modo registro não é fixada aqui: ela sai do conjunto de atalhos já em
uso na tela de resultado, e é escolhida no plano para não colidir com nenhum.

O Textual já oferece `fixed_columns` e `zebra_stripes`; `result_table.py` não usa
nenhum dos dois. A plataforma tinha a resposta e o produto não pegou.

**A razão é o domínio, não a estética.** O dbqm existe para **comparar**, e comparar
exige saber *de qual registro* é a linha. Truncar a chave para caber mais colunas
destrói justamente a informação sem a qual as outras não significam nada. Rolar sem
fixar a chave tem o mesmo efeito, dois segundos depois.

**Descartado — colunas prioritárias** (mostrar N, esconder o resto): exigiria o
produto adivinhar quais colunas importam, e são as consultas do usuário que decidem
isso. Adivinhação silenciosa é pior que rolagem explícita.

**Descartado — só modo registro:** mata a comparação, que é a razão de a tela existir.

**Custo aceito:** rolagem lateral é mais lenta que ver tudo de uma vez. Para
consultas de 4–6 colunas, que hoje cabem, nada muda. Da mediana para cima, troca-se
"vejo tudo, ilegível" por "vejo parte, legível, e navego".

**Consequência sobre a fase 1:** o esqueleto de carregamento foi aprovado com
`colunas=4`. A mediana medida é **9**. O valor está errado para o caso mediano e é
corrigido aqui.

## 7. Decisão — onde ficam as ações

**Botão é ação, nunca navegação nem menu.**

- Ações ficam **ancoradas ao painel que operam**, alinhadas à esquerda com o conteúdo.
- **Ação destrutiva fica separada** das demais.
- Centralizar um cluster só faz sentido quando ele **é** a tela — um diálogo. Numa
  tela de trabalho, centralizar desconecta a ação daquilo que ela opera.
- `Ferramentas` vira **lista escolhível**: quatro botões de largura total são quatro
  botões fingindo ser um menu.

## 8. As 16 telas (e um widget)

São 16 arquivos em `dbqm/ui/screens/`. `result_table` entra na lista por ser
consumido por várias delas e por concentrar a decisão de densidade — é widget,
não tela. Telas marcadas **padrão** estabelecem o que as demais consomem.

| Tela | O que muda | Papel |
|---|---|---|
| `connections` | Lista com hierarquia de 3 linhas; fim da concatenação | padrão |
| `query_exec` | Abas de 16 pastas → `Select` com contagem; lista com hierarquia; esqueleto com 9 colunas | padrão |
| `result_table` *(widget)* | Chave fixa, zebra, rolagem lateral, modo registro | padrão |
| `settings` | Um painel por assunto; caminho longo elidido no meio; fim do transbordo | aplica |
| `ferramentas` | Quatro botões de largura total → lista escolhível | aplica |
| `config_port` | Dois botões flutuando no vazio ganham painel e contexto | aplica |
| `group_run` | Abas → `Select`; lista com hierarquia | aplica |
| `query_manage` | 15 botões reancorados; fim do cluster centralizado | aplica |
| `group_manage` | 18 botões reancorados; moldura de seção | aplica |
| `package_editor` | 12 botões reancorados; 11 centralizações removidas | aplica |
| `oracle_clients` | Bordas cruas → `Panel`; título sai de dentro da caixa | aplica |
| `browser` | Lista de objetos ganha hierarquia | aplica |
| `history` | Tabela ganha chave fixa e zebra | aplica |
| `adhoc` | 3 centralizações removidas | aplica |
| `exec_routine`, `template_manage`, `group_exec` | Moldura de seção e ancoragem de ações | aplica |

## 9. Ordem de aplicação

Cada passo estabelece o que o seguinte consome.

1. **Moldura de seção** — `Panel` como única moldura, e o guarda que reprova borda
   crua. Tudo depois depende disto.
2. **Densidade da tabela** — chave fixa, zebra, rolagem, modo registro. Libera a
   altura que a moldura consome.
3. **Lista com hierarquia** — conexões e consultas.
4. **Navegação por cardinalidade** — `Select` onde havia abas; `ListView` sai.
5. **Ancoragem de ações** — 103 botões reancorados; `Ferramentas` e
   `Exportar/Importar` deixam de ser botão-menu.
6. **Travar** — o inventário de layout em modo erro.

## 10. Os guardas

Mesma disciplina da fase 1: cada regra ganha um guarda, e **cada guarda é verificado
quebrando a regra que ele protege**.

| Guarda | Reprova |
|---|---|
| `sem_borda_crua` | `border:` fora de um componente de moldura |
| `sem_listview` | `ListView`, que duplica a função do `OptionList` |
| `sem_cluster_centralizado` | `align: center` em grupo de botão fora de diálogo |
| `rotulo_nao_achatado` | item de lista montado por concatenação numa string |
| `tabela_com_chave_fixa` | `DataTable` de resultado sem `fixed_columns` |

**Limites já conhecidos**, herdados da fase 1 e aceitos: uma varredura textual não
vê construção por interpolação, constante definida fora da árvore varrida, nem
markup montado noutra camada. São limites escolhidos, não descuidos, e devem ser
nomeados no código de cada guarda.

## 11. Fora de escopo

- **Conversão de `$text-muted` e `[dim]`** (96 usos) para tokens próprios. É trabalho
  da camada de cor, já declarado como lacuna conhecida na fase 1.
- **A pergunta do "aviso".** Os toasts de `information` e `warning` ficaram na mesma
  cor porque a paleta não tem cor de aviso por desenho. A decisão real — se o dbqm
  tem o conceito de aviso, ou se as 78 chamadas `severity="warning"` devem ser
  auditadas entre informativo e falha — é do mantenedor e não é resolvida aqui.
- **Redesenho de fluxo.** Esta fase muda estrutura, não o que cada tela faz nem em
  que ordem os passos acontecem.
