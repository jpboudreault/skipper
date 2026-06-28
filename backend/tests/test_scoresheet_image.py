"""Unit tests for scoresheet row detection and row tile prep."""

import io
from pathlib import Path

from PIL import Image

from app.scoresheet_image import (
    _detect_row_boxes,
    prepare_scoresheet_row_tiles,
    prepare_scoresheet_tiles,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scoresheets"


def test_detect_row_boxes_scenario_01():
    img = Image.open(FIXTURES / "scenario_01.jpg")
    boxes = _detect_row_boxes(img, expected_rows=4)
    assert len(boxes) == 4
    assert boxes[0][0] < boxes[1][0] < boxes[2][0] < boxes[3][0]


def test_detect_row_boxes_scenario_02():
    img = Image.open(FIXTURES / "scenario_02.jpg")
    boxes = _detect_row_boxes(img, expected_rows=7)
    assert len(boxes) == 7


def test_prepare_row_tiles_returns_labels():
    raw = (FIXTURES / "scenario_01.jpg").read_bytes()
    tiles = prepare_scoresheet_row_tiles(raw, "image/jpeg", expected_rows=4)
    assert len(tiles) >= 4
    assert all(label.startswith("Ligne") for _, _, label in tiles)


def test_prepare_sheet_tiles_non_empty():
    raw = (FIXTURES / "scenario_02.jpg").read_bytes()
    tiles = prepare_scoresheet_tiles(raw, "image/jpeg")
    assert len(tiles) >= 1
    for data, media in tiles:
        assert media == "image/jpeg"
        assert len(data) > 1000
