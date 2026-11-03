"""The replicated state machine: a tiny key-value store.

Commands are immutable values so the same object can sit in many logs at once.
``apply`` must be deterministic; that is the whole contract replication relies on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Set:
    key: str
    value: Any


@dataclass(frozen=True)
class Delete:
    key: str


@dataclass(frozen=True)
class Get:
    """A read. It goes through the log like a write so that it is ordered with
    them: a deposed leader can't answer it, because it can't commit it."""

    key: str


class KeyValueStore:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def apply(self, command: Set | Delete | Get) -> Any:
        if isinstance(command, Set):
            self._data[command.key] = command.value
        elif isinstance(command, Delete):
            self._data.pop(command.key, None)
        elif isinstance(command, Get):
            return self._data.get(command.key)
        else:
            raise TypeError(f"unknown command: {command!r}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._data)
