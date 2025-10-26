import pytest

from theo.application.facades import security as security_facade
from theo.application.security import Principal, PrincipalResolver


class _Resolver(PrincipalResolver):
    def __init__(self) -> None:
        self.calls: list[tuple[object, str | None, str | None]] = []

    async def resolve(
        self,
        *,
        request: object,
        authorization: str | None,
        api_key_header: str | None,
    ) -> Principal:
        self.calls.append((request, authorization, api_key_header))
        return Principal(method="bearer", subject="user", scopes=[], claims={}, token="tkn")


@pytest.fixture(autouse=True)
def _reset_resolver() -> None:
    previous = getattr(security_facade, "_resolver", None)
    security_facade._resolver = None  # type: ignore[attr-defined]
    try:
        yield
    finally:
        security_facade._resolver = previous  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_resolve_principal_requires_configuration() -> None:
    with pytest.raises(RuntimeError):
        security_facade.get_principal_resolver()

    with pytest.raises(RuntimeError):
        await security_facade.resolve_principal(request=object(), authorization=None, api_key_header=None)


@pytest.mark.asyncio
async def test_facade_delegates_to_resolver() -> None:
    resolver = _Resolver()
    security_facade.set_principal_resolver(resolver)

    principal = await security_facade.resolve_principal(
        request="req", authorization="Bearer token", api_key_header="api-key"
    )

    assert principal["subject"] == "user"
    assert resolver.calls == [("req", "Bearer token", "api-key")]
    assert security_facade.get_principal_resolver() is resolver
