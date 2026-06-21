"""Team dashboard warmup across league integrations."""

from __future__ import annotations

from sqlmodel import Session

from app.models import Team


def warmup_dashboard(session: Session, team: Team, *, limit: int = 3) -> dict:
    if team.integration_version == "lfbq_spordle":
        from app.league_integrations.lfbq_spordle.warmup import warmup_team_dashboard

        return warmup_team_dashboard(session, team, limit=limit)
    return {"ok": False, "reason": "integration_not_configured"}
