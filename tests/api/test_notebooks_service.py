from theo.infrastructure.api.app.notebooks.service import (
    _ensure_team_membership,
    _principal_teams,
)


def test_principal_teams_with_list_claims() -> None:
    principal = {"claims": {"teams": ["team-123", "team-456"]}}

    teams = _principal_teams(principal)

    assert teams == {"team-123", "team-456"}

    _ensure_team_membership(principal, "team-123")


def test_principal_teams_with_string_claims() -> None:
    principal = {"claims": {"teams": "team-123"}}

    teams = _principal_teams(principal)

    assert teams == {"team-123"}

    _ensure_team_membership(principal, "team-123")
