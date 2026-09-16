# QA — the package editor (`PKG`)

TUI only: **Ferramentas → Editor de packages** (`dbqm/ui/screens/package_editor.py`).
The screen loads a package's spec and body from `ALL_SOURCE`, or offers a
blank/wizard template for a new one, and compiles what is in the editor
with `CREATE OR REPLACE`. After a compile, `ALL_ERRORS` is read and each
error is shown with its line and column. **Oracle only**: packages do not
exist elsewhere (`objects --type PACKAGE` on SQLite is QA-DISC-003).

Every row is `manual`. The core functions are unit-tested with mocks in
`tests/core/test_package_editor.py` (`TestCheckPackageExists`,
`TestFetchPackageSource`, `TestCompilePackage`, `TestFetchCompilationErrors`,
`TestGenerateBlankTemplate`, `TestGenerateWizardTemplate`) and the screen
renders in `tests/ui/test_screens.py::test_package_editor_screen_renders`;
what a real Oracle adds is the dictionary and the compiler.

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-PKG-001 | Dado uma conexao Oracle e o nome `QA_NOVO` (inexistente) / Quando o editor e aberto para ele / Entao a tela oferece o template em branco com `CREATE OR REPLACE PACKAGE QA_NOVO` no spec e `PACKAGE BODY QA_NOVO` no body · unit: `tests/core/test_package_editor.py::TestGenerateBlankTemplate::test_structure` | manual | oracle | — |
| QA-PKG-002 | Dado o body com um erro (`x := ;`) / Quando compilado / Entao a tela mostra o erro com a linha e a coluna vindas de `ALL_ERRORS` e o status do package fica INVALID · unit: `tests/core/test_package_editor.py::TestFetchCompilationErrors::test_returns_errors` | manual | oracle | — |
| QA-PKG-003 | Dado o erro corrigido / Quando compilado de novo / Entao nenhum erro e listado e `SELECT status FROM all_objects WHERE object_name = 'QA_NOVO'` e `VALID` para spec e body · unit: `tests/core/test_package_editor.py::TestCompilePackage::test_success` | manual | oracle | — |
| QA-PKG-004 | Dado um package existente / Quando o editor e aberto para ele / Entao spec e body vem de `ALL_SOURCE` exatamente como estao no banco · unit: `tests/core/test_package_editor.py::TestFetchPackageSource::test_fetches_spec_and_body` | manual | oracle | — |
| QA-PKG-005 | Dado uma conexao Oracle `read_only` / Quando compilar / Entao a compilacao e recusada pela guarda de somente leitura, antes de enviar · unit: `tests/core/test_read_only.py` (compile arm) | manual | oracle | — |

## Manual (Oracle) — the script

```
dbqm                          # TUI → Ferramentas → Editor de packages
# 1. conexao <ora>, nome QA_NOVO → "Template em branco"
#    spec starts with: CREATE OR REPLACE PACKAGE QA_NOVO AS
# 2. in the body, inside a procedure, type:  x := ;
#    Compilar → the error panel lists one entry with line/column, e.g.
#    "Linha 4, coluna 8: PLS-00103: Encountered the symbol ";" ..."
#    dbqm sql "SELECT object_type, status FROM all_objects WHERE object_name = 'QA_NOVO'" <ora>
#    → PACKAGE BODY INVALID
# 3. fix the line (x := 1;) → Compilar → no errors
#    same SELECT → PACKAGE VALID, PACKAGE BODY VALID
# 4. reopen QA_NOVO → spec/body text equals what step 3 compiled
# 5. same steps on a read_only connection → refused before the CREATE is sent
```
