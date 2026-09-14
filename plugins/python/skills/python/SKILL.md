---
name: python
description: Apply Tyler's Python conventions when creating, editing, reviewing, or bootstrapping Python packages and uv workspaces. Includes a CLI for project setup and convention checks.
---

# Python

## Toolchain

- Use uv for Python environments, dependencies, lockfiles, packages, and workspaces.
  Use `uv add`, `uv sync`, and `uv run`; commit `uv.lock`. Use uv workspace members
  when multiple packages belong to one workspace, with a shared root lockfile.
- Require Python >=3.12. Prefer Python 3.12 and pin `.python-version` to `3.12`
  unless the project requires a newer version.
- Use Hatchling (`hatchling.build`, the Hatch build backend) for builds, driven by
  `uv build`. Do not introduce a second environment or package manager.
- Use poethepoet for tasks. Define at least `format`, `check`, `fix`, and `test`.
  Name scoped tasks `parent:child`, for example `check:types`, `check:lint`,
  `check:format`, and `fix:lint`.
- Use Ruff for formatting and linting, ty for type checking, and pytest for tests.
  `check` is non-mutating and includes Ruff lint, Ruff format checking, and ty.
  `fix` runs Ruff fixes and formatting; `test` runs pytest.
- Configure pre-commit with a local hook running `uv run poe check`, with
  `pass_filenames: false` and `always_run: true`. Install with
  `uv run pre-commit install` when setting up a Git checkout.

## Records and typing

Never store or access a record as a dict when its keys are knowable at development
time. Use an annotated dataclass for in-memory records and a Pydantic v2
`BaseModel` for wire records that need serialization or deserialization. Use
`model_validate`, `model_validate_json`, `model_dump`, and `model_dump_json` at
boundaries. Convert raw parser output immediately to models; do not retain or
index raw dict records. A genuinely dynamic mapping, such as names to task
commands, may remain a typed mapping. TypedDict and named tuples are not substitutes
for these record conventions.

Annotate all class attributes, function arguments, and return types, including
private functions and `__init__ -> None`. The implicit `self` and `cls` receiver
need no redundant annotation. Avoid `Any` as a shortcut around modeling records.
Use underscore prefixes for private record attributes; Pydantic private state
uses `PrivateAttr` and is not a wire field. Keep wire fields public if they must
serialize.

## Errors, logging, and deliberate exceptions

- Treat `getattr` and `setattr` as code smells. Use direct, typed attribute access
  for objects we own. Dynamic access is permitted only for an object we do not
  own when safe attribute access is necessary. Add a code comment explaining
  ownership, why direct access is unsuitable, and the intended fallback.
- Treat catching an exception without reraising as a code smell. Recovery,
  aggregating validation failures, and mapping errors to CLI exit statuses can
  be deliberate choices; add a code comment explaining why the exception is
  consumed and how the failure remains visible. Avoid bare `except`, silent
  `pass`, and success-shaped fallback values that hide failure. When translating
  exceptions, preserve the cause with `raise ... from error`.
- Logging is mandatory. Use the standard library `logging` module. Configure it
  at application entry points, and use `logging.getLogger(__name__)` in modules.
  Libraries must not reconfigure their caller's root logger on import. Every CLI
  must expose verbosity controls (for example `-v/--verbose` and `-q/--quiet`).
  Send diagnostics to stderr and preserve errors when quiet mode is selected.
- Treat `print` as a code smell. It is appropriate when stdout is the intended
  output contract, such as JSON, generated content, or data for another process.
  Use logging for progress, status, debugging, and errors. Keep machine-readable
  stdout free of diagnostics.
- Treat dict `.get()`, `.get(..., None)`, `.setdefault()`, and other forgiving
  lookups as code smells. Use them only when missing data is expected and the
  fallback has deliberate meaning. Required fields should fail when missing.
  This does not relax the dataclass/BaseModel record rule.
- Prefer loud failures with informative messages: identify the operation, the
  expected condition, and the particular offending values when safe. Never dump
  passwords, tokens, raw secret-bearing records, or parser/validation errors that
  embed them. Redact or omit sensitive values while retaining safe field names,
  locations, and error categories.

The verifier flags recognizable examples as review findings, not unconditional
bans. For justified exceptions, place a comment directly before or on the flagged
statement (or immediately inside an except handler):

```python
# python-style: allow[print] Emit the JSON protocol consumed by the calling process.
print(report.model_dump_json())
```

Supported rationale tags are `dynamic-attrs`, `caught-error`, `print`, and
`forgiving-get`. A tag needs an actual explanation. It is a review aid, not proof
that a use is justified. Attribute ownership, lookup receiver types, exception
control flow, logging coverage, and privacy still require semantic review.

## Modules and documentation

Prefer splitting files longer than 300 lines into focused submodules. Private
modules and private record attributes start with `_`. Keep implementations out
of `__init__.py`; it contains only re-exports, optional `__all__`, and a module
docstring. Put record/type definitions in separate `types.py` or `_types.py`
modules (or a dedicated types package), and behavior in implementation modules.
Record validation may remain with its model; business logic belongs elsewhere.

Use NumPy-style function and method docstrings: a concise summary followed by
`Parameters`, `Returns`, `Raises`, or `Yields` sections where applicable. Do not
add empty sections. Write pytest tests for behavior and meaningful failure cases.

## Bootstrap and verify

The companion executable is `../../bin/python-style` relative to this skill
folder. Resolve it to an absolute path before changing directories. It requires
uv; uv installs its Python 3.12 environment and locked dependencies on first use.
It does not require a Claude marketplace client. Keep `bin/`, `lib/`,
`pyproject.toml`, `.python-version`, and `uv.lock` together when downloading.

```sh
/path/to/python/bin/python-style bootstrap ./my-project --name my-project
cd my-project
uv sync
uv run poe check
uv run poe test
uv run pre-commit install
/path/to/python/bin/python-style verify .
/path/to/python/bin/python-style verify . --run
```

Bootstrap creates a single-package uv project with a src layout. It refuses
collisions and leaves unrelated files alone. For a multi-package workspace,
bootstrap each new member, declare it in the root `[tool.uv.workspace].members`,
and manage dependencies and locking from the root. Do not blindly replace an
existing project's configuration; migrate it intentionally.

`verify` performs read-only configuration and AST checks and returns nonzero for
findings. `--run` additionally runs the target project's `uv run poe check` and
`uv run poe test`; those are project-defined commands, so use it only when running
the project's code is within the task's scope. `--json` emits a structured report.
The verifier accepts the scaffold's task shape and reports unsupported task
shapes rather than claiming they passed. Run it per package for workspaces.

Static checks are partial evidence. Review semantic record usage, serialization
boundaries, module responsibility, and appropriate private names manually.
Checks cannot infer whether every dict is a record, discover every annotation
alias, or establish that every type definition is in the right module.
