import pytest

from theo.application.security import Principal, PrincipalResolver


class _Resolver(PrincipalResolver):
    async def resolve(
        self,
        *,
        request: object,
        authorization: str | None,
        api_key_header: str | None,
    ) -> Principal:
        return Principal(
            method="bearer",
            subject="user-1",
            scopes=["read"],
            claims={"authorized": True},
            token=authorization or "",
        )


@pytest.mark.asyncio
async def test_principal_resolver_protocol() -> None:
    resolver = _Resolver()

    assert isinstance(resolver, PrincipalResolver)

    principal = await resolver.resolve(
        request=object(), authorization="token", api_key_header=None
    )

    assert principal["subject"] == "user-1"
    assert principal["token"] == "token"
    assert principal["scopes"] == ["read"]
