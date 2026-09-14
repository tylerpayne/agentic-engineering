"""Create projects without replacing existing files."""

import keyword
import re
from pathlib import Path

from python_style.types import GeneratedFile


def bootstrap(destination: Path, name: str) -> list[Path]:
    """Create a package scaffold, refusing collisions before writing.

    Parameters
    ----------
    destination : Path
        Target project directory.
    name : str
        Distribution name; hyphens become underscores in the import name.

    Returns
    -------
    list[Path]
        Created file paths.

    Raises
    ------
    ValueError
        If the name is invalid or a generated path already exists.
    """
    module = name.replace("-", "_")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or keyword.iskeyword(module):
        raise ValueError(
            "Use a lowercase Python package name, optionally with hyphens."
        )
    templates = Path(__file__).parent / "templates"
    config = (templates / "pyproject.toml.txt").read_text()
    files = [
        GeneratedFile(
            Path("pyproject.toml"),
            config.replace("@NAME@", name).replace("@MODULE@", module),
        ),
        GeneratedFile(
            Path(".pre-commit-config.yaml"),
            (templates / "pre-commit.yaml.txt").read_text(),
        ),
        GeneratedFile(Path(".python-version"), "3.12\n"),
        GeneratedFile(
            Path(".gitignore"),
            ".venv/\n__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\ndist/\n",
        ),
        GeneratedFile(Path(f"src/{module}/__init__.py"), f'"""{name} package."""\n'),
        GeneratedFile(
            Path(f"src/{module}/types.py"),
            '"""Package record and type definitions."""\n',
        ),
        GeneratedFile(
            Path("tests/test_package.py"),
            f'"""Package import smoke test."""\n\nimport {module}\n\n\n'
            f'def test_import() -> None:\n    """The package is importable."""\n'
            f'    assert {module}.__name__ == "{module}"\n',
        ),
    ]
    for file in files:
        target = destination / file.path
        if target.exists() or target.is_symlink():
            raise ValueError(f"Refusing to overwrite {target}")
        for parent in target.parents:
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f"Unsafe destination parent: {parent}")
    for file in files:
        target = destination / file.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as stream:
            stream.write(file.content)
    return [destination / file.path for file in files]
