#!/usr/bin/env python3
"""Generate print-ready tag36h11 ID 6/7 labels for the D60 cylinder."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


MM_TO_PT = 72.0 / 25.4
MODULES = 10
DETECTION_MODULES = 8
LABEL_SIZE_MM = 36.0
TAGS = (("top", 6), ("bottom", 7))

# Black=1 payloads from OpenCV 4.12 DICT_APRILTAG_36h11 generateImageMarker(8).
DETECTION_GRIDS = {
    6: (
        "11111111",
        "10101111",
        "11011111",
        "10100011",
        "10110101",
        "11001011",
        "10111111",
        "11111111",
    ),
    7: (
        "11111111",
        "11101011",
        "10001111",
        "11000101",
        "11101011",
        "11001111",
        "11101111",
        "11111111",
    ),
}


def mm(value: float) -> float:
    return value * MM_TO_PT


def full_grid(tag_id: int) -> tuple[str, ...]:
    detection = DETECTION_GRIDS[tag_id]
    return ("0" * MODULES,) + tuple(f"0{row}0" for row in detection) + ("0" * MODULES,)


def write_svg(path: Path, tag_id: int) -> None:
    black_cells = []
    for y, row in enumerate(full_grid(tag_id)):
        for x, value in enumerate(row):
            if value == "1":
                black_cells.append(f'  <rect x="{x}" y="{y}" width="1" height="1"/>')
    content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{LABEL_SIZE_MM:g}mm" '
            f'height="{LABEL_SIZE_MM:g}mm" viewBox="0 0 {MODULES} {MODULES}" '
            'shape-rendering="crispEdges">'
        ),
        f'  <rect width="{MODULES}" height="{MODULES}" fill="white"/>',
        '  <g fill="black">',
        *black_cells,
        '  </g>',
        '</svg>',
        '',
    ]
    path.write_text("\n".join(content), encoding="ascii")


def draw_tag(pdf: canvas.Canvas, tag_id: int, x: float, y: float, size: float) -> None:
    module = size / MODULES
    pdf.setFillColor(white)
    pdf.rect(x, y, size, size, stroke=0, fill=1)
    pdf.setFillColor(black)
    for row, values in enumerate(full_grid(tag_id)):
        for col, value in enumerate(values):
            if value == "1":
                pdf.rect(
                    x + col * module,
                    y + (MODULES - 1 - row) * module,
                    module,
                    module,
                    stroke=0,
                    fill=1,
                )


def draw_crop_marks(pdf: canvas.Canvas, x: float, y: float, size: float) -> None:
    offset = mm(1.0)
    length = mm(3.0)
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


def write_pdf(path: Path) -> None:
    page_w, page_h = A4
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    pdf.setTitle("DexHand D60 cylinder AprilTags")
    pdf.setAuthor("robot-assets")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(page_w / 2, page_h - mm(18), "D60 x H80 cylinder | tag36h11")
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(
        page_w / 2,
        page_h - mm(24),
        "Print at 100% / Actual size | full label 36 mm | detector tagSize 28.8 mm",
    )
    size = mm(LABEL_SIZE_MM)
    gap = mm(30)
    origin_x = (page_w - 2 * size - gap) / 2
    y = (page_h - size) / 2
    for index, (face, tag_id) in enumerate(TAGS):
        x = origin_x + index * (size + gap)
        draw_tag(pdf, tag_id, x, y, size)
        draw_crop_marks(pdf, x, y, size)
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(x + size / 2, y - mm(5), f"{face.upper()} | ID {tag_id}")
    pdf.showPage()
    pdf.save()


def write_mapping(path: Path) -> None:
    path.write_text(
        "\n".join(
            (
                "family: tag36h11",
                "payload_source: OpenCV 4.12 DICT_APRILTAG_36h11 generateImageMarker",
                "layout: 10x10 complete image with one-module white border",
                "print_scale: 1.0",
                "complete_label_size_m: 0.036",
                "detector_tag_size_m: 0.0288",
                "proposed_faces:",
                "  top:",
                "    id: 6",
                "  bottom:",
                "    id: 7",
                "",
            )
        ),
        encoding="ascii",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "generated",
    )
    args = parser.parse_args()
    svg_dir = args.output_dir / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    for face, tag_id in TAGS:
        write_svg(svg_dir / f"cylinder_d60_h80_{face}_id{tag_id:02d}_36mm.svg", tag_id)
    write_pdf(args.output_dir / "dexhand_cylinder_d60_h80_tag36h11_A4.pdf")
    write_mapping(args.output_dir / "cylinder_tag_mapping.yaml")
    print(args.output_dir)


if __name__ == "__main__":
    main()
