"""Lazy local configuration for the offline watcher core."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


DEFAULT_WATCHER_ROOT = Path(r"G:\EMPRESAS")


@dataclass(frozen=True, slots=True)
class WatcherConfig:
    root: Path = DEFAULT_WATCHER_ROOT

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "WatcherConfig":
        source = os.environ if environ is None else environ
        return cls(root=Path(source.get("LUMEN_WATCHER_ROOT", str(DEFAULT_WATCHER_ROOT))))
