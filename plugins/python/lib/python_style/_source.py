"""Conservative syntax checks for Python source conventions."""

import ast
from pathlib import Path

from python_style._report import add
from python_style._smells import check_smells
from python_style.types import Report

_SKIP = frozenset(
    {".git", ".venv", "venv", "__pycache__", "dist", "build", ".tox", "node_modules"}
)


def check_source(root: Path, report: Report) -> None:
    """Inspect first-party source files without importing them.

    Parameters
    ----------
    root : Path
        Project directory.
    report : Report
        Findings to append to.
    """
    for path in sorted(root.rglob("*.py")):
        if any(
            part in _SKIP or part.startswith(".")
            for part in path.relative_to(root).parts
        ):
            continue
        if path.is_symlink():
            continue
        try:
            source = path.read_text()
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeError) as error:
            # python-style: allow[caught-error] Report unreadable source and continue checking other files.
            add(
                report, path, "syntax", f"Cannot inspect {path}: {type(error).__name__}"
            )
            continue
        check_smells(tree, source, path, report)
        if len(source.splitlines()) > 300:
            add(
                report,
                path,
                "size",
                "Prefer splitting files longer than 300 lines into submodules.",
            )
        if path.name == "__init__.py":
            for node in tree.body:
                docstring = (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
                exports = isinstance(node, (ast.Assign, ast.AnnAssign)) and all(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                )
                if not (
                    isinstance(node, (ast.Import, ast.ImportFrom))
                    or docstring
                    or exports
                ):
                    add(
                        report,
                        path,
                        "init",
                        "__init__.py is for re-exports only.",
                        node.lineno,
                    )
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                args += [
                    arg
                    for arg in (node.args.vararg, node.args.kwarg)
                    if arg is not None
                ]
                if node.returns is None or any(
                    arg.annotation is None and arg.arg not in {"self", "cls"}
                    for arg in args
                ):
                    add(
                        report,
                        path,
                        "annotations",
                        "Annotate all arguments and the return type.",
                        node.lineno,
                    )
            if (
                isinstance(node, ast.Dict)
                and node.keys
                and all(
                    isinstance(key, ast.Constant) and isinstance(key.value, str)
                    for key in node.keys
                )
            ):
                add(
                    report,
                    path,
                    "records",
                    "Fixed string-key dict: use a dataclass or Pydantic v2 model if this is a record.",
                    node.lineno,
                )
            if isinstance(node, ast.ClassDef):
                for statement in node.body:
                    if isinstance(statement, ast.Assign):
                        add(
                            report,
                            path,
                            "annotations",
                            "Annotate class attributes.",
                            statement.lineno,
                        )
                bases = [ast.unparse(base).split(".")[-1] for base in node.bases]
                decorators = [
                    ast.unparse(item).split("(")[0].split(".")[-1]
                    for item in node.decorator_list
                ]
                if "TypedDict" in bases:
                    add(
                        report,
                        path,
                        "records",
                        "Use dataclasses for memory and BaseModel for wire records.",
                        node.lineno,
                    )
                if (
                    ("BaseModel" in bases or "dataclass" in decorators)
                    and path.stem not in {"types", "_types"}
                    and "types" not in path.relative_to(root).parts
                ):
                    add(
                        report,
                        path,
                        "types",
                        "Move record definitions to a separate types module.",
                        node.lineno,
                    )
