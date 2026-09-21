# Configuration

Where dbqm keeps its files, where it writes the ones you ask it for, and
which language it speaks. All three are settings you can change; none needs
the TUI — `dbqm config get|set|list` reads and writes the same values.

[← Back to the README](../README.md)

---

## Data directory

DBQM stores all configuration, credentials, and exports under `~/.dbqm/` by default. Override with the `DBQM_HOME` environment variable:

```bash
export DBQM_HOME=/path/to/custom/dir
dbqm config list
```


## Export destination

Exports go to the current working directory by default. The first time you press `Export` in the UI, dbqm shows a setup modal so you can pick a fixed default directory or keep using the CWD. You can change it later in Settings → Export. Two options live there:

- **Export directory** — empty means "use CWD"; any custom path must already exist.
- **Subdirectories by kind** (ON by default) — controls whether group/DDL/SQL exports nest under `grupos/`, `ddl/`, etc. Query results (`consultas`) always go flat in the resolved directory.

Those folder names are **not** translated. They are directories on your disk:
renaming them per language would write the next export beside everything
already there, and leave the old files where nothing looks.

The CLI uses the same setting (no modal).


## Language

dbqm speaks English by default and ships a Portuguese translation. The
setting covers everything a user reads — the TUI, the CLI's messages, its
`--help`, and the headers of exported files and HTML reports.

```bash
dbqm config set language pt     # or: en
dbqm config get language
```

`DBQM_LANG` overrides the stored setting for one run, which is what you
want in a script or a CI job that parses output:

```bash
DBQM_LANG=en dbqm run vendas -f json
```

An unknown value falls back to English rather than failing: a typo in a
config file should not stop the program from starting.

Adding a language is a file: copy `dbqm/i18n/en.py` to `dbqm/i18n/xx.py`,
translate the values, and register it in `CATALOGOS`. A key with no
translation falls back to English at runtime, so a half-finished file still
runs — but `tests/design/test_i18n_policy.py` requires a language in
`CATALOGOS` to carry every key English defines, with the same placeholders.
Translate as you go; register when you are done.
