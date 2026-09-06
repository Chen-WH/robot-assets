#!/usr/bin/env python3
"""Generate the 100 mm tag36h11 ID 10 used on the D435i mount."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


FULL_SIZE_MM = 100.0
TAG_SIZE_MM = 80.0
MODULES = 10
MM_TO_PT = 72.0 / 25.4


def mm(value: float) -> float:
    return value * MM_TO_PT


def load_grid(source: Path) -> list[list[bool]]:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        if rgba.size != (MODULES, MODULES):
            raise ValueError(f"Expected a 10x10 official tag image, got {rgba.size}")

        grid = []
        for y in range(MODULES):
            row = []
            for x in range(MODULES):
                red, green, blue, alpha = rgba.getpixel((x, y))
                if alpha != 255 or (red, green, blue) not in ((0, 0, 0), (255, 255, 255)):
                    raise ValueError("Source tag must contain only opaque black and white pixels")
                row.append(red == 0)
            grid.append(row)

    if any(grid[0]) or any(grid[-1]) or any(row[0] or row[-1] for row in grid):
        raise ValueError("The official one-module white border is missing")
    return grid


def write_svg(path: Path, grid: list[list[bool]]) -> None:
    cells = []
    for y, row in enumerate(grid):
        for x, is_black in enumerate(row):
            if is_black:
                cells.append(f'    <rect x="{x}" y="{y}" width="1" height="1"/>')

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
            'viewBox="0 0 10 10" shape-rendering="crispEdges">'
        ),
        '  <rect width="10" height="10" fill="white"/>',
        '  <g fill="black">',
        *cells,
        '  </g>',
        '</svg>',
        '',
    ]
    path.write_text("\n".join(svg), encoding="ascii")


def write_png(path: Path, grid: list[list[bool]]) -> None:
    module_px = 200
    source = Image.new("1", (MODULES, MODULES), color=1)
    for y, row in enumerate(grid):
        for x, is_black in enumerate(row):
            if is_black:
                source.putpixel((x, y), 0)
    output = source.resize(
        (MODULES * module_px, MODULES * module_px),
        resample=Image.NEAREST,
    )
    output.save(path, dpi=(508, 508))


def draw_tag(pdf: canvas.Canvas, grid: list[list[bool]], x: float, y: float) -> None:
    size = mm(FULL_SIZE_MM)
    module = size / MODULES
    pdf.setFillColor(white)
    pdf.rect(x, y, size, size, stroke=0, fill=1)
    pdf.setFillColor(black)
    for row, values in enumerate(grid):
        for col, is_black in enumerate(values):
            if is_black:
                pdf.rect(
                    x + col * module,
                    y + (MODULES - 1 - row) * module,
                    module,
                    module,
                    stroke=0,
                    fill=1,
                )


def draw_crop_marks(pdf: canvas.Canvas, x: float, y: float) -> None:
    size = mm(FULL_SIZE_MM)
    offset = mm(1.0)
    length = mm(4.0)
    pdf.setStrokeColor(Color(0.55, 0.55, 0.55))
    pdf.setLineWidth(0.25)
    for cx, cy, sx, sy in (
        (x, y, -1, -1),
        (x + size, y, 1, -1),
        (x, y + size, -1, 1),
        (x + size, y + size, 1, 1),
    ):
        pdf.line(cx + sx * offset, cy, cx + sx * (offset + length), cy)
        pdf.line(cx, cy + sy * offset, cx, cy + sy * (offset + length))


def write_pdf(path: Path, grid: list[list[bool]]) -> None:
    page_width, page_height = A4
    size = mm(FULL_SIZE_MM)
    x = (page_width - size) / 2.0
    y = (page_height - size) / 2.0

    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    pdf.setTitle("D435i mount AprilTag tag36h11 ID 10")
    pdf.setAuthor("robot-assets")
    pdf.setSubject("100 mm full label with 80 mm detector tag size")
    pdf.setFillColor(black)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(page_width / 2.0, page_height - mm(18.0), "D435i mount | tag36h11 | ID 10")
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(
        page_width / 2.0,
        page_height - mm(24.0),
        "Full label: 100 mm | detector tag size: 80 mm | print at 100% / Actual size",
    )
    draw_tag(pdf, grid, x, y)
    draw_crop_marks(pdf, x, y)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(
        page_width / 2.0,
        y - mm(8.0),
        "Cut at the white square boundary; gray crop marks stay on the scrap.",
    )
    pdf.showPage()
    pdf.save()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    grid = load_grid(args.source)
    stem = "apriltag_tag36h11_id10_full100mm_tag80mm"
    write_svg(args.output_dir / f"{stem}.svg", grid)
    write_png(args.output_dir / f"{stem}_2000px.png", grid)
    write_pdf(args.output_dir / f"{stem}_A4.pdf", grid)
    (args.output_dir / f"{stem}.yaml").write_text(
        "family: tag36h11\n"
        "id: 10\n"
        "full_label_size_m: 0.1\n"
        "detector_tag_size_m: 0.08\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
