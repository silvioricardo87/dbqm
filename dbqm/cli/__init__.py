"""Command-line interface for non-interactive execution of dbqm operations."""
from __future__ import annotations

import argparse

from dbqm.cli.commands import config_cmd as _config_commands
from dbqm.cli.commands import connection as _connection_commands
from dbqm.cli.commands import saved as _saved_commands
from dbqm.cli.commands import schema as _schema_commands
from dbqm.cli.commands.config_bundle import cmd_export_config, cmd_import_config
from dbqm.cli.commands.config_cmd import cmd_config
from dbqm.cli.commands.connection import cmd_connection
from dbqm.cli.commands.inspect import cmd_ddl, cmd_history, cmd_list, cmd_test
from dbqm.cli.commands.query import cmd_call, cmd_multi, cmd_run, cmd_run_group, cmd_sql
from dbqm.cli.commands.saved import cmd_group, cmd_query
from dbqm.cli.commands.schema import cmd_describe, cmd_objects, cmd_rows
from dbqm.cli.params import (
    _add_connection_fields,
    _add_group_fields,
    _add_query_fields,
    _parse_params,
    resolve_password,
)
from dbqm.cli.render import _print_query_result, console, rich_theme

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbqm",
        description="DB Query Manager — ferramenta CLI para consultas em banco de dados",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- run ---
    p_run = subparsers.add_parser("run", help="Executar uma consulta salva")
    p_run.add_argument("query", help="Nome da consulta")
    p_run.add_argument("-c", "--connection", help="Conexao (sobrescreve a padrao da consulta)")
    p_run.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro (pode repetir)")
    p_run.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help="Formato de saida (padrao: table). 'raw' imprime valores sem decoracao.")
    p_run.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help="Exportar resultado para arquivo")

    # --- run-group ---
    p_grp = subparsers.add_parser("run-group", help="Executar comparacao de grupo")
    p_grp.add_argument("group", help="Nome do grupo")
    p_grp.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro compartilhado (pode repetir)")
    p_grp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")
    p_grp.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help="Exportar resultado para arquivo. 'html' nao pode ser usado com --flat.")
    p_grp.add_argument("--flat", action="store_true",
                       help="Usar formato flat (um bloco por coluna)")

    # --- multi ---
    p_multi = subparsers.add_parser(
        "multi", help="Executar um SQL ad-hoc em varias conexoes e comparar")
    p_multi.add_argument("sql", help="SQL a executar (ou caminho para arquivo .sql)")
    p_multi.add_argument("-c", "--connection", action="append", metavar="NOME",
                         help="Conexao (repita para cada uma; minimo 2)")
    p_multi.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                         help="Parametro (pode repetir)")
    p_multi.add_argument("--key", help="Coluna de juncao (padrao: a primeira coluna comum)")
    p_multi.add_argument("-f", "--format", choices=["table", "json"], default="table",
                         help="Formato de saida")
    p_multi.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                         help="Exportar resultado para arquivo. 'html' nao pode ser usado com --flat.")
    p_multi.add_argument("--flat", action="store_true",
                         help="Usar formato flat (um bloco por coluna)")

    # --- sql ---
    p_sql = subparsers.add_parser(
        "sql",
        help="Executar SQL ad-hoc (SELECT, CTE, DML, DDL, PL/SQL ou EXPLAIN PLAN)",
    )
    p_sql.add_argument(
        "sql",
        help=(
            "SQL a executar (ou caminho para arquivo .sql). "
            "Aceita SELECT (incluindo CTE WITH ... SELECT), INSERT/UPDATE/DELETE "
            "(com --commit), DDL (CREATE/ALTER/DROP/...), blocos PL/SQL anonimos "
            "(DECLARE/BEGIN/END;) com captura de DBMS_OUTPUT, os atalhos "
            "EXEC/EXECUTE/CALL <proc>, e EXPLAIN PLAN. Use --explain para "
            "obter o plano automaticamente."
        ),
    )
    p_sql.add_argument("connection", help="Nome da conexao")
    p_sql.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro (pode repetir)")
    p_sql.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help="Formato de saida. 'raw' imprime valores sem decoracao.")
    p_sql.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help="Exportar resultado para arquivo")
    p_sql.add_argument("--commit", action="store_true",
                       help="Auto-commit para DML (INSERT/UPDATE/DELETE)")
    p_sql.add_argument("--force-write", dest="force_write", action="store_true",
                       help="Enviar mesmo numa conexao somente leitura")
    p_sql.add_argument("--explain", action="store_true",
                       help=(
                           "Mostra o plano de execucao da query (EXPLAIN PLAN + DBMS_XPLAN.DISPLAY no Oracle, "
                           "EXPLAIN nativo em PostgreSQL/MySQL). Passe apenas a query, sem EXPLAIN PLAN FOR."
                       ))

    # --- call ---
    p_call = subparsers.add_parser(
        "call", help="Executar uma procedure ou function (somente Oracle)")
    p_call.add_argument("routine", help="Nome da rotina: PACOTE.ROTINA ou ROTINA avulsa")
    p_call.add_argument("connection", help="Nome da conexao")
    p_call.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                        help="Parametro de entrada (pode repetir)")
    p_call.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")
    p_call.add_argument("--commit", action="store_true",
                        help="Confirmar a transacao. Sem isso, a rotina roda e e desfeita.")

    # --- test ---
    p_test = subparsers.add_parser("test", help="Testar conexao com banco de dados")
    p_test.add_argument("connection", nargs="?", default="__all__",
                        help="Nome da conexao (ou omita para testar todas)")
    p_test.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")

    # --- list ---
    p_list = subparsers.add_parser("list", help="Listar conexoes, consultas ou grupos")
    p_list.add_argument("resource", choices=["connections", "queries", "groups"],
                        help="O que listar")
    p_list.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")

    # --- ddl ---
    p_ddl = subparsers.add_parser("ddl", help="Extrair DDL de objeto do banco")
    p_ddl.add_argument("object", help="Nome do objeto")
    p_ddl.add_argument("connection", help="Nome da conexao")
    p_ddl.add_argument("--stdout", action="store_true",
                       help="Imprimir DDL no stdout em vez de salvar em arquivo")
    p_ddl.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")

    # --- objects ---
    p_objects = subparsers.add_parser("objects", help="Listar objetos do banco")
    p_objects.add_argument("connection", help="Nome da conexao")
    p_objects.add_argument("--type", choices=_schema_commands.OBJECT_TYPES,
                           default="TABLE", help="Tipo de objeto")
    p_objects.add_argument("-f", "--format", choices=["table", "json"],
                           default="table", help="Formato de saida")

    # --- describe ---
    p_describe = subparsers.add_parser("describe", help="Ver a estrutura de um objeto")
    p_describe.add_argument("object", help="Nome do objeto")
    p_describe.add_argument("connection", help="Nome da conexao")
    p_describe.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help="Formato de saida")

    # --- rows ---
    p_rows = subparsers.add_parser("rows", help="Listar linhas de uma tabela")
    p_rows.add_argument("table", help="Nome da tabela")
    p_rows.add_argument("connection", help="Nome da conexao")
    p_rows.add_argument("--limit", type=int, default=100,
                        help="Quantas linhas trazer (padrao: 100)")
    p_rows.add_argument("--offset", type=int, default=0,
                        help="A partir de qual linha (padrao: 0)")
    p_rows.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"],
                        default="table", help="Formato de saida")

    # --- export-config ---
    p_exp = subparsers.add_parser("export-config", help="Exportar configuracoes para bundle .dbqm")
    p_exp.add_argument("--password",
                       help="Senha (desaconselhado: fica no historico do shell "
                            "e na tabela de processos; prefira --password-stdin)")
    p_exp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")
    p_exp.add_argument("--no-connections", action="store_true", help="Excluir conexoes")
    p_exp.add_argument("--no-queries", action="store_true", help="Excluir consultas")
    p_exp.add_argument("--no-groups", action="store_true", help="Excluir grupos")
    p_exp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")

    # --- import-config ---
    p_imp = subparsers.add_parser("import-config", help="Importar configuracoes de bundle .dbqm")
    p_imp.add_argument("file", help="Caminho do arquivo .dbqm")
    p_imp.add_argument("--password",
                       help="Senha (desaconselhado: fica no historico do shell "
                            "e na tabela de processos; prefira --password-stdin)")
    p_imp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")
    p_imp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")

    # --- history ---
    p_hist = subparsers.add_parser("history", help="Ver historico de execucoes")
    p_hist.add_argument("-n", "--limit", type=int, help="Numero de entradas (padrao: 20)")
    p_hist.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")
    p_hist.add_argument("--clear", action="store_true", help="Limpar historico")

    # --- config ---
    p_config = subparsers.add_parser(
        "config",
        help="Ver e alterar as configuracoes do programa (get, set, list)",
    )
    # `cmd_config` (in `dbqm.cli.commands.config_cmd`) reads this back to
    # print the group's own help on a bare `dbqm config`.
    _config_commands._config_parser = p_config
    config_sub = p_config.add_subparsers(dest="subcommand")

    p_config_list = config_sub.add_parser("list", help="Listar todas as configuracoes")
    p_config_list.add_argument("-f", "--format", choices=["table", "json"],
                               default="table", help="Formato de saida")

    p_config_get = config_sub.add_parser("get", help="Ver uma configuracao")
    p_config_get.add_argument("key", help="Nome da configuracao")
    p_config_get.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    p_config_set = config_sub.add_parser("set", help="Alterar uma configuracao")
    p_config_set.add_argument("key", help="Nome da configuracao")
    p_config_set.add_argument("value", help="Novo valor")
    p_config_set.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    # --- connection ---
    p_conn = subparsers.add_parser(
        "connection",
        help="Gerenciar conexoes (criar, alterar, remover, ver, listar)",
    )
    # `cmd_connection` (in `dbqm.cli.commands.connection`) reads this back to
    # print the group's own help on a bare `dbqm connection`.
    _connection_commands._connection_parser = p_conn
    conn_sub = p_conn.add_subparsers(dest="subcommand")

    p_conn_add = conn_sub.add_parser("add", help="Criar uma conexao")
    p_conn_add.add_argument("name", help="Nome da conexao")
    _add_connection_fields(p_conn_add)

    p_conn_update = conn_sub.add_parser("update", help="Alterar uma conexao existente")
    p_conn_update.add_argument("name", help="Nome da conexao")
    _add_connection_fields(p_conn_update)

    p_conn_show = conn_sub.add_parser("show", help="Ver uma conexao (senha omitida)")
    p_conn_show.add_argument("name", help="Nome da conexao")
    p_conn_show.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help="Formato de saida")

    p_conn_rm = conn_sub.add_parser("rm", help="Remover uma conexao")
    p_conn_rm.add_argument("name", help="Nome da conexao")
    p_conn_rm.add_argument("--yes", action="store_true",
                           help="Remover sem confirmacao (obrigatorio fora do terminal)")
    p_conn_rm.add_argument("-f", "--format", choices=["table", "json"],
                           default="table", help="Formato de saida")

    p_conn_list = conn_sub.add_parser("list", help="Listar conexoes")
    p_conn_list.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help="Formato de saida")

    # --- query ---
    p_query = subparsers.add_parser(
        "query",
        help="Gerenciar consultas salvas (criar, alterar, remover, ver, listar)",
    )
    # `cmd_query` (in `dbqm.cli.commands.saved`) reads this back to print the
    # group's own help on a bare `dbqm query`.
    _saved_commands._query_parser = p_query
    query_sub = p_query.add_subparsers(dest="subcommand")

    p_query_add = query_sub.add_parser("add", help="Criar uma consulta")
    p_query_add.add_argument("name", help="Nome da consulta")
    _add_query_fields(p_query_add)

    p_query_update = query_sub.add_parser("update", help="Alterar uma consulta existente")
    p_query_update.add_argument("name", help="Nome da consulta")
    _add_query_fields(p_query_update)

    p_query_show = query_sub.add_parser("show", help="Ver uma consulta")
    p_query_show.add_argument("name", help="Nome da consulta")
    p_query_show.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    p_query_rm = query_sub.add_parser("rm", help="Remover uma consulta")
    p_query_rm.add_argument("name", help="Nome da consulta")
    p_query_rm.add_argument("--yes", action="store_true",
                            help="Remover sem confirmacao (obrigatorio fora do terminal)")
    p_query_rm.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help="Formato de saida")

    p_query_list = query_sub.add_parser("list", help="Listar consultas")
    p_query_list.add_argument("--connection", help="Filtrar por conexao")
    p_query_list.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    # --- group ---
    p_group = subparsers.add_parser(
        "group",
        help="Gerenciar grupos de comparacao (criar, alterar, remover, ver, listar)",
    )
    # `cmd_group` (in `dbqm.cli.commands.saved`) reads this back to print the
    # group's own help on a bare `dbqm group`.
    _saved_commands._group_parser = p_group
    group_sub = p_group.add_subparsers(dest="subcommand")

    p_group_add = group_sub.add_parser("add", help="Criar um grupo")
    p_group_add.add_argument("name", help="Nome do grupo")
    _add_group_fields(p_group_add)

    p_group_update = group_sub.add_parser("update", help="Alterar um grupo existente")
    p_group_update.add_argument("name", help="Nome do grupo")
    _add_group_fields(p_group_update)

    p_group_show = group_sub.add_parser("show", help="Ver um grupo")
    p_group_show.add_argument("name", help="Nome do grupo")
    p_group_show.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    p_group_rm = group_sub.add_parser("rm", help="Remover um grupo")
    p_group_rm.add_argument("name", help="Nome do grupo")
    p_group_rm.add_argument("--yes", action="store_true",
                            help="Remover sem confirmacao (obrigatorio fora do terminal)")
    p_group_rm.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help="Formato de saida")

    p_group_list = group_sub.add_parser("list", help="Listar grupos")
    p_group_list.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help="Formato de saida")

    return parser


COMMAND_MAP = {
    "run": cmd_run,
    "run-group": cmd_run_group,
    "multi": cmd_multi,
    "sql": cmd_sql,
    "call": cmd_call,
    "test": cmd_test,
    "list": cmd_list,
    "ddl": cmd_ddl,
    "export-config": cmd_export_config,
    "import-config": cmd_import_config,
    "history": cmd_history,
    "config": cmd_config,
    "connection": cmd_connection,
    "query": cmd_query,
    "group": cmd_group,
    "objects": cmd_objects,
    "describe": cmd_describe,
    "rows": cmd_rows,
}


def run_cli(argv: list[str] | None = None) -> bool:
    """Parse CLI args and execute command. Returns True if a command was handled."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        return False

    handler = COMMAND_MAP.get(args.command)
    if handler:
        handler(args)
        return True

    return False
