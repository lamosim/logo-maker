"""JSON stdout contract shared by every CLI command."""
from __future__ import annotations

import json
import sys
from typing import Any, Iterable, NoReturn

EXIT_OK = 0
EXIT_RULE = 2
EXIT_EXTERNAL = 3
EXIT_VERIFY = 4


class CliError(Exception):
    """An error the CLI reports as JSON. `code` is the process exit code."""

    def __init__(self, message: str, code: int = EXIT_RULE, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def emit(
    data: dict[str, Any] | None = None,
    *,
    ok: bool = True,
    errors: Iterable[str] = (),
    warnings: Iterable[str] = (),
    code: int = EXIT_OK,
) -> NoReturn:
    payload: dict[str, Any] = {"ok": ok, "errors": list(errors), "warnings": list(warnings)}
    payload.update(data or {})
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    sys.stdout.flush()
    sys.exit(code)
