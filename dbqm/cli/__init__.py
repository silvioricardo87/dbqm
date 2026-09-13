"""Command-line interface for non-interactive execution of dbqm operations."""
from __future__ import annotations

import argparse

from dbqm.cli.commands import connection as _connection_commands
from dbqm.cli.commands import schema as _schema_commands
from dbqm.cli.commands.config_bundle import cmd_export_config, cmd_import_config
from dbqm.cli.commands.connection import cmd_connection
from dbqm.cli.commands.inspect import cmd_ddl, cmd_history, cmd_list, cmd_test
from dbqm.cli.commands.query import cmd_run, cmd_run_group, cmd_sql
from dbqm.cli.commands.schema import cmd_describe, cmd_objects
from dbqm.cli.params import _add_connection_fields, _parse_params, resolve_password
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
    p_run.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")

    # --- run-group ---
    p_grp = subparsers.add_parser("run-group", help="Executar comparacao de grupo")
    p_grp.add_argument("group", help="Nome do grupo")
    p_grp.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro compartilhado (pode repetir)")
    p_grp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")
    p_grp.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")
    p_grp.add_argument("--flat", action="store_true",
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
    p_sql.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")
    p_sql.add_argument("--commit", action="store_true",
                       help="Auto-commit para DML (INSERT/UPDATE/DELETE)")
    p_sql.add_argument("--explain", action="store_true",
                       help=(
                           "Mostra o plano de execucao da query (EXPLAIN PLAN + DBMS_XPLAN.DISPLAY no Oracle, "
                           "EXPLAIN nativo em PostgreSQL/MySQL). Passe apenas a query, sem EXPLAIN PLAN FOR."
                       ))

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

    return parser


COMMAND_MAP = {
    "run": cmd_run,
    "run-group": cmd_run_group,
    "sql": cmd_sql,
    "test": cmd_test,
    "list": cmd_list,
    "ddl": cmd_ddl,
    "export-config": cmd_export_config,
    "import-config": cmd_import_config,
    "history": cmd_history,
    "connection": cmd_connection,
    "objects": cmd_objects,
    "describe": cmd_describe,
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
