"""League-specific format plugins for scoresheet parsing and lineup printing."""

from app.league_formats.registry import (
    DEFAULT_LINEUP_PRINT_VERSION,
    DEFAULT_SCORESHEET_VERSION,
    get_scoresheet_prompt,
    get_scoresheet_row_prompt,
    get_scoresheet_transcribe_prompt,
    list_scoresheet_versions,
    register_scoresheet,
)

# Import built-in formats so they self-register.
from app.league_formats import baseball_quebec  # noqa: F401

__all__ = [
    "DEFAULT_LINEUP_PRINT_VERSION",
    "DEFAULT_SCORESHEET_VERSION",
    "get_scoresheet_prompt",
    "get_scoresheet_row_prompt",
    "get_scoresheet_transcribe_prompt",
    "list_scoresheet_versions",
    "register_scoresheet",
]
