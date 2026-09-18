"""Portuguese — a translation of `en.py`.

Carries no accents, which is this project's long-standing rule for anything
a user reads on screen: the terminals dbqm runs in are not all trusted to
render them, and a label that renders as mojibake reads worse than one
without a tilde.

Every key here must exist in `en.py`, with the same placeholders. The guard
in `tests/design/test_i18n_policy.py` says so, because a translation that
drifts from the source is how a `{nome}` turns into a literal `{nome}` on
someone's screen.
"""
from __future__ import annotations

from typing import Final

TEXTOS: Final[dict[str, str]] = {
    # -- connection_builder ------------------------------------------------
    "connection.name_required": "Nome obrigatorio.",
    "connection.type_required": "Selecione o tipo de banco.",
    "connection.type_invalid": "Tipo de banco invalido: {tipo}. Use um de: {validos}.",
    "connection.oracle_mode_invalid": "Modo Oracle invalido: {modo}. Use um de: {validos}.",
    "connection.sqlite_database_required": "Informe o arquivo do banco SQLite (ou :memory:).",
    "connection.sqlite_field_unused": "SQLite nao usa {campo}; deixe em branco.",
    "connection.sqlite_password_unused": "SQLite nao usa senha; deixe em branco.",

    # -- config ------------------------------------------------------------
    "config.language_invalid": 'Idioma "{idioma}" nao existe. Idiomas validos: {validos}.',

    # -- read_only ---------------------------------------------------------
    "read_only.refused": (
        "Conexao '{nome}' e somente leitura. Use --force-write para enviar assim mesmo."
    ),
    "read_only.multiple_statements": (
        "Conexao '{nome}' e somente leitura e o comando tem mais de um "
        "statement, que nao podem ser verificados separadamente. Use "
        "--force-write para enviar assim mesmo."
    ),
    "read_only.explain_executes": (
        "Conexao '{nome}' e somente leitura e este EXPLAIN executa o comando "
        "que explica. Use --force-write para enviar assim mesmo."
    ),
    "query.sql_required": 'Informe o SQL.',
    "query.name_required": 'Informe o nome da consulta.',
    "query.connection_required": 'Selecione uma conexao.',
    "query.connection_not_found": 'Conexao "{nome}" nao encontrada.',
    "group.name_required": 'Informe o nome do grupo.',
    "group.two_queries_required": 'Selecione pelo menos 2 consultas.',
    "group.query_not_found": 'Consulta "{nome}" nao encontrada.',
    "group.query_repeated": 'Consulta "{nome}" repetida. Um grupo compara consultas distintas.',
    "group.join_key_required": 'Informe a coluna de juncao.',
    "template.name_required": 'Informe o nome do template.',
    "template.content_required": 'O conteudo do template nao pode estar vazio.',
    "crypto.password_unreadable": "Senha guardada nao pode ser lida: a chave em .dbqm_key nao corresponde a esta senha. Regrave-a com 'dbqm connection update <nome> --password-stdin'.",
    "bundle.too_large": 'Arquivo excede o tamanho maximo de {mb} MB.',
    "driver.not_installed": 'Driver para {banco} ({pacote}) nao esta instalado neste ambiente ({plataforma}). Instale manualmente com `pip install {pacote}` se houver wheel disponivel para sua plataforma; em Windows ARM, este driver nao tem wheel publicada e foi omitido por padrao.',
    "oracle_client.dir_missing": 'Diretorio nao existe: {caminho}',
    "oracle_client.not_a_dir": 'O caminho nao e um diretorio: {caminho}',
    "oracle_client.no_oci_dll": 'oci.dll nao encontrado em {caminho} nem em {pasta_bin}: o diretorio nao parece um Oracle Client.',
    "oracle_client.unusable": 'O Oracle Instant Client configurado no dbqm nao pode ser usado. {problema}\nAjuste o caminho em Config > Oracle Instant Client.',
    "connection.unknown_db_type": 'Tipo de banco desconhecido: {tipo}',
    "connection.test_ok": 'Conexao "{nome}" OK! ({segundos}s)\n  Versao: {versao}',
    "connection.connect_failed": 'Erro ao conectar: {erro}',
    "object.invalid_name": 'Nome de objeto invalido: {nome}',
    "engine.packages_oracle_only": 'Packages so existem no Oracle. Conexao e {tipo}.',
    "engine.sqlite_no_routines": 'SQLite nao tem rotinas armazenadas.',
    "engine.packages_and_routines_oracle_only": 'Packages e rotinas so existem no Oracle. Conexao e {tipo}.',
    "engine.routines_oracle_only": 'Rotinas armazenadas so existem no Oracle. Conexao e {tipo}.',
    "read_only.routine_refused": "Conexao '{nome}' e somente leitura e uma rotina pode escrever independente do texto do comando. Desmarque 'Somente leitura' na conexao para executar.",
    "read_only.package_compile_refused": "Conexao '{nome}' e somente leitura e a compilacao de pacote e sempre DDL. Desmarque 'Somente leitura' na conexao para compilar.",
    "sql.select_only": 'Apenas comandos SELECT sao permitidos.',
    "sql.unsupported_type": 'Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE, DELETE, DDL (CREATE/ALTER/DROP...) ou EXPLAIN PLAN.',
    "sql.explain_unsupported": '--explain ainda nao e suportado para {tipo}.',
    "sql.result_sets_returned": '{quantidade} conjuntos de resultado retornados; exibindo o ultimo.',
    "sql.result_set_shape": '{indice}: {linhas} linha(s), colunas: {colunas}',
    "group.no_comparable_columns": 'Consultas nao retornaram colunas comparaveis.',
    "group.duplicate_key_rows": "Chave '{chave}' tem valores repetidos em '{lado}': {linhas} linha(s) fora da comparacao.",
    "ddl.object_not_found": "Objeto '{nome}' nao encontrado.",
    "ddl.routine_not_in_body": "Rotina '{rotina}' nao encontrada no body de '{pacote}'.",
    "ddl.routine_not_found_or_denied": "Rotina '{nome}' nao encontrada ou sem permissao.",
    "ddl.extract_failed": 'Erro ao extrair: {erro}',
    "ddl.extract_failed_object": 'Erro ao extrair {nome}: {erro}',
    "ddl.type_unsupported": "Tipo '{tipo}' nao suportado para extracao.",
    "ddl.engine_unsupported": 'Extracao de DDL nao suportada para {tipo}.',
    "group.summary_column": 'Coluna: {coluna}',
    "group.summary_equal": '  Iguais:       {n}',
    "group.summary_normalized": '  Iguais (norm): {n}',
    "group.summary_different": '  Diferentes:   {n}',
    "group.summary_absent": '  Ausentes:     {n}',
    "sql.explain_takes_the_query_only": 'Passe apenas a query (sem EXPLAIN PLAN FOR) ao usar --explain.',
    "oracle_client.thin_mode_unsupported": 'Thin mode nao suportado por este servidor (DPY-3015). E preciso um Oracle Instant Client compativel para usar thick mode.\nConfigure o caminho em Config > Oracle Instant Client (a mesma tela permite baixar e instalar um client).\nDownload: {url}',
    "oracle_client.thin_mode_detail": '\n\n[!] O Oracle Instant Client nao foi carregado - o dbqm esta em thin mode.\n    Motivo: {motivo}\n    Configure o caminho em Config > Oracle Instant Client.',
}
