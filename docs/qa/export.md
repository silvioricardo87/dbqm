# QA — export (`EXPORT`)

`-e csv|json|txt|html` on `run`, `run-group`, `multi` and `sql`.

Every export writes one file under the export directory and reports its
path in `data.exported` (with `data.format`; `multi` adds `join_key`). The
rows in [adhoc-sql.md](adhoc-sql.md) (QA-SQL-011), [saved-queries.md](saved-queries.md)
(QA-QUERY-008), [groups.md](groups.md) (QA-GROUP-004/006) and
[multi.md](multi.md) (QA-MULTI-010) prove the file exists and the exit
code survives; the rows here open the file and check what is in it.
`run-group --flat` is one block per column and has no HTML form.

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-EXPORT-001 | Given `run ativos -e csv` / When the file is read / Then the first line is `id,name` and there is one line per row (`1,Ana`, `3,Caio`) | functional | all | tests/functional/test_export.py::test_run_csv_has_a_header_and_one_line_per_row |
| QA-EXPORT-002 | Given `run ativos -e json` / When the file is read as JSON / Then it carries the columns and the rows (`"columns"` with `id`, `name`; `Ana` and `Caio` among the values) | functional | all | tests/functional/test_export.py::test_run_json_carries_columns_and_rows |
| QA-EXPORT-003 | Given `run ativos -e txt` / When the file is read / Then it carries `id`, `name`, `Ana` and `Caio` | functional | all | tests/functional/test_export.py::test_run_txt_carries_the_rows |
| QA-EXPORT-004 | Given `run ativos -e html` / When the file is read / Then it contains `<table`, `<th>`/`<td>` with `name` and `Ana` | functional | all | tests/functional/test_export.py::test_run_html_is_a_table |
| QA-EXPORT-005 | Given `sql "SELECT id, name FROM customers" local -e csv|json|txt|html` / When each file is read / Then the csv starts with `id,name`, the json parses and carries `Ana`, the txt carries `Ana`, the html has `<table` | functional | all | tests/functional/test_export.py::test_sql_export_content_per_format |
| QA-EXPORT-006 | Given `run-group orders -e csv|json|txt|html` (divergent) / When each file is read / Then the csv and the txt carry `value`, the json parses and carries `value`, the html has `<table` — and the exit was 5 in every case | functional | all | tests/functional/test_export.py::test_run_group_export_content_per_format |
| QA-EXPORT-007 | Given `run-group orders --flat -e csv|json|txt` / When each file is read / Then the name starts with `flat_` and the content carries `value` | functional | all | tests/functional/test_export.py::test_run_group_flat_content_per_format |
| QA-EXPORT-008 | Given `multi ... -e csv|json|txt|html` / When each file is read / Then the content carries `value` (`<table` in the html) and `data.join_key == "id"` | functional | all | tests/functional/test_export.py::test_multi_export_content_per_format |
| QA-EXPORT-009 | Given any export under `tmp_config_dir` / When the path is inspected / Then it sits below the test's export folder, never below the cwd | functional | all | tests/functional/test_export.py::test_every_export_lands_under_the_export_dir |
| QA-EXPORT-010 | Given a saved group with a `shared_params` default and `run-group ... -e json` / When the exported file is read / Then the file name carries the default (`minimum-10`) and the JSON body's `params` carries it too | functional | all | tests/functional/test_export.py::test_run_group_export_carries_a_shared_params_default |
