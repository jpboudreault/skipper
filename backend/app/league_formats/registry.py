"""Registry for league-specific scoresheet prompt builders."""

from typing import Callable, Dict, List, Optional

DEFAULT_SCORESHEET_VERSION = "baseball_quebec"
DEFAULT_LINEUP_PRINT_VERSION = "baseball_quebec"

ScoresheetPromptBuilder = Callable[[List[dict]], str]

_SCORESHEET_BUILDERS: Dict[str, ScoresheetPromptBuilder] = {}
_TRANSCRIBE_BUILDERS: Dict[str, ScoresheetPromptBuilder] = {}
_ROW_BUILDERS: Dict[str, ScoresheetPromptBuilder] = {}


def register_scoresheet(version: str):
    """Decorator to register a scoresheet prompt builder for a league format."""

    def decorator(fn: ScoresheetPromptBuilder) -> ScoresheetPromptBuilder:
        _SCORESHEET_BUILDERS[version] = fn
        return fn

    return decorator


def register_scoresheet_transcribe(version: str):
    """Decorator to register a transcription-only prompt builder."""

    def decorator(fn: ScoresheetPromptBuilder) -> ScoresheetPromptBuilder:
        _TRANSCRIBE_BUILDERS[version] = fn
        return fn

    return decorator


def get_scoresheet_transcribe_prompt(version: Optional[str], players: List[dict]) -> str:
    """Return the transcription prompt for the given scoresheet version."""
    resolved = version or DEFAULT_SCORESHEET_VERSION
    builder = _TRANSCRIBE_BUILDERS.get(resolved)
    if builder is None:
        if resolved != DEFAULT_SCORESHEET_VERSION:
            raise ValueError(f"Unknown scoresheet version '{resolved}'")
        builder = _TRANSCRIBE_BUILDERS[DEFAULT_SCORESHEET_VERSION]
    return builder(players)


def register_scoresheet_rows(version: str):
    """Decorator to register a per-row scoresheet prompt builder."""

    def decorator(fn: ScoresheetPromptBuilder) -> ScoresheetPromptBuilder:
        _ROW_BUILDERS[version] = fn
        return fn

    return decorator


def get_scoresheet_row_prompt(version: Optional[str], players: List[dict]) -> str:
    """Return the per-row vision prompt for the given scoresheet version."""
    resolved = version or DEFAULT_SCORESHEET_VERSION
    builder = _ROW_BUILDERS.get(resolved)
    if builder is None:
        if resolved != DEFAULT_SCORESHEET_VERSION:
            raise ValueError(f"Unknown scoresheet version '{resolved}'")
        builder = _ROW_BUILDERS[DEFAULT_SCORESHEET_VERSION]
    return builder(players)


def get_scoresheet_prompt(version: Optional[str], players: List[dict]) -> str:
    """Return the vision prompt for the given scoresheet version."""
    resolved = version or DEFAULT_SCORESHEET_VERSION
    builder = _SCORESHEET_BUILDERS.get(resolved)
    if builder is None:
        if resolved != DEFAULT_SCORESHEET_VERSION:
            raise ValueError(f"Unknown scoresheet version '{resolved}'")
        builder = _SCORESHEET_BUILDERS[DEFAULT_SCORESHEET_VERSION]
    return builder(players)


def list_scoresheet_versions() -> List[str]:
    return sorted(_SCORESHEET_BUILDERS.keys())
