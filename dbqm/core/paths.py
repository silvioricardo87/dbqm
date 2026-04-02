"""Centralized path resolution for DBQM data directories."""
import os
from pathlib import Path

def _get_dbqm_home() -> Path:
    """Get the DBQM home directory."""
    env = os.environ.get("DBQM_HOME")
    if env:
        return Path(env)
    return Path.home() / ".dbqm"

DBQM_HOME = _get_dbqm_home()
CONFIG_DIR = DBQM_HOME / "config"
EXPORTS_DIR = DBQM_HOME / "exports"
KEY_FILE = DBQM_HOME / ".dbqm_key"
CLIENTS_DIR = DBQM_HOME / "clients"
TNS_DIR = DBQM_HOME / "tns"
HISTORY_DIR = CONFIG_DIR / "history"
AUDIT_FILE = CONFIG_DIR / "audit.log"
CONNECTIONS_FILE = CONFIG_DIR / "connections.json"
QUERIES_FILE = CONFIG_DIR / "queries.json"
GROUPS_FILE = CONFIG_DIR / "groups.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
TEMPLATES_DIR = DBQM_HOME / "templates"
TEMPLATES_FILE = TEMPLATES_DIR / "templates.json"

def ensure_dirs():
    """Create data directories if they don't exist."""
    for d in [CONFIG_DIR, EXPORTS_DIR, HISTORY_DIR, TEMPLATES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
