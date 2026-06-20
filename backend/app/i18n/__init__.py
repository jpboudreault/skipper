from __future__ import annotations

import os
from typing import Any

POSITION_LABELS: dict[str, dict[int, str]] = {
    "en": {
        0: "Bench (X)",
        1: "Pitcher (P)",
        2: "Catcher (C)",
        3: "First Base (1B)",
        4: "Second Base (2B)",
        5: "Third Base (3B)",
        6: "Shortstop (SS)",
        7: "Left Field (LF)",
        8: "Center Field (CF)",
        9: "Right Field (RF)",
    },
    "fr": {
        0: "Banc (X)",
        1: "Lanceur (P)",
        2: "Receveur (C)",
        3: "Première base (1B)",
        4: "Deuxième base (2B)",
        5: "Troisième base (3B)",
        6: "Arrêt-court (SS)",
        7: "Champ gauche (LF)",
        8: "Champ centre (CF)",
        9: "Champ droit (RF)",
    },
}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "internal_server_error": "Internal Server Error",
        "not_authorized_for_team": "Not authorized for this team",
        "game_not_found": "Game not found on this team",
        "player_not_found": "Player {player_id} not found on this team",
        "team_not_found": "Team not found",
        "google_client_id_not_configured": "GOOGLE_CLIENT_ID is not configured on the server.",
        "invalid_google_token": "Invalid Google token: {reason}",
        "google_token_verification_failed": "Google token verification failed: {reason}",
        "invalid_token": "Invalid token",
        "invalid_user": "Invalid user",
        "token_expired": "Token has expired",
        "invalid_user_session": "Invalid user session",
        "user_not_associated_with_team": "User not associated with any team",
        "google_email_missing": "Invalid Google token payload: email missing",
        "email_not_authorized": "Your email is not authorized to access this app.",
        "photo_ingestion_not_configured": "Photo ingestion is not configured. Set the ANTHROPIC_API_KEY environment variable.",
        "invalid_file_type": "Invalid file type '{content_type}'. Please upload a JPEG, PNG, or WebP image.",
        "file_empty": "Uploaded file is empty.",
        "file_too_large": "File too large. Maximum size is 20 MB.",
        "unknown_scoresheet_version": "Unknown scoresheet version",
        "ai_service_unavailable": "{reason}",
        "ai_parsing_failed": "AI parsing failed: {reason}",
        "insufficient_players": "Need at least 9 available players, only {count} available",
        "duplicate_position_lock": "Inning {inning}: Multiple players locked to the same position ({position}): {players}.",
        "multiple_positions_lock": "Inning {inning}: {player_name} is locked to multiple positions ({positions}).",
        "pitcher_game_cap": "{player_name} is locked to pitch in {count} innings, which exceeds the game limit of {max} inning(s).",
        "pitcher_7day_cap": "{player_name} is locked to pitch in {count} innings, exceeding their remaining 7-day rolling limit of {remaining} (already pitched {pitched} innings in last 7 days).",
        "pitcher_reentry_violation": "Pitcher Re-entry violation: {player_name} is locked to pitch in Inning {first_inning} and Inning {last_inning}, but is locked to {position} in Inning {between_inning}.",
        "pitcher_reentry_game_cap": "Pitcher Re-entry & Cap violation: {player_name} is locked to pitch in Inning {first_inning} and Inning {last_inning}, which would force them to pitch for at least {min_required} consecutive innings, exceeding the game limit of {max} inning(s).",
        "pitcher_reentry_7day_cap": "Pitcher Re-entry & Cap violation: {player_name} is locked to pitch in Inning {first_inning} and Inning {last_inning}, forcing at least {min_required} consecutive innings, exceeding their remaining 7-day rolling limit of {remaining}.",
        "catcher_pitcher_rest": "Catcher-to-Pitcher Rest violation: {player_name} catches in Inning {catcher_inning} and is locked to pitch in Inning {pitcher_inning}.",
        "forbidden_position_substitute_pitch": "Forbidden Position: {player_name} is a substitute and cannot pitch, but is locked to that position in Inning {inning}.",
        "forbidden_position": "Forbidden Position: {player_name} is forbidden from playing {position}, but is locked to that position in Inning {inning}.",
        "no_feasible_lineup": "No feasible lineup found. Check constraints and availability.",
        "invalid_inning_count": "Inning count must be between {min_innings} and {max_innings}.",
        "lineup_inning_out_of_range": "Lineup cell for inning {inning} is outside the game range (1-{max_inning}).",
    },
    "fr": {
        "internal_server_error": "Erreur interne du serveur",
        "not_authorized_for_team": "Non autorisé pour cette équipe",
        "game_not_found": "Match introuvable pour cette équipe",
        "player_not_found": "Joueur {player_id} introuvable dans cette équipe",
        "team_not_found": "Équipe introuvable",
        "google_client_id_not_configured": "GOOGLE_CLIENT_ID n'est pas configuré sur le serveur.",
        "invalid_google_token": "Jeton Google invalide : {reason}",
        "google_token_verification_failed": "Échec de la vérification du jeton Google : {reason}",
        "invalid_token": "Jeton invalide",
        "invalid_user": "Utilisateur invalide",
        "token_expired": "Le jeton a expiré",
        "invalid_user_session": "Session utilisateur invalide",
        "user_not_associated_with_team": "Utilisateur non associé à une équipe",
        "google_email_missing": "Charge utile du jeton Google invalide : courriel manquant",
        "email_not_authorized": "Votre courriel n'est pas autorisé à accéder à cette application.",
        "photo_ingestion_not_configured": "L'importation photo n'est pas configurée. Définissez la variable d'environnement ANTHROPIC_API_KEY.",
        "invalid_file_type": "Type de fichier invalide « {content_type} ». Veuillez téléverser une image JPEG, PNG ou WebP.",
        "file_empty": "Le fichier téléversé est vide.",
        "file_too_large": "Fichier trop volumineux. La taille maximale est de 20 Mo.",
        "unknown_scoresheet_version": "Version de feuille de match inconnue",
        "ai_service_unavailable": "{reason}",
        "ai_parsing_failed": "Échec de l'analyse IA : {reason}",
        "insufficient_players": "Au moins 9 joueurs disponibles requis, seulement {count} disponibles",
        "duplicate_position_lock": "Manche {inning} : Plusieurs joueurs verrouillés à la même position ({position}) : {players}.",
        "multiple_positions_lock": "Manche {inning} : {player_name} est verrouillé à plusieurs positions ({positions}).",
        "pitcher_game_cap": "{player_name} est verrouillé comme lanceur pour {count} manches, ce qui dépasse la limite de {max} manche(s) par match.",
        "pitcher_7day_cap": "{player_name} est verrouillé comme lanceur pour {count} manches, dépassant sa limite glissante de 7 jours de {remaining} (déjà {pitched} manches dans les 7 derniers jours).",
        "pitcher_reentry_violation": "Violation de réentrée du lanceur : {player_name} est verrouillé comme lanceur à la manche {first_inning} et à la manche {last_inning}, mais est verrouillé à {position} à la manche {between_inning}.",
        "pitcher_reentry_game_cap": "Violation de réentrée et limite : {player_name} est verrouillé comme lanceur à la manche {first_inning} et à la manche {last_inning}, ce qui l'obligerait à lancer au moins {min_required} manches consécutives, dépassant la limite de {max} manche(s) par match.",
        "pitcher_reentry_7day_cap": "Violation de réentrée et limite : {player_name} est verrouillé comme lanceur à la manche {first_inning} et à la manche {last_inning}, forçant au moins {min_required} manches consécutives, dépassant sa limite glissante de 7 jours de {remaining}.",
        "catcher_pitcher_rest": "Violation repos receveur-lanceur : {player_name} attrape à la manche {catcher_inning} et est verrouillé comme lanceur à la manche {pitcher_inning}.",
        "forbidden_position_substitute_pitch": "Position interdite : {player_name} est un substitut et ne peut pas lancer, mais est verrouillé à cette position à la manche {inning}.",
        "forbidden_position": "Position interdite : {player_name} ne peut pas jouer {position}, mais est verrouillé à cette position à la manche {inning}.",
        "no_feasible_lineup": "Aucune composition réalisable. Vérifiez les contraintes et la disponibilité.",
        "invalid_inning_count": "Le nombre de manches doit être entre {min_innings} et {max_innings}.",
        "lineup_inning_out_of_range": "La cellule d'alignement pour la manche {inning} dépasse la plage du match (1-{max_inning}).",
    },
}


def get_locked_locale() -> str | None:
    value = os.environ.get("SKIPPER_LOCALE", "").strip().lower()
    if value in ("en", "fr"):
        return value
    return None


def parse_locale(accept_language: str | None) -> str:
    locked = get_locked_locale()
    if locked:
        return locked
    if not accept_language:
        return "en"
    for part in accept_language.split(","):
        lang = part.split(";")[0].strip().lower()
        base = lang.split("-")[0]
        if base == "fr":
            return "fr"
        if base == "en":
            return "en"
    return "en"


def _format_positions(locale: str, position_ids: list[int]) -> str:
    labels = POSITION_LABELS.get(locale, POSITION_LABELS["en"])
    return ", ".join(labels.get(pos, str(pos)) for pos in position_ids)


def _resolve_params(params: dict[str, Any], locale: str) -> dict[str, Any]:
    resolved = dict(params)
    if "position_id" in resolved:
        pos_id = resolved.pop("position_id")
        labels = POSITION_LABELS.get(locale, POSITION_LABELS["en"])
        resolved["position"] = labels.get(pos_id, str(pos_id))
    if "position_ids" in resolved:
        pos_ids = resolved.pop("position_ids")
        resolved["positions"] = _format_positions(locale, pos_ids)
    return resolved


def translate(code: str, params: dict[str, Any] | None = None, locale: str = "en") -> str:
    params = params or {}
    resolved_params = _resolve_params(params, locale)
    template = MESSAGES.get(locale, {}).get(code) or MESSAGES["en"].get(code) or code
    try:
        return template.format(**resolved_params)
    except KeyError:
        return template


def localize_detail(detail: Any, locale: str) -> Any:
    if isinstance(detail, dict) and "code" in detail:
        return translate(detail["code"], detail.get("params"), locale)
    return detail
