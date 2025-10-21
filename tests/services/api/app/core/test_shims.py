import importlib
import sys
import warnings
from types import ModuleType
from typing import Any

import pytest


SHIM_DEFINITIONS = [
    {
        "shim": "theo.services.api.app.core.database",
        "facade": "theo.application.facades.database",
        "exports": ["Base", "configure_engine", "get_engine", "get_session"],
        "callables": ["configure_engine", "get_engine", "get_session"],
    },
    {
        "shim": "theo.services.api.app.core.runtime",
        "facade": "theo.application.facades.runtime",
        "exports": ["allow_insecure_startup"],
        "callables": ["allow_insecure_startup"],
    },
    {
        "shim": "theo.services.api.app.core.secret_migration",
        "facade": "theo.application.facades.secret_migration",
        "exports": ["migrate_secret_settings"],
        "callables": ["migrate_secret_settings"],
    },
    {
        "shim": "theo.services.api.app.core.settings",
        "facade": "theo.application.facades.settings",
        "exports": ["Settings", "get_settings", "get_settings_cipher"],
        "callables": ["get_settings", "get_settings_cipher"],
    },
    {
        "shim": "theo.services.api.app.core.settings_store",
        "facade": "theo.application.facades.settings_store",
        "exports": [
            "SETTINGS_NAMESPACE",
            "SettingNotFoundError",
            "load_setting",
            "require_setting",
            "save_setting",
        ],
        "callables": ["load_setting", "require_setting", "save_setting"],
    },
    {
        "shim": "theo.services.api.app.core.version",
        "facade": "theo.application.facades.version",
        "exports": ["get_git_sha"],
        "callables": ["get_git_sha"],
    },
]


def _import_module(name: str) -> ModuleType:
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.mark.parametrize("definition", SHIM_DEFINITIONS)
def test_core_shim_emits_warning_and_exports(definition: dict[str, Any]) -> None:
    facade = importlib.import_module(definition["facade"])
    with pytest.warns(DeprecationWarning) as captured:
        module = _import_module(definition["shim"])
    assert captured, "Import should emit a DeprecationWarning"
    assert sorted(module.__all__) == sorted(definition["exports"])

    for export in definition["exports"]:
        assert getattr(module, export) is getattr(facade, export)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module(definition["shim"])
        assert not any(
            issubclass(item.category, DeprecationWarning) for item in caught
        )


ALL_CALLABLE_EXPORTS = sorted(
    {name for definition in SHIM_DEFINITIONS for name in definition["callables"]}
)


@pytest.mark.parametrize("definition", SHIM_DEFINITIONS)
@pytest.mark.parametrize("callable_name", ALL_CALLABLE_EXPORTS)
def test_core_shim_forwards_calls(
    monkeypatch: pytest.MonkeyPatch, definition: dict[str, Any], callable_name: str
) -> None:
    if callable_name not in definition["callables"]:
        pytest.skip("Callable not exported by this shim")

    facade = importlib.import_module(definition["facade"])

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def sentinel(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        if kwargs.get("should_fail"):
            raise RuntimeError("boom")
        return "sentinel-result"

    monkeypatch.setattr(facade, callable_name, sentinel)
    module = _import_module(definition["shim"])

    exported = getattr(module, callable_name)

    result = exported(1, 2, flag=True)
    assert result == "sentinel-result"
    assert calls == [((1, 2), {"flag": True})]

    calls.clear()
    with pytest.raises(RuntimeError):
        exported(should_fail=True)
    assert calls == [((), {"should_fail": True})]
