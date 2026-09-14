---
name: python
description: Apply Tyler's Python conventions when creating, editing, reviewing, or bootstrapping Python packages and uv workspaces. Includes a CLI for project setup and convention checks.
---

# Python

Apply these preferences to Python work. This file is the complete style guide;
using the companion CLI does not replace reading or applying these rules.

## Toolchain

### 1. uv manages workspaces and packages

Use **uv as the workspace and package manager**, including interpreter selection,
virtual environments, dependency management, and locking. Use `uv add` for runtime
dependencies, `uv add --dev` for development tools, `uv sync` to synchronize the
environment, and `uv run` to execute project commands. Commit `uv.lock`.

For multiple packages, declare `[tool.uv.workspace].members` at the workspace
root and share its lockfile. Manage workspace dependencies from that root. Do not
introduce Poetry, pipenv, or an independent environment-management workflow.

### 2. Hatch is the build system

Use **Hatch's Hatchling backend** for package builds. uv still manages the project
and invokes the build with `uv build`.

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"
```

### 3. poethepoet is the task system

Use **poethepoet** and define at least `format`, `check`, `fix`, and `test`.
Scoped tasks use **`parent:child`** names, such as `check:types` or `test:unit`.
`check` must not modify source files. A baseline task configuration is:

```toml
[tool.poe.tasks]
format = "ruff format ."
"check:lint" = "ruff check ."
"check:format" = "ruff format --check ."
"check:types" = "ty check"
check = ["check:lint", "check:format", "check:types"]
"fix:lint" = "ruff check --fix ."
fix = ["fix:lint", "format"]
test = "pytest"
```

Run tasks with `uv run poe <task>`. Add scoped tasks when needed while retaining
these four top-level task names.

### 4. Ruff formats and lints

Use **Ruff for both formatting and linting**. `format` runs the formatter;
`check` includes linting and formatting verification; `fix` applies lint fixes
and formatting. Enable annotation and docstring checks (`ANN` and `D`) and set
`[tool.ruff.lint.pydocstyle].convention = "numpy"`.

### 5. ty checks types

Use **ty for type checking**, and include `ty check` in `poe check`. Do not
substitute mypy or Pyright as the project's preferred type checker. Resolve type
errors by accurately modeling the data rather than adding `Any` to bypass them.

### 6. Python 3.12 is preferred

Require **Python >=3.12**, preferring **3.12** for development and execution.
Set `requires-python = ">=3.12"`, `.python-version` to `3.12`, and Ruff's target
version to `py312`. If a project specifically needs a newer interpreter, document
that requirement and align its runtime, metadata, and tool configuration.

### 7. pre-commit runs poe check

Configure a local **pre-commit hook running `uv run poe check`**. It must check
the project instead of appending the staged filenames to the Poe command:

```yaml
repos:
  - repo: local
    hooks:
      - id: check
        name: poe check
        entry: uv run poe check
        language: system
        pass_filenames: false
        always_run: true
```

Install the hook with `uv run pre-commit install` in a Git checkout.

### 8. pytest runs tests

Use **pytest** and expose it through `uv run poe test`. Test behavior, meaningful
failure paths, and serialization boundaries where relevant. Keep tests typed;
test functions and fixtures need argument and return annotations too.

## Records, types, and modules

### 9. Known-key records must not be dicts

**Never store or access records as dicts if their keys are knowable at compile
(or development) time.** Always use **dataclasses for in-memory records** and
**Pydantic v2 `BaseModel` subclasses for wire records** that need serialization
or deserialization. TypedDict and named tuples do not replace these conventions.

```python
# types.py
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class Job:
    """An in-memory job."""

    name: str
    attempts: int


class JobPayload(BaseModel):
    """A serialized job representation."""

    name: str
    attempts: int
```

Access `job.name`, not `job["name"]` or `job.get("name")`. Parse incoming wire data
with `JobPayload.model_validate_json(...)` or `model_validate(...)`, then work
with attributes. Serialize with `model_dump_json()` or `model_dump()` at the wire
boundary. Immediately convert a parser's raw dict output into its model; do not
keep passing that raw record through implementation code.

A genuinely dynamic mapping, such as arbitrary job names to `Job` instances,
may be `dict[str, Job]`. Its keys are data, not a fixed record schema. This is not
permission to encode known record fields as dictionary keys.

### 10. Split large files into smaller submodules

Prefer breaking files **longer than 300 lines** into focused submodules with
smaller files. Split along responsibilities rather than moving arbitrary line
ranges. Treat the threshold as a design signal; do not compress code to evade it.

### 11. Private files and record properties start with an underscore

Prefix **private module filenames** and **private record properties/attributes**
with `_`, for example `_parser.py` and `_cached_result`. For Pydantic models,
private state uses `PrivateAttr` and is not serialized. A field that belongs on
the wire must remain a public model field rather than being hidden as private
state. Annotate private attributes as well as public ones.

### 12. __init__.py contains re-exports only

**Never define implementations in `__init__.py`.** Put functions, classes,
initialization logic, and side effects in their own modules. An `__init__.py`
may contain re-export imports, an optional `__all__`, and a package docstring.
Do not configure logging or execute setup code there.

### 13. Annotate every property, argument, and return type

All **class properties/attributes**, **function and method arguments**, and
**function and method return types** must have type annotations. This includes
private helpers, properties, constructors (`__init__ -> None`), tests, and
fixtures. The implicit `self` and `cls` receiver needs no redundant annotation.
Avoid untyped records and `Any` used to dodge modeling a known shape.

### 14. Use NumPy-style method docstrings

Use **NumPy-style function and method docstrings**: a concise summary, followed
by `Parameters`, `Returns`, `Raises`, or `Yields` sections as applicable. Do not
add empty sections. For example:

```python
def retry_delay(attempt: int) -> float:
    """Calculate the delay before another attempt.

    Parameters
    ----------
    attempt : int
        Zero-based attempt number.

    Returns
    -------
    float
        Delay in seconds.

    Raises
    ------
    ValueError
        If the attempt number is negative.
    """
    if attempt < 0:
        raise ValueError(f"attempt must be nonnegative; received {attempt}")
    return min(2.0 ** min(attempt, 6), 60.0)
```

### 15. Separate type definitions from implementations

Put dataclasses, wire models, and other type definitions in **separate modules
from implementation code**, for example `types.py`, `_types.py`, or a dedicated
`types/` package. Import those types into modules that perform work. Model
validation may stay with the model; business logic belongs in implementation
modules. Avoid mixing record definitions into service or CLI modules.

## Code smells, logging, and failures

### 16. getattr/setattr require external ownership and an explanation

`getattr` and `setattr` are **code smells, not blanket prohibitions**. Use them
only when we genuinely **do not own the object** and need safe dynamic attribute
access. Use direct, typed attributes for objects we own. Add a **code comment**
explaining whose object it is, why direct access is unsuitable, and what any
fallback means. Do not use dynamic access to avoid defining or fixing our types.

### 17. Consuming exceptions must be deliberate and explained

A **try/except that does not reraise is a code smell**, not an absolute ban.
Use it deliberately and include a **code comment explaining why the exception is
consumed**. Recovery, aggregating validation failures, or translating a failure
into a nonzero CLI exit status can be appropriate. Make the failure visible or
explain why it is an expected condition. Do not silently `pass` or substitute a
success-shaped default for a failed operation. When translating an exception,
preserve its cause with `raise ... from error`.

### 18. Logging is mandatory and every CLI controls verbosity

Always set up Python's standard-library **`logging`** at application entry
points. Use `logging.getLogger(__name__)` for module loggers. Libraries must not
reconfigure their caller's root logger on import.

**Every available CLI must support `--loglevel DEBUG|INFO|WARNING|ERROR`**,
defaulting to `INFO`. Prefer this explicit severity selector over verbose/quiet
flags. Use DEBUG for diagnostic detail, INFO for ordinary progress, WARNING for
warnings and errors, and ERROR for errors only. Reject unsupported levels with
an informative error. Send diagnostics to stderr. The bootstrap's
`_logging.py` helper supplies this setup; call it from the application's entry
point and connect its arguments to the CLI flags.

### 19. print is for intentional stdout output

`print` is a **code smell, not a blanket prohibition**. Use it when stdout is the
intended destination for the output, such as a JSON protocol, generated content,
or data that another process consumes. Otherwise **use logging**, including for
progress, success messages, debugging, and errors. Never mix diagnostic text
into machine-readable stdout.

### 20. Forgiving dict lookups must be intentional

Dict `.get()`, **`.get(..., None)`**, **`.setdefault()`**, and other forgiving
getters are **code smells, not blanket prohibitions**. Use them only when missing
data is expected and the default has a deliberate meaning. Required data should
fail loudly when missing. Do not use fallback getters to conceal an unknown
schema or missing required values. The known-key record prohibition still
applies: use dataclass or model attributes instead of dict getters for records.

### 21. Fail loudly with safe, specific context

Always prefer **informative failures over silent recovery**. Error messages
should identify the operation, the expected condition, and the **particular
values that caused the error**, privacy permitting. For example, report
`attempt must be nonnegative; received -2`, not just `invalid argument`.

Do not print or log passwords, tokens, raw secret-bearing records, or exception
representations that contain those values. Parser and Pydantic validation errors
can embed their input: omit or redact sensitive values while retaining safe
field names, file locations, error categories, and other useful context. CLI
failures must return a nonzero exit status.

## Using the verifier's rationale comments

The verifier flags recognizable smells for review; it cannot prove ownership,
intent, full exception control flow, or privacy. For a justified exception,
place a comment directly before or on the flagged statement, or immediately
inside its except handler:

```python
# python-style: allow[print] Emit the JSON protocol consumed by the calling process.
print(report.model_dump_json())
```

Supported tags are `dynamic-attrs`, `caught-error`, `print`, and `forgiving-get`.
Each requires an actual explanation. The tag does not make otherwise unjustified
code acceptable. Apply the rules above even if the verifier does not flag a use.

## Bootstrap and verify

The companion executable is `../../bin/python-style` relative to this skill
folder. Resolve it to an absolute path before changing directories. It requires
uv; uv installs its Python 3.12 environment and locked dependencies on first use.
Keep `bin/`, `lib/`, `pyproject.toml`, `.python-version`, and `uv.lock` together
when downloading. A Claude marketplace client is not required.

```sh
/path/to/python/bin/python-style bootstrap ./my-project --name my-project
cd my-project
uv sync
uv run poe check
uv run poe test
uv run pre-commit install
/path/to/python/bin/python-style verify .
/path/to/python/bin/python-style verify . --run --json --loglevel DEBUG
```

Bootstrap creates a single-package uv project with a src layout. It refuses
collisions and leaves unrelated files alone. For a multi-package workspace,
bootstrap each new member, declare it in the root `[tool.uv.workspace].members`,
and manage dependencies and locking from the root. Migrate existing project
configuration intentionally rather than replacing it wholesale.

`verify` checks configuration and AST conventions without executing project code
and returns nonzero for findings. `--run` additionally runs the target project's
`uv run poe check` and `uv run poe test`; use it when running that project's code
is within the task's scope. `--json` emits a structured stdout report.
`--loglevel DEBUG|INFO|WARNING|ERROR` controls logging to stderr (default INFO).

The verifier accepts the scaffold's task shape and reports unsupported task
shapes rather than claiming they passed. Run it per package for workspaces.
Passing checks is partial evidence, not complete compliance: manually review all
21 rules, especially record semantics, module responsibility, private names,
dynamic attribute ownership, deliberate recovery, logging coverage, and privacy.
