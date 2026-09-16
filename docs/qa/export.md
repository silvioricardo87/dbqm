# QA — export (`EXPORT`)

`-e csv|json|txt|html` on `run`, `run-group`, `multi` and `sql`.

Every export writes one file under the export directory and reports its
path in `data.exported` (with `data.format`; `multi` adds `join_key`). The
rows in [adhoc-sql.md](adhoc-sql.md) (QA-SQL-011), [saved-queries.md](saved-queries.md)
(QA-QUERY-008), [groups.md](groups.md) (QA-GROUP-004/006) and
[multi.md](multi.md) (QA-MULTI-010) prove the file exists and the exit
code survives; the rows here open the file and check what is in it.
`run-group --flat` is one block per column and has no HTML form.

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-EXPORT-001 | Dado `run ativos -e csv` / Quando o arquivo e lido / Entao a primeira linha e `id,nome` e ha uma linha por registro (`1,Ana`, `3,Caio`) | functional | all | tests/functional/test_export.py::test_run_csv_has_a_header_and_one_line_per_row |
| QA-EXPORT-002 | Dado `run ativos -e json` / Quando o arquivo e lido como JSON / Entao contem as colunas e as linhas (`"columns"` com `id`,`nome`; `Ana` e `Caio` entre os valores) | functional | all | tests/functional/test_export.py::test_run_json_carries_columns_and_rows |
| QA-EXPORT-003 | Dado `run ativos -e txt` / Quando o arquivo e lido / Entao traz `id`, `nome`, `Ana` e `Caio` | functional | all | tests/functional/test_export.py::test_run_txt_carries_the_rows |
| QA-EXPORT-004 | Dado `run ativos -e html` / Quando o arquivo e lido / Entao contem `<table`, `<th>`/`<td>` com `nome` e `Ana` | functional | all | tests/functional/test_export.py::test_run_html_is_a_table |
| QA-EXPORT-005 | Dado `sql "SELECT id, nome FROM clientes" local -e csv|json|txt|html` / Quando cada arquivo e lido / Entao o csv comeca por `id,nome`, o json parseia e traz `Ana`, o txt traz `Ana`, o html tem `<table` | functional | all | tests/functional/test_export.py::test_sql_export_content_per_format |
| QA-EXPORT-006 | Dado `run-group pedidos -e csv|json|txt|html` (divergente) / Quando cada arquivo e lido / Entao o csv e o txt trazem `valor`, o json parseia e traz `valor`, o html tem `<table` — e o exit foi 5 em todos | functional | all | tests/functional/test_export.py::test_run_group_export_content_per_format |
| QA-EXPORT-007 | Dado `run-group pedidos --flat -e csv|json|txt` / Quando cada arquivo e lido / Entao o nome comeca por `flat_` e o conteudo traz `valor` | functional | all | tests/functional/test_export.py::test_run_group_flat_content_per_format |
| QA-EXPORT-008 | Dado `multi ... -e csv|json|txt|html` / Quando cada arquivo e lido / Entao o conteudo traz `valor` (`<table` no html) e `data.join_key == "id"` | functional | all | tests/functional/test_export.py::test_multi_export_content_per_format |
| QA-EXPORT-009 | Dado qualquer export sob `tmp_config_dir` / Quando o caminho e examinado / Entao esta abaixo da pasta de exports do teste, nunca do cwd | functional | all | tests/functional/test_export.py::test_every_export_lands_under_the_export_dir |
