"""Unit tests for scoresheet transcription → stat interpretation."""

from app.scoresheet_interpret import interpret_transcriptions, merge_transcriptions


def test_merge_transcriptions_keeps_best_cells():
    merged = merge_transcriptions([
        {"jersey": 46, "cells": ["BB"], "confidence": 0.7},
        {"jersey": 46, "cells": ["BB encerclé", "OPT"], "confidence": 0.9},
    ])
    assert len(merged) == 1
    assert merged[0]["cells"] == ["BB encerclé", "OPT"]
    assert merged[0]["confidence"] == 0.9


def test_merge_transcriptions_concatenates_horizontal_tiles():
    merged = merge_transcriptions([
        {"jersey": 44, "cells": ["1B", "vide"], "confidence": 0.8},
        {"jersey": 44, "cells": ["BB", "KD"], "confidence": 0.9},
    ])
    assert merged[0]["cells"] == ["1B", "vide", "BB", "KD"]


def test_interpret_strikeouts_and_walk():
    rows = interpret_transcriptions(
        [{"jersey": 17, "cells": ["KD", "KE", "vide"], "confidence": 0.8}],
        roster_jerseys=[17],
    )
    assert len(rows) == 1
    assert rows[0]["kd"] == 1
    assert rows[0]["ke"] == 1


def test_interpret_circled_hit_at_top():
    rows = interpret_transcriptions(
        [{"jersey": 45, "cells": ["2 encerclé en haut, 1 3 CC non encerclés"], "confidence": 0.9}],
        roster_jerseys=[45],
    )
    assert rows[0]["doubles"] == 1
    assert rows[0]["singles"] == 0


def test_interpret_rbi_from_diamond_number():
    rows = interpret_transcriptions(
        [
            {"jersey": 46, "cells": ["losange complet tracé, losange avec 52"], "confidence": 0.9},
            {"jersey": 52, "cells": ["OPT"], "confidence": 0.8},
        ],
        roster_jerseys=[46, 52],
    )
    by_jersey = {r["jersey"]: r for r in rows}
    assert by_jersey[46]["r"] == 1
    assert by_jersey[52]["rbi"] == 1
    assert by_jersey[52]["fc"] == 1


def test_interpret_bp_no_rbi():
    rows = interpret_transcriptions(
        [{"jersey": 46, "cells": ["BP dans le losange", "KD"], "confidence": 0.9}],
        roster_jerseys=[46],
    )
    assert rows[0]["rbi"] == 0
    assert rows[0]["kd"] == 1


def test_interpret_circled_left_column_bb():
    rows = interpret_transcriptions(
        [{"jersey": 46, "cells": ["BB encerclé à gauche"], "confidence": 0.9}],
        roster_jerseys=[46],
    )
    assert rows[0]["bb"] == 1


def test_interpret_circled_left_column_fa():
    rows = interpret_transcriptions(
        [{"jersey": 41, "cells": ["FA encerclé à gauche"], "confidence": 0.9}],
        roster_jerseys=[41],
    )
    assert rows[0]["hbp"] == 1


def test_interpret_left_column_not_circled_ignored():
    rows = interpret_transcriptions(
        [{"jersey": 46, "cells": ["colonne gauche BB BBI FA SAC INT, rien encerclé"], "confidence": 0.9}],
        roster_jerseys=[46],
    )
    assert rows == []


def test_interpret_filters_roster_only():
    rows = interpret_transcriptions(
        [{"jersey": 99, "cells": ["KD"], "confidence": 0.5}],
        roster_jerseys=[17],
    )
    assert rows == []
