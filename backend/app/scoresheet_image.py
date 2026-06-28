"""Prepare scoresheet photos for Claude vision (tiling + row crops + sizing)."""

from __future__ import annotations

import io
from typing import List, Optional, Tuple

from PIL import Image

# Anthropic downscales images beyond these limits; keep each tile under them.
MAX_LONG_EDGE = 1568
MAX_PIXELS = 1_150_000
OVERLAP_RATIO = 0.06
MIN_HEIGHT = 1000
MIN_ROW_HEIGHT = 120
ROW_TARGET_HEIGHT = 320


def prepare_scoresheet_tiles(image_bytes: bytes, content_type: str) -> List[Tuple[bytes, str]]:
    """
    Split a scoresheet into tiles that preserve readable cell detail.

    Wide Baseball Québec sheets are tiled horizontally (inning columns).
    Tall sheets are tiled vertically. Small crops are upscaled first.
    """
    img = _load_rgb(image_bytes)
    img = _upscale_if_needed(img)
    width, height = img.size

    if width > MAX_LONG_EDGE:
        tiles = _horizontal_tiles(img)
    elif height > MAX_LONG_EDGE or width * height > MAX_PIXELS:
        tiles = _vertical_tiles(img)
    else:
        tiles = [_resize_if_needed(img)]

    return [_encode_jpeg(t) for t in tiles]


def prepare_scoresheet_row_tiles(
    image_bytes: bytes,
    content_type: str,
    expected_rows: Optional[int] = None,
) -> List[Tuple[bytes, str, str]]:
    """
    Crop individual batter rows and return labeled JPEG tiles.

    Each row uses the full sheet width (optionally split into 2 horizontal tiles
    when very wide). Returns (jpeg_bytes, media_type, label) tuples.
    """
    img = _load_rgb(image_bytes)
    img = _upscale_if_needed(img)
    row_boxes = _detect_row_boxes(img, expected_rows=expected_rows)

    labeled: List[Tuple[bytes, str, str]] = []
    for index, (y0, y1) in enumerate(row_boxes, start=1):
        row = img.crop((0, y0, img.width, y1))
        row = _enlarge_row(row)
        parts = _row_horizontal_parts(row)
        if len(parts) == 1:
            labeled.append((_encode_jpeg(parts[0])[0], "image/jpeg", f"Ligne {index} (frappeur #{index}, haut vers bas)"))
            continue
        for part_index, part in enumerate(parts, start=1):
            label = f"Ligne {index} tuile {part_index}/{len(parts)} (frappeur #{index}, haut vers bas)"
            labeled.append((_encode_jpeg(part)[0], "image/jpeg", label))
    return labeled


def _load_rgb(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _detect_row_boxes(img: Image.Image, expected_rows: Optional[int] = None) -> List[Tuple[int, int]]:
    """Find batter row y-ranges using ink density on the left grid column."""
    width, height = img.size
    gray = img.convert("L")
    sample_w = max(24, int(width * 0.12))
    pixels = gray.load()

    row_ink: List[float] = []
    for y in range(height):
        dark = 0
        for x in range(sample_w):
            if pixels[x, y] < 185:
                dark += 1
        row_ink.append(dark / sample_w)

    smoothed = _smooth(row_ink, window=7)
    threshold = max(0.08, sum(smoothed) / len(smoothed) * 0.75)

    segments: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for y, value in enumerate(smoothed):
        if value >= threshold:
            if start is None:
                start = y
        elif start is not None:
            segments.append((start, y))
            start = None
    if start is not None:
        segments.append((start, height))

    min_height = max(MIN_ROW_HEIGHT // 2, int(height / 20))
    segments = [(s, e) for s, e in segments if e - s >= min_height]
    segments = _merge_nearby_segments(segments, gap=max(8, min_height // 3))

    if expected_rows:
        detected_count = len(segments)
        if detected_count != expected_rows:
            if not segments or detected_count == 1 or abs(detected_count - expected_rows) <= 2:
                segments = _equal_row_boxes(height, expected_rows)
    elif not segments:
        count = max(1, height // max(MIN_ROW_HEIGHT, 1))
        segments = _equal_row_boxes(height, count)

    pad = max(4, min_height // 8)
    return [(max(0, s - pad), min(height, e + pad)) for s, e in segments]


def _equal_row_boxes(height: int, num_rows: int) -> List[Tuple[int, int]]:
    num_rows = max(1, num_rows)
    band = height / num_rows
    overlap = max(6, int(band * 0.06))
    boxes: List[Tuple[int, int]] = []
    for i in range(num_rows):
        y0 = int(i * band) - (overlap if i else 0)
        y1 = int((i + 1) * band) + (overlap if i < num_rows - 1 else 0)
        boxes.append((max(0, y0), min(height, y1)))
    return boxes


def _merge_nearby_segments(segments: List[Tuple[int, int]], gap: int) -> List[Tuple[int, int]]:
    if not segments:
        return []
    merged = [segments[0]]
    for s, e in segments[1:]:
        prev_s, prev_e = merged[-1]
        if s - prev_e <= gap:
            merged[-1] = (prev_s, e)
        else:
            merged.append((s, e))
    return merged


def _smooth(values: List[float], window: int) -> List[float]:
    if window <= 1:
        return values
    half = window // 2
    out: List[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        chunk = values[lo:hi]
        out.append(sum(chunk) / len(chunk))
    return out


def _enlarge_row(row: Image.Image) -> Image.Image:
    """Scale a row crop to use Anthropic's width budget for inning columns."""
    width, height = row.size
    if width <= 0 or height <= 0:
        return row
    scale = min(MAX_LONG_EDGE / width, ROW_TARGET_HEIGHT / height, 3.0)
    if pixels := width * height:
        scale = min(scale, (MAX_PIXELS / pixels) ** 0.5)
    if scale <= 1.05:
        return _resize_if_needed(row)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return row.resize(new_size, Image.Resampling.LANCZOS)


def _row_horizontal_parts(row: Image.Image) -> List[Image.Image]:
    """Split a wide row into at most 2 parts, keeping jersey column on part 2."""
    width, height = row.size
    if width <= MAX_LONG_EDGE:
        return [_resize_if_needed(row)]

    jersey_strip = min(max(100, int(width * 0.08)), 220)
    overlap = max(30, int(width * OVERLAP_RATIO))
    split = (width + jersey_strip) // 2

    left = row.crop((0, 0, min(width, split + overlap), height))
    right_start = max(jersey_strip, split - overlap)
    innings = row.crop((right_start, 0, width, height))
    strip = row.crop((0, 0, jersey_strip, height))
    right = Image.new("RGB", (strip.width + innings.width, height))
    right.paste(strip, (0, 0))
    right.paste(innings, (strip.width, 0))
    return [_resize_if_needed(left), _resize_if_needed(right)]


def _upscale_if_needed(img: Image.Image) -> Image.Image:
    """Upscale short/wide crops so each row has enough pixels for handwriting."""
    width, height = img.size
    if height >= MIN_HEIGHT:
        return img
    scale = MIN_HEIGHT / height
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _horizontal_tiles(img: Image.Image) -> List[Image.Image]:
    width, height = img.size
    jersey_strip = min(max(120, int(width * 0.08)), 260)
    num_tiles = 2
    overlap = max(40, int(width * OVERLAP_RATIO))
    content_width = max(1, width - jersey_strip)
    band = (content_width + overlap * (num_tiles - 1)) // num_tiles

    tiles: List[Image.Image] = []
    content_start = jersey_strip
    for i in range(num_tiles):
        if i == num_tiles - 1:
            x_start, x_end = content_start, width
        else:
            x_end = min(width, content_start + band)
            x_start = jersey_strip if i == 0 else max(jersey_strip, content_start - overlap)

        if i == 0:
            tile = img.crop((0, 0, x_end, height))
        else:
            strip = img.crop((0, 0, jersey_strip, height))
            innings = img.crop((x_start, 0, x_end, height))
            tile = Image.new("RGB", (strip.width + innings.width, height))
            tile.paste(strip, (0, 0))
            tile.paste(innings, (strip.width, 0))

        tiles.append(_resize_if_needed(tile))
        content_start = x_end - overlap
        if x_end >= width:
            break
    return tiles


def _vertical_tiles(img: Image.Image) -> List[Image.Image]:
    width, height = img.size
    num_tiles = 2 if height < 1400 else 3
    overlap = max(24, int(height * OVERLAP_RATIO))
    band = (height + overlap * (num_tiles - 1)) // num_tiles

    tiles: List[Image.Image] = []
    y = 0
    for _ in range(num_tiles):
        y_end = min(height, y + band)
        tiles.append(_resize_if_needed(img.crop((0, y, width, y_end))))
        if y_end >= height:
            break
        y = y_end - overlap
    return tiles


def _resize_if_needed(img: Image.Image) -> Image.Image:
    width, height = img.size
    long_edge = max(width, height)
    pixels = width * height
    scale = 1.0
    if long_edge > MAX_LONG_EDGE:
        scale = min(scale, MAX_LONG_EDGE / long_edge)
    if pixels * scale * scale > MAX_PIXELS:
        scale = min(scale, (MAX_PIXELS / pixels) ** 0.5)
    if scale >= 1.0:
        return img
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _encode_jpeg(img: Image.Image) -> Tuple[bytes, str]:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue(), "image/jpeg"
