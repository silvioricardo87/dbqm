"""Published requirements must preserve the versions validated before shipping."""
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from packaging.requirements import Requirement


def test_direct_dependencies_are_exactly_pinned():
    config = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text())
    requirements = list(config["build-system"]["requires"])
    requirements.extend(config["project"]["dependencies"])
    for group in config["project"]["optional-dependencies"].values():
        requirements.extend(group)
    for text in requirements:
        requirement = Requirement(text)
        specifiers = list(requirement.specifier)
        assert len(specifiers) == 1, text
        assert specifiers[0].operator == "==", text
        assert "*" not in specifiers[0].version, text
