"""In-memory records and validated configuration wire models."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class GeneratedFile:
    """A file to create during bootstrap."""

    path: Path
    content: str


@dataclass(frozen=True)
class TaskReferenceError(ValueError):
    """A missing or cyclic task reference."""

    task: str


class CommandOptions(BaseModel):
    """Validated command-line input."""

    command: Literal["bootstrap", "verify"]
    path: Path
    name: str = ""
    run: bool = False
    json_output: bool = False
    loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class Finding(BaseModel):
    """A serializable verification finding."""

    path: str
    rule: str
    message: str
    line: int | None = None


class ValidationDetail(BaseModel):
    """Safe fields from an external Pydantic validation error."""

    loc: tuple[str | int, ...]
    type: str


class Report(BaseModel):
    """A serializable verification result."""

    project: str
    findings: list[Finding] = Field(default_factory=list)


class Project(BaseModel):
    """Package metadata read from pyproject.toml."""

    requires_python: str = Field(alias="requires-python")
    dependencies: list[str] = Field(default_factory=list)


class BuildSystem(BaseModel):
    """PEP 517 build settings."""

    build_backend: str = Field(alias="build-backend")
    requires: list[str]


class Executor(BaseModel):
    """Explicit environment selection for task execution."""

    type: str
    location: str


class Poe(BaseModel):
    """Task names are dynamic; commands use Poe strings and reference sequences."""

    tasks: dict[str, str | list[str]]
    executor: Executor


class Pydocstyle(BaseModel):
    """Docstring convention settings."""

    convention: str


class Lint(BaseModel):
    """Ruff lint settings."""

    select: list[str]
    pydocstyle: Pydocstyle


class Ruff(BaseModel):
    """Ruff configuration."""

    target_version: str = Field(alias="target-version")
    lint: Lint


class Tool(BaseModel):
    """The tool settings checked by this verifier."""

    poe: Poe
    ruff: Ruff


class DependencyGroups(BaseModel):
    """Development dependencies."""

    dev: list[str]


class Pyproject(BaseModel):
    """Validated project configuration boundary."""

    project: Project
    build_system: BuildSystem = Field(alias="build-system")
    dependency_groups: DependencyGroups = Field(alias="dependency-groups")
    tool: Tool


class Hook(BaseModel):
    """A pre-commit hook definition."""

    id: str
    entry: str = ""
    language: str = ""
    pass_filenames: bool = True
    always_run: bool = False


class HookRepo(BaseModel):
    """A pre-commit hook repository."""

    repo: str
    hooks: list[Hook] = Field(default_factory=list)


class PreCommit(BaseModel):
    """Validated pre-commit configuration."""

    repos: list[HookRepo]
