# Configuration

Where dbqm keeps its files, and where it writes the ones you ask it for.
Both are settings you can change; neither needs the TUI —
`dbqm config get|set|list` reads and writes the same values.

[← Back to the README](../README.md)

---

## Data directory

DBQM stores all configuration, credentials, and exports under `~/.dbqm/` by default. Override with the `DBQM_HOME` environment variable:

```bash
export DBQM_HOME=/path/to/custom/dir
dbqm
```


## Export destination

Exports go to the current working directory by default. The first time you press `Exportar` in the UI, dbqm shows a setup modal so you can pick a fixed default directory or keep using the CWD. You can change it later in Settings → Exportacao. Two options live there:

- **Diretorio de exportacao** — empty means "use CWD"; any custom path must already exist.
- **Criar subdiretorios por tipo** (ON by default) — controls whether group/DDL/SQL exports nest under `grupos/`, `ddl/`, etc. Query results (`consultas`) always go flat in the resolved directory.

The CLI uses the same setting (no modal).
