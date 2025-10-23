"""SQLite-specific database maintenance utilities for adapters."""
from __future__ import annotations

import gc
import threading
import time
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.engine import Connection, Engine

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from typing import Protocol

    class _Disposable(Protocol):
        def dispose(self) -> None: ...
else:  # pragma: no cover - runtime import guard
    _Disposable = object  # type: ignore[assignment]

def _collect_open_files(process, target_paths: set[str], timeout: float = 1.0):
    """Best-effort collection of open file handles with a timeout safeguard."""

    entries: list = []
    errors: list[BaseException] = []

    def _invoke() -> None:
        try:
            entries.append(process.open_files())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive guard
            errors.append(exc)

    worker = threading.Thread(target=_invoke, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        return None
    if errors:
        return []
    if not entries:
        return []
    return [entry for entry in entries[0] if getattr(entry, "path", None) in target_paths]


def dispose_sqlite_engine(
    bind: Connection | Engine | None,
    *,
    dispose_engine: bool = True,
    dispose_callable: Callable[[], None] | None = None,
) -> None:
    """Dispose SQLite engines to release file handles promptly."""

    engine: Engine | None = None
    if isinstance(bind, Connection):
        engine = bind.engine
    elif isinstance(bind, Engine):
        engine = bind
    if engine is None:
        return
    if getattr(getattr(engine, "dialect", None), "name", None) != "sqlite":
        return
    url = getattr(engine, "url", None)
    database_name = getattr(url, "database", None)
    url_string = str(url) if url is not None else ""
    if dispose_engine:
        try:
            if dispose_callable is not None:
                dispose_callable()
            elif not database_name or database_name == ":memory:" or "mode=memory" in url_string:
                return
            else:
                engine.dispose()
        except Exception:  # pragma: no cover - defensive release guard
            return
    if not database_name or database_name == ":memory:" or "mode=memory" in url_string:
        return
    try:
        import inspect
        import sqlite3  # pragma: no cover - optional inspection for stray connections
    except Exception:
        sqlite3 = None
        inspect = None  # type: ignore[assignment]
    if sqlite3 is not None:
        cursor_type = getattr(sqlite3, "Cursor", None)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            for obj in gc.get_objects():
                try:
                    if isinstance(obj, sqlite3.Connection):
                        obj.close()
                    elif cursor_type is not None and isinstance(obj, cursor_type):
                        obj.close()
                except ReferenceError:
                    continue
                except Exception:
                    continue
        if inspect is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                for frame_info in inspect.stack():
                    for value in list(frame_info.frame.f_locals.values()):
                        try:
                            if isinstance(value, sqlite3.Connection):
                                value.close()
                            elif cursor_type is not None and isinstance(value, cursor_type):
                                value.close()
                        except Exception:
                            continue
    gc.collect()
    time.sleep(0.05)
    if database_name and database_name != ":memory:":
        db_path = Path(database_name)
        candidates = [db_path]
        candidates.extend(
            db_path.parent / f"{db_path.name}{suffix}"
            for suffix in ("-journal", "-wal", "-shm")
        )
        for candidate in candidates:
            if not candidate.exists():
                continue
            for _ in range(100):
                try:
                    with candidate.open("rb"):
                        break
                except PermissionError:
                    time.sleep(0.05)
        if sqlite3 is not None and db_path.exists():
            for _ in range(100):
                try:
                    with sqlite3.connect(
                        f"file:{db_path}?mode=ro&cache=shared", uri=True
                    ):
                        break
                except sqlite3.OperationalError:
                    time.sleep(0.05)
        try:
            import psutil  # pragma: no cover - optional handle inspection
        except Exception:
            psutil = None  # type: ignore[assignment]
        if psutil is not None:
            try:
                process = psutil.Process()
            except Exception:  # pragma: no cover - defensive guard
                process = None
            if process is not None:
                target_paths = {str(path.resolve()) for path in candidates if path.exists()}
                for _ in range(100):
                    open_entries = _collect_open_files(process, target_paths)
                    if open_entries is None:
                        break
                    if not open_entries:
                        break
                    for entry in open_entries:
                        try:
                            import ctypes  # pragma: no cover - windows-only
                            import msvcrt  # pragma: no cover - windows-only

                            handle = msvcrt.get_osfhandle(entry.fd)
                            ctypes.windll.kernel32.CloseHandle(int(handle))
                        except Exception:
                            continue
                    time.sleep(0.05)
