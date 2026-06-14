from sqlmodel import Session, select
from typing import List, Dict, Any
from app.models import BattingLine, PitchingAppearance, Lineup, Player, Game

def get_season_batting(team_id: int, session: Session, game_ids: list = None) -> List[Dict[str, Any]]:
    players = session.exec(select(Player).where(Player.team_id == team_id, Player.is_substitute == False, Player.is_coach == False)).all()
    
    query = select(BattingLine).join(Player).where(Player.team_id == team_id)
    if game_ids is not None:
        query = query.where(BattingLine.game_id.in_(game_ids))
    lines = session.exec(query).all()
    
    stats_by_player = {p.id: {
        "player_id": p.id,
        "name": f"{p.first_name} {p.last_name}",
        "jersey": p.jersey,
        "pa": 0, "ab": 0, "singles": 0, "doubles": 0, "triples": 0, "hr": 0,
        "bb": 0, "bbi": 0, "hbp": 0, "sac": 0, "intf": 0, "kd": 0, "ke": 0,
        "outs_not_k": 0, "fc": 0, "roe": 0, "rbi": 0, "r": 0, "sb": 0,
    } for p in players}
    
    for line in lines:
        if line.player_id not in stats_by_player:
            continue
        s = stats_by_player[line.player_id]
        s["singles"] += line.singles
        s["doubles"] += line.doubles
        s["triples"] += line.triples
        s["hr"] += line.hr
        s["bb"] += line.bb
        s["bbi"] += line.bbi
        s["hbp"] += line.hbp
        s["sac"] += line.sac
        s["intf"] += line.intf
        s["kd"] += line.kd
        s["ke"] += line.ke
        s["outs_not_k"] += line.outs_not_k
        s["fc"] += line.fc
        s["roe"] += line.roe
        s["rbi"] += line.rbi
        s["r"] += line.r
        s["sb"] += line.sb

    results = []
    for p_id, s in stats_by_player.items():
        H = s["singles"] + s["doubles"] + s["triples"] + s["hr"]
        AB = H + s["kd"] + s["ke"] + s["outs_not_k"] + s["fc"] + s["roe"]
        PA = AB + s["bb"] + s["bbi"] + s["hbp"] + s["sac"] + s["intf"]
        
        s["h"] = H
        s["ab"] = AB
        s["pa"] = PA
        
        avg = H / AB if AB > 0 else 0.0
        obp_denom = (AB + s["bb"] + s["bbi"] + s["hbp"] + s["sac"])
        obp = (H + s["bb"] + s["bbi"] + s["hbp"]) / obp_denom if obp_denom > 0 else 0.0
        slg = (s["singles"] + 2*s["doubles"] + 3*s["triples"] + 4*s["hr"]) / AB if AB > 0 else 0.0
        ops = obp + slg
        
        s["avg"] = round(avg, 3)
        s["obp"] = round(obp, 3)
        s["slg"] = round(slg, 3)
        s["ops"] = round(ops, 3)
        
        results.append(s)
        
    results.sort(key=lambda x: x["ops"], reverse=True)
    return results

def get_season_pitching(team_id: int, session: Session, game_ids: list = None) -> List[Dict[str, Any]]:
    players = session.exec(select(Player).where(Player.team_id == team_id, Player.is_substitute == False, Player.is_coach == False)).all()
    
    query = select(PitchingAppearance).join(Player).where(Player.team_id == team_id)
    if game_ids is not None:
        query = query.where(PitchingAppearance.game_id.in_(game_ids))
    apps = session.exec(query).all()
    
    stats_by_player = {p.id: {
        "player_id": p.id,
        "name": f"{p.first_name} {p.last_name}",
        "jersey": p.jersey,
        "ip_outs": 0, "runs_allowed": 0, "k": 0, "bb": 0, "hbp": 0,
        "appearances": 0
    } for p in players}
    
    for app in apps:
        if app.player_id not in stats_by_player:
            continue
        s = stats_by_player[app.player_id]
        s["ip_outs"] += app.ip_outs
        s["runs_allowed"] += app.runs_allowed
        s["k"] += app.k
        s["bb"] += app.bb
        s["hbp"] += app.hbp
        s["appearances"] += 1
        
    results = []
    for p_id, s in stats_by_player.items():
        ip = s["ip_outs"] / 3.0
        s["ip"] = round(ip, 2)
        s["ip_display"] = f"{s['ip_outs'] // 3}.{s['ip_outs'] % 3}" if s["ip_outs"] % 3 != 0 else str(s["ip_outs"] // 3)
        
        s["k_9"] = round((s["k"] * 9) / ip, 2) if ip > 0 else 0.0
        s["bb_9"] = round((s["bb"] * 9) / ip, 2) if ip > 0 else 0.0
        s["hbp_9"] = round((s["hbp"] * 9) / ip, 2) if ip > 0 else 0.0
        s["r_9"] = round((s["runs_allowed"] * 9) / ip, 2) if ip > 0 else 0.0
        
        results.append(s)
        
    results.sort(key=lambda x: x["ip_outs"], reverse=True)
    return results

def get_season_position(team_id: int, session: Session) -> List[Dict[str, Any]]:
    players = session.exec(select(Player).where(Player.team_id == team_id, Player.is_substitute == False, Player.is_coach == False)).all()
    
    lineups = session.exec(
        select(Lineup)
        .join(Player)
        .join(Game, Lineup.game_id == Game.id)
        .where(Player.team_id == team_id)
        .where(Game.result_runs_for.is_not(None))
    ).all()
    
    stats_by_player = {p.id: {
        "player_id": p.id,
        "name": f"{p.first_name} {p.last_name}",
        "jersey": p.jersey,
        "positions": {str(i): 0 for i in range(10)},
        "total_innings": 0
    } for p in players}
    
    for l in lineups:
        if l.player_id not in stats_by_player:
            continue
        s = stats_by_player[l.player_id]
        pos_str = str(l.position)
        if pos_str in s["positions"]:
            s["positions"][pos_str] += 1
        s["total_innings"] += 1
        
    results = []
    for p_id, s in stats_by_player.items():
        tot = s["total_innings"]
        s["bench_pct"] = round((s["positions"]["0"] / tot * 100), 1) if tot > 0 else 0.0
        results.append(s)
        
    results.sort(key=lambda x: x["jersey"])
    return results

from datetime import date, timedelta

def get_pitching_plan(team_id: int, session: Session) -> Dict[str, Any]:
    start_date = date.today() - timedelta(days=7)
    
    # Get games from start_date onwards
    games = session.exec(
        select(Game)
        .where(Game.team_id == team_id, Game.date >= start_date)
        .order_by(Game.date)
    ).all()
    
    # Get active players (excluding coaches and substitutes)
    players = session.exec(
        select(Player)
        .where(
            Player.team_id == team_id,
            Player.active == True,
            Player.is_substitute == False,
            Player.is_coach == False
        )
        .order_by(Player.jersey)
    ).all()
    
    game_ids = [g.id for g in games]
    
    # Get actual pitching appearances
    apps = session.exec(
        select(PitchingAppearance)
        .where(PitchingAppearance.game_id.in_(game_ids))
    ).all()
    
    # Get lineups
    lineups = session.exec(
        select(Lineup)
        .where(Lineup.game_id.in_(game_ids), Lineup.position == 1)
    ).all()
    
    # Group by game to see which games have actuals
    apps_by_game = {}
    for app in apps:
        apps_by_game.setdefault(app.game_id, []).append(app)
        
    lineups_by_game = {}
    for l in lineups:
        lineups_by_game.setdefault(l.game_id, []).append(l)
        
    innings = {} # map player_id -> game_id -> innings
    for p in players:
        innings[p.id] = {}
        
    for game in games:
        # If we have actual pitching appearances for this game, use them
        if game.id in apps_by_game and apps_by_game[game.id]:
            for app in apps_by_game[game.id]:
                if app.player_id in innings:
                    # Round up partial innings
                    inns = (app.ip_outs + 2) // 3
                    innings[app.player_id][game.id] = innings[app.player_id].get(game.id, 0) + inns
        else:
            # Fallback to lineups
            if game.id in lineups_by_game:
                for l in lineups_by_game[game.id]:
                    if l.player_id in innings:
                        innings[l.player_id][game.id] = innings[l.player_id].get(game.id, 0) + 1
                        
    return {
        "games": [
            {
                "id": g.id,
                "date": g.date.isoformat(),
                "opponent": g.opponent,
                "home_away": g.home_away,
                "game_type": g.game_type
            } for g in games
        ],
        "players": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "jersey": p.jersey
            } for p in players
        ],
        "pitching_innings": innings
    }
