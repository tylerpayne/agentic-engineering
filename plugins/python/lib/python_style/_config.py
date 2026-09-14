"""Check project tool configuration through validated wire models."""

import shlex
import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from pydantic import ValidationError

from python_style._report import add, configuration_error
from python_style.types import PreCommit, Pyproject, Report, TaskReferenceError


def _commands(
    tasks: dict[str, str | list[str]], name: str, seen: frozenset[str] = frozenset()
) -> list[str]:
    """Resolve task references without allowing cycles.

    Parameters
    ----------
    tasks : dict[str, str | list[str]]
        Dynamic task-name mapping.
    name : str
        Task to resolve.
    seen : frozenset[str]
        Ancestor tasks.

    Returns
    -------
    list[str]
        Leaf commands.

    Raises
    ------
    ValueError
        If a task is missing or cyclic.
    """
    if name in seen or name not in tasks:
        raise TaskReferenceError(name)
    value = tasks[name]
    if isinstance(value, str):
        return [value]
    return [
        command for child in value for command in _commands(tasks, child, seen | {name})
    ]


def check_config(root: Path, report: Report) -> None:
    """Check Python, build, tasks, lint settings, and pre-commit.

    Parameters
    ----------
    root : Path
        Project directory.
    report : Report
        Findings to append to.
    """
    path = root / "pyproject.toml"
    try:
        config = Pyproject.model_validate(tomllib.loads(path.read_text()))
        specifier = SpecifierSet(config.project.requires_python)
        if "3.12" not in specifier or any(
            f"3.{minor}" in specifier for minor in range(12)
        ):
            add(
                report,
                path,
                "python",
                "Require Python >=3.12; this profile prefers 3.12.",
            )
        if config.build_system.build_backend != "hatchling.build":
            add(report, path, "build", "Use the hatchling.build backend.")
        if not any(
            Requirement(dep).name == "hatchling" for dep in config.build_system.requires
        ):
            add(report, path, "build", "Declare hatchling in build-system.requires.")
        development = {Requirement(dep).name for dep in config.dependency_groups.dev}
        for name in ("poethepoet", "pre-commit", "pytest", "ruff", "ty"):
            if name not in development:
                add(
                    report,
                    path,
                    "dependencies",
                    f"Missing development dependency: {name}",
                )
        pydantic = [
            Requirement(dep)
            for dep in config.project.dependencies
            if Requirement(dep).name == "pydantic"
        ]
        if pydantic and any(
            "1.10" in dep.specifier or "3.0" in dep.specifier for dep in pydantic
        ):
            add(report, path, "records", "Constrain Pydantic to v2 (>=2,<3).")
        tasks = config.tool.poe.tasks
        if (
            config.tool.poe.executor.type != "virtualenv"
            or config.tool.poe.executor.location != ".venv"
        ):
            add(
                report,
                path,
                "executor",
                "Use Poe's virtualenv executor at .venv to avoid implicit syncing.",
            )
        required = (
            ("format", "ruff format ."),
            ("check", "ruff check ."),
            ("check", "ruff format --check ."),
            ("check", "ty check"),
            ("fix", "ruff check --fix ."),
            ("fix", "ruff format ."),
            ("test", "pytest"),
        )
        for task, command in required:
            if not any(
                shlex.split(cmd) == shlex.split(command)
                for cmd in _commands(tasks, task)
            ):
                add(
                    report,
                    path,
                    "tasks",
                    f"{task} must include {command!r} (scaffold profile).",
                )
        for command in _commands(tasks, "check"):
            tokens = shlex.split(command)
            if "--fix" in tokens or (
                tokens[:2] == ["ruff", "format"] and "--check" not in tokens
            ):
                add(report, path, "tasks", "check must not change files.")
        for name in tasks:
            if name not in {"format", "check", "fix", "test"} and ":" not in name:
                add(report, path, "tasks", f"Use parent:child for scoped tasks: {name}")
        lint = config.tool.ruff.lint
        if config.tool.ruff.target_version != "py312":
            add(report, path, "ruff", "Use the preferred py312 target.")
        if lint.pydocstyle.convention != "numpy" or not {"ANN", "D"}.issubset(
            lint.select
        ):
            add(report, path, "ruff", "Enable ANN and D rules with NumPy docstrings.")
    except (OSError, ValueError, ValidationError) as error:
        # python-style: allow[caught-error] Aggregate configuration failures into a nonzero verification report.
        add(report, path, "configuration", configuration_error(error))
    pin = root / ".python-version"
    if not pin.is_file() or pin.read_text().strip() != "3.12":
        add(report, pin, "python", "Pin the preferred interpreter to 3.12.")
    path = root / ".pre-commit-config.yaml"
    try:
        hooks = PreCommit.model_validate(yaml.safe_load(path.read_text()))
        if not any(
            repo.repo == "local"
            and hook.entry == ".venv/bin/python -m poethepoet check"
            and hook.language == "system"
            and not hook.pass_filenames
            and hook.always_run
            for repo in hooks.repos
            for hook in repo.hooks
        ):
            add(
                report,
                path,
                "pre-commit",
                "Use a local .venv/bin/python -m poethepoet check hook with pass_filenames=false and always_run=true.",
            )
    except (OSError, ValueError, yaml.YAMLError) as error:
        # python-style: allow[caught-error] Report invalid hook configuration without exposing parser input.
        add(report, path, "pre-commit", configuration_error(error))
