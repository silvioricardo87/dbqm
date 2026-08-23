"""Settings screen — um painel por assunto (gramatica de layout, secao 4).

Antes desta tarefa a tela tinha UM painel chamado "CONFIG DA APLICACAO" com
quatro assuntos dentro (tema, auditoria, exportacao e Oracle Instant Client),
separados so por um rotulo em negrito, e tres botoes que fingiam ser menu. A
queixa do mantenedor foi textual: "a tela de configuracoes esta horrivel com
um monte de botao alinhado no centro e dentro da tela de configuracoes do
sistema, esta tudo muito confuso".

Agora cada assunto tem sua moldura, e a navegacao para as duas telas mais
fundas (portabilidade e gerenciador de clients) e uma LISTA, nao um botao —
secao 7 da gramatica: botao e acao, nunca navegacao. Os botoes que sobram
abrem um dialogo sobre o assunto do painel em que vivem.
"""
from __future__ import annotations

import re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, ContentSwitcher, OptionList, Select, Static, Switch

from dbqm.ui.theme import get_theme
from dbqm.ui.utils import NavSelect, NavVerticalScroll
from dbqm.ui.widgets.lista_hierarquica import OpcaoNomeada, item_hierarquico
from dbqm.ui.widgets.panel import Panel

#: Um caractere, e nao "...": o rotulo de caminho tem 30 celulas num
#: terminal de 80, e cada coluna gasta com o marcador e uma coluna a
#: menos de caminho.
RETICENCIA = "\u2026"

#: Separadores de caminho das duas familias, capturados para que o corte
#: possa remontar o texto original byte a byte (um caminho do Windows pode
#: misturar os dois: `C:\\Users\\ricar/exports`).
_SEPARADOR = re.compile(r"([\\/])")


def elidir_caminho(caminho: str, largura: int) -> str:
    """Encurta *caminho* para caber em *largura* colunas cortando o MEIO.

    O inicio e o fim de um caminho sao o que o identificam — a raiz diz de
    que arvore ele vem, o ultimo segmento diz de que diretorio ou arquivo se
    trata. O meio e o descartavel. A alternativa que o Textual da de graca
    (deixar o texto quebrar sozinho) faz o contrario do que se precisa:
    quebra no meio de um NOME e, quando o painel acaba, e justamente o fim do
    caminho que some. A tela pintava
    `C:\\Users\\ricar\\AppData\\Local\\Tem` / `p\\pytest-of-ricar\\pytest-626\\tes`
    e nada depois disso.

    O corte prefere cair entre segmentos: metade de um nome de diretorio nao
    identifica nada, e ainda parece um nome de verdade. So quando nao ha
    separador aproveitavel e que se corta por caractere — que continua sendo
    melhor que cortar so o fim.

    O resultado nunca passa de *largura*, inclusive nas larguras absurdas: e
    dai que vem o teste que varre largura por largura.
    """
    texto = str(caminho)
    if largura <= 0:
        return ""
    if len(texto) <= largura:
        return texto
    if largura <= len(RETICENCIA):
        return RETICENCIA[:largura]

    # `split` com grupo capturante intercala segmentos e separadores:
    # ['C:', '/', 'Users', '/', ...]. Indice par = segmento, impar = separador.
    pecas = _SEPARADOR.split(texto)
    if len(pecas) >= 5:  # raiz + separador + ao menos dois segmentos
        cabeca = "".join(pecas[:3])
        if len(cabeca) + len(RETICENCIA) < largura:
            cauda = ""
            i = len(pecas) - 1
            while i >= 3:
                candidata = "".join(pecas[i:])
                if len(cabeca) + len(RETICENCIA) + len(candidata) > largura:
                    break
                cauda = candidata
                i -= 2
            if cauda:
                return cabeca + RETICENCIA + cauda

    sobra = largura - len(RETICENCIA)
    frente = (sobra + 1) // 2
    fim = sobra - frente
    return texto[:frente] + RETICENCIA + (texto[len(texto) - fim:] if fim else "")


class SettingsScreen(Vertical):
    """Tela de configuracoes: um painel por assunto, em duas colunas.

    Hospeda tambem as duas telas mais fundas da area de configuracao
    (`ConfigPortScreen` e `OracleClientsScreen`) num `ContentSwitcher` —
    mesmo mecanismo que `FerramentasScreen` ja usa para hospedar telas
    inteiras dentro de uma aba. Ver `_abrir_ferramenta`.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        height: 1fr;
    }
    SettingsScreen ContentSwitcher {
        height: 1fr;
    }
    SettingsScreen #settings-main {
        height: 1fr;
    }
    SettingsScreen .settings-coluna {
        width: 1fr;
        height: 1fr;
        padding: 1 1;
    }
    /* `auto` mede o conteudo desde a Task 6; a coluna e que rola quando a
       soma dos paineis passa da tela. Sem isto cada painel esticaria ate a
       altura da COLUNA e so o primeiro de cada uma apareceria. */
    SettingsScreen .settings-coluna > Panel {
        height: auto;
        margin-bottom: 1;
    }
    /* O padding vertical do corpo custa 2 linhas POR PAINEL, e agora sao
       seis paineis: 12 linhas de uma tela de 24 gastas em ar. O padding
       horizontal fica — e ele que separa o texto da borda. */
    SettingsScreen .settings-coluna > Panel > #panel-body {
        padding: 0 1;
    }
    SettingsScreen .settings-hospede {
        height: 1fr;
    }
    SettingsScreen #settings-theme-select {
        width: 1fr;
    }
    SettingsScreen .settings-linha {
        height: auto;
    }
    SettingsScreen .settings-nota {
        height: auto;
        color: $texto-apoio;
    }
    SettingsScreen .settings-acoes {
        height: auto;
    }
    SettingsScreen .settings-acoes Button {
        margin: 0 1 0 0;
    }
    SettingsScreen #settings-ferramentas-list {
        height: auto;
    }
    """

    ORACLE_CLIENT_ORIGINS = {
        "config": "configuracao do dbqm",
        "clients": "clients instalados pelo dbqm",
        "package": "pasta clients/ do pacote",
        "ORACLE_HOME": "variavel de ambiente ORACLE_HOME",
        "scan": "deteccao automatica no sistema",
    }

    #: As telas hospedadas: (chave, identidade, desambiguacao). A chave
    #: viaja como DADO na opcao (`OpcaoNomeada.nome`), nunca como `id` — o
    #: motivo esta na docstring de `OpcaoNomeada`.
    #:
    #: O texto e CURTO por exigencia de layout, nao por gosto: a coluna da
    #: lista tem 30 celulas num terminal de 80, e uma linha mais larga que
    #: isso quebra sozinha no render — a continuacao volta para a coluna 0,
    #: a mesma da identidade da entrada seguinte, que e exatamente a
    #: confusao que esta fase existe para desfazer. `item_hierarquico` nao
    #: tem como recuar a quebra automatica (esta escrito na docstring dele).
    #: `test_lista_de_mais_configuracoes_nao_quebra_a_80_colunas` cobra.
    FERRAMENTAS = (
        (
            "oracle-clients",
            "Oracle Instant Clients",
            "instalar, remover, escolher",
        ),
        (
            "portabilidade",
            "Exportar / Importar",
            "bundle .dbqm com senha",
        ),
    )

    #: Chave -> id do container onde aquela tela e montada.
    _HOSPEDES = {
        "oracle-clients": "settings-host-oracle-clients",
        "portabilidade": "settings-host-portabilidade",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dir_exportacao = ""
        self._montadas: set[str] = set()
        self._client_oracle: tuple[str | None, str] = (None, "none")
        self._client_oracle_erro = ""

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="settings-main"):
            with Horizontal(id="settings-main"):
                with NavVerticalScroll(
                    id="settings-col-esquerda", classes="settings-coluna"
                ):
                    with Panel("🎨  TEMA", id="settings-panel-tema"):
                        yield NavSelect(
                            [
                                ("Plano Escuro", "plano-escuro"),
                                ("Plano Claro", "plano-claro"),
                            ],
                            id="settings-theme-select",
                            allow_blank=False,
                        )

                    with Panel("📋  AUDITORIA", id="settings-panel-auditoria"):
                        with Vertical(classes="settings-linha"):
                            yield Switch(id="settings-audit-switch")
                            yield Static(
                                "Registra execucoes de consultas e grupos.",
                                id="settings-audit-desc",
                                classes="settings-nota",
                            )

                    with Panel("📁  EXPORTACAO", id="settings-panel-exportacao"):
                        yield Static(
                            "Onde os arquivos exportados sao salvos.",
                            classes="settings-nota",
                        )
                        yield Static(
                            "", id="settings-export-dir-current", markup=True
                        )
                        with Horizontal(classes="settings-acoes"):
                            yield Button(
                                "Alterar diretorio",
                                variant="primary",
                                id="btn-export-dir",
                            )
                        with Vertical(classes="settings-linha"):
                            yield Switch(id="settings-export-subdirs-switch")
                            yield Static(
                                "Subdiretorios por tipo (grupos, DDL, SQL).",
                                classes="settings-nota",
                            )

                with NavVerticalScroll(
                    id="settings-col-direita", classes="settings-coluna"
                ):
                    with Panel(
                        "🔌  ORACLE INSTANT CLIENT", id="settings-panel-oracle"
                    ):
                        # Curto de proposito: cada linha de prosa aqui e
                        # uma linha a menos para a lista de MAIS
                        # CONFIGURACOES, que num terminal de 24 fica logo
                        # abaixo deste painel.
                        yield Static(
                            "Prioritario sobre o ORACLE_HOME do sistema, "
                            "que pode apontar para outra arquitetura.",
                            classes="settings-nota",
                        )
                        yield Static(
                            "", id="settings-oracle-client-current", markup=True
                        )
                        with Horizontal(classes="settings-acoes"):
                            yield Button(
                                "Definir caminho",
                                variant="primary",
                                id="btn-oracle-client-dir",
                            )

                    # Logo abaixo do painel de Oracle de proposito: a
                    # entrada do gerenciador de clients fica encostada no
                    # status que faz alguem querer abri-lo.
                    with Panel(
                        "🧰  MAIS CONFIGURACOES", id="settings-panel-ferramentas"
                    ):
                        yield OptionList(id="settings-ferramentas-list")

                    with Panel("🔑  FERNET KEY", id="settings-panel-fernet"):
                        yield Static("", id="settings-fernet-status", markup=True)

            yield Vertical(
                id="settings-host-portabilidade", classes="settings-hospede"
            )
            yield Vertical(
                id="settings-host-oracle-clients", classes="settings-hospede"
            )

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = get_theme(settings.theme).name

        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

        subdirs_switch = self.query_one("#settings-export-subdirs-switch", Switch)
        subdirs_switch.value = settings.create_export_subdirs

        lista = self.query_one("#settings-ferramentas-list", OptionList)
        lista.clear_options()
        for chave, identidade, desambiguacao in self.FERRAMENTAS:
            lista.add_option(
                OpcaoNomeada(item_hierarquico(identidade, desambiguacao), chave)
            )

        self._dir_exportacao = settings.default_export_dir
        self._refresh_oracle_client_status()
        self._pintar_caminhos()

        self.call_after_refresh(self._set_initial_focus)

    def on_resize(self, event) -> None:
        """Repinta os caminhos: a largura util mudou.

        As duas colunas sao `1fr`, entao a largura de um rotulo depende do
        terminal — 30 celulas a 80 colunas, 52 a 120. Elidir contra uma
        constante acertaria uma largura e erraria as outras.
        `call_after_refresh` porque durante o proprio evento de resize as
        regioes dos filhos ainda sao as antigas.
        """
        self.call_after_refresh(self._pintar_caminhos)

    # ------------------------------------------------------------------
    # Caminhos longos
    # ------------------------------------------------------------------

    def _pintar_caminhos(self) -> None:
        """Repinta os tres rotulos que carregam caminho.

        Repintar e so formatar: nenhuma destas funcoes vai ao disco. A
        deteccao do Instant Client (`resolve_oracle_client_dir`) VAI — ela
        varre os diretorios de instalacao comuns do sistema — e por isso
        mora em `_refresh_oracle_client_status`, chamada quando a resposta
        pode ter mudado, e nao aqui, que roda a cada resize do terminal.
        """
        self._pintar_dir_exportacao()
        self._pintar_client_oracle()
        self._pintar_fernet()

    @staticmethod
    def _largura_util(rotulo: Static) -> int:
        """Quantas colunas o rotulo tem para pintar.

        Medido no widget montado: `content_region` ja desconta a borda do
        painel, o padding do corpo e o do proprio rotulo. Enquanto o layout
        nao aconteceu ela mede 0 — e nesse estado nao se elide nada, porque
        elidir contra zero apagaria o caminho inteiro. `on_resize` repinta
        assim que a regiao existe.
        """
        return rotulo.content_region.width

    def _refresh_export_dir_label(self, configured: str) -> None:
        self._dir_exportacao = configured
        self._pintar_dir_exportacao()

    def _pintar_dir_exportacao(self) -> None:
        rotulo = self.query_one("#settings-export-dir-current", Static)
        largura = self._largura_util(rotulo)
        if self._dir_exportacao:
            caminho = self._dir_exportacao
            sufixo = ""
        else:
            caminho = str(Path.cwd())
            sufixo = "\n[$texto-desabilitado](diretorio de execucao)[/]"
        if largura:
            caminho = elidir_caminho(caminho, largura)
        rotulo.update(f"[b]Diretorio atual:[/]\n{caminho}{sufixo}")

    def _refresh_oracle_client_status(self) -> None:
        """Redescobre qual Instant Client esta em uso, e de onde veio.

        Faz I/O (ver `resolve_oracle_client_dir`): so e chamada quando a
        resposta pode ter mudado — na montagem e depois de o modal de
        caminho salvar. Um caminho configurado mas inutilizavel e reportado
        como ERRO, e nao substituido em silencio: esse silencio e o que
        tornava o conflito de ORACLE_HOME tao dificil de diagnosticar.
        """
        from dbqm.core.db_manager import OracleClientConfigError, resolve_oracle_client_dir

        try:
            self._client_oracle = resolve_oracle_client_dir()
            self._client_oracle_erro = ""
        except OracleClientConfigError as e:
            self._client_oracle = (None, "none")
            self._client_oracle_erro = str(e)
        self._pintar_client_oracle()

    def _pintar_client_oracle(self) -> None:
        label = self.query_one("#settings-oracle-client-current", Static)
        if self._client_oracle_erro:
            label.update(f"[b]Client em uso:[/] [$op-falha]{self._client_oracle_erro}[/]")
            return
        path, origin = self._client_oracle
        if not path:
            label.update(
                "[b]Client em uso:[/] [$texto-apoio]nenhum encontrado[/] "
                "[$texto-desabilitado](thick mode indisponivel)[/]"
            )
            return
        source = self.ORACLE_CLIENT_ORIGINS.get(origin, origin)
        largura = self._largura_util(label)
        mostrado = elidir_caminho(str(path), largura) if largura else str(path)
        label.update(f"[b]Client em uso:[/]\n{mostrado}\n[b]Origem:[/] {source}")

    def _pintar_fernet(self) -> None:
        from dbqm.core.paths import KEY_FILE

        status = self.query_one("#settings-fernet-status", Static)
        exists = KEY_FILE.exists()
        state = "Presente" if exists else "[$texto-apoio]Sera gerada no primeiro uso[/]"
        largura = self._largura_util(status)
        local = str(KEY_FILE)
        if largura:
            local = elidir_caminho(local, largura)
        status.update(
            f"[b]Status:[/b] {state}\n"
            f"[b]Local:[/b] [$texto-desabilitado]{local}[/]\n\n"
            "[$texto-desabilitado]Criptografa as senhas de conexao salvas. "
            "Nao ha acao manual: ela e criada automaticamente.[/]"
        )

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#settings-theme-select", Select).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Telas hospedadas
    # ------------------------------------------------------------------

    def _construir(self, chave: str):
        if chave == "oracle-clients":
            from dbqm.ui.screens.oracle_clients import OracleClientsScreen

            return OracleClientsScreen(id="settings-oracle-clients-screen")
        if chave == "portabilidade":
            from dbqm.ui.screens.config_port import ConfigPortScreen

            return ConfigPortScreen(id="settings-config-port-screen")
        raise ValueError(f"ferramenta de configuracao desconhecida: {chave}")

    def _abrir_ferramenta(self, chave: str) -> None:
        """Troca a area de configuracoes pela tela *chave*, montando na 1a vez.

        Estas duas telas ficaram INALCANCAVEIS da v1.17.0 ate aqui: os
        botoes que as abriam consultavam `#screen-area`, removido em
        e02b8a8 quando o app virou uma shell de abas unica, e o
        `except Exception` transformava a falha num toast de erro. Elas
        voltam pelo mecanismo que a shell ja tem para hospedar uma tela
        inteira dentro de uma aba — o mesmo `ContentSwitcher` de
        `FerramentasScreen` — em vez de um `push_screen`, que tiraria da
        vista o cabecalho, as abas e a barra de acoes.
        """
        hospede = self.query_one(f"#{self._HOSPEDES[chave]}", Vertical)
        if chave not in self._montadas:
            hospede.mount(self._construir(chave))
            self._montadas.add(chave)
        self.query_one(ContentSwitcher).current = self._HOSPEDES[chave]

    def voltar_ao_inicio(self) -> bool:
        """Volta da tela hospedada para os paineis. `False` se ja estava la.

        Devolve bool porque quem chama pelo `Esc` (`DBQMApp.action_go_back`)
        precisa saber se o `Esc` foi consumido aqui.

        A tela hospedada continua MONTADA, so escondida — como
        `FerramentasScreen` ja faz com as suas cinco. Desmontar seria
        arrancar o widget debaixo de um worker vivo: a instalacao de um
        Instant Client baixa 150+ MB em background e escreve progresso
        nesta arvore. Voltar nao pode ser cancelar.
        """
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "settings-main":
            return False
        switcher.current = "settings-main"
        self.call_after_refresh(self._focar_lista_de_ferramentas)
        return True

    def _focar_lista_de_ferramentas(self) -> None:
        try:
            self.query_one("#settings-ferramentas-list", OptionList).focus()
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "settings-ferramentas-list":
            return
        event.stop()
        chave = getattr(event.option, "nome", "")
        if chave in self._HOSPEDES:
            self._abrir_ferramenta(chave)

    # ------------------------------------------------------------------
    # Controles
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "settings-theme-select":
            return
        if event.value is None or event.value is Select.BLANK:
            return

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        new_theme = str(event.value)
        if new_theme == settings.theme:
            return
        settings.theme = new_theme
        save_settings(settings)
        try:
            self.app.theme = settings.theme
        except Exception:
            pass
        self.notify(f"Tema alterado: {settings.theme}")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        from dbqm.models.settings import load_settings, save_settings

        if event.switch.id == "settings-audit-switch":
            settings = load_settings()
            settings.audit_log_enabled = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Log de auditoria {status}!")
        elif event.switch.id == "settings-export-subdirs-switch":
            settings = load_settings()
            settings.create_export_subdirs = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Subdiretorios por tipo: {status}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-oracle-client-dir":
            self._open_oracle_client_dir_modal()
        elif event.button.id == "btn-export-dir":
            self._open_export_dir_modal()

    def _open_export_dir_modal(self) -> None:
        """Open the export dir setup modal in edit mode."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

        settings = load_settings()
        modal = ExportDirSetupModal(
            initial_use_cwd=not settings.default_export_dir,
            initial_path=settings.default_export_dir,
        )
        self.app.push_screen(modal, callback=self._on_export_dir_saved)

    def _on_export_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        from dbqm.models.settings import load_settings

        settings = load_settings()
        self._refresh_export_dir_label(settings.default_export_dir)
        self.notify("Diretorio de exportacao atualizado!")

    def _open_oracle_client_dir_modal(self) -> None:
        """Open the Instant Client directory modal seeded with the current setting."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

        modal = OracleClientDirModal(initial_path=load_settings().oracle_client_dir)
        self.app.push_screen(modal, callback=self._on_oracle_client_dir_saved)

    def _on_oracle_client_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        self._refresh_oracle_client_status()
        self.notify("Oracle Instant Client atualizado! Reabra o dbqm para aplicar.")
