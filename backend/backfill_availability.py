import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from app.models import Player, Availability, Game
from app.db import engine

with Session(engine) as session:
    games = session.exec(select(Game)).all()
    total = 0
    for game in games:
        players = session.exec(
            select(Player).where(Player.team_id == game.team_id, Player.active == True)
        ).all()
        for p in players:
            exists = session.exec(
                select(Availability).where(
                    Availability.game_id == game.id,
                    Availability.player_id == p.id
                )
            ).first()
            if not exists:
                session.add(Availability(game_id=game.id, player_id=p.id, status="available"))
                total += 1
    session.commit()
    print(f"Backfilled {total} availability rows across {len(games)} game(s)")
