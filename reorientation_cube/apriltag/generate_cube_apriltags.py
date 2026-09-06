#!/usr/bin/env python3
"""Generate print-ready AprilTag 3 tag36h11 labels for cube faces."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


MM_TO_PT = 72.0 / 25.4
MODULES = 10
DETECTION_MODULES = 8


@dataclass(frozen=True)
class CubeSpec:
    name: str
    edge_mm: float

    @property
    def tag_size_mm(self) -> float:
        return self.edge_mm * DETECTION_MODULES / MODULES


CUBES = (
    CubeSpec("cube_50mm", 50.0),
    CubeSpec("cube_60mm", 60.0),
    CubeSpec("cube_70mm", 70.0),
)

# Face -> (key, PDF label, tag id, how to orient the printed label).
#
# **LEFT and RIGHT here are the cube's own, not the viewer's.**  With the frame
# +X right, +Y front, +Z top, the RIGHT face (+X) is the one on your LEFT while
# you look at the FRONT face, the same way a person facing you has their right
# hand on your left.  The labels say so on the printed sheet because getting this
# backwards is not hypothetical: it is what happened here.
#
# Updated 2026-09-04 to the layout actually attached to the physical pine cubes,
# previously recorded separately in `physical_cube_tag_layout.yaml`.  The original
# print plan put ID 0 on the front and ID 4 on top; the operator stuck them with
# ID 0 on top and ID 1 on the front, and the physical cube is the thing trackers
# have to agree with.  Keeping two mappings alive cost a 90 degree error waiting
# to happen -- a translation-only pipeline never notices it, an orientation
# pipeline is wrecked by it -- so the generator now emits the physical layout and
# there is one mapping instead of two.
#
# Corrected again 2026-09-05: IDs 2 and 4 were the wrong way round.  The record's
# unfolding, drawn facing the FRONT face, puts ID 2 to the viewer's right, and the
# viewer's right is -X = the LEFT face -- so ID 2 is on LEFT (-X) and ID 4 on
# RIGHT (+X).  The `recorded_edge_adjacencies` in `physical_cube_tag_layout.yaml`
# had said the same thing all along (read as each tag image's own left/right they
# give the cycle 1->2->3->4 along image-right, where the old table gave
# 1->4->3->2), but they were set aside as ambiguous and nothing acted on them.
# What forced it was the tracker: with two faces of the real cube in view at once,
# IDs 3 and 4 both decoded on 696/696 frames and their pose votes differed by
# 179.2 deg, sd 0.02, about the cube z axis -- exactly a swap of two opposite side
# faces.  Re-audited after the swap: every observed pair agrees within 1.3 deg
# (`armhand-mjlab/scripts/deploy/faceaudit.py`, 2695 frames).
#
# The in-plane orientations were already identical between the two plans for every
# face position; only the id-to-face assignment moved.
FACES = (
    ("top", "TOP +Z", 0, "top edge toward BACK face"),
    ("front", "FRONT +Y", 1, "top edge toward TOP face"),
    ("right", "RIGHT +X", 4, "top edge toward TOP face"),
    ("back", "BACK -Y", 3, "top edge toward TOP face"),
    ("left", "LEFT -X", 2, "top edge toward TOP face"),
    ("bottom", "BOTTOM -Z", 5, "top edge toward FRONT face"),
)


def mm(value: float) -> float:
    return value * MM_TO_PT


def load_tag_grid(source_dir: Path, tag_id: int) -> list[list[bool]]:
    source = source_dir / f"tag36_11_{tag_id:05d}.png"
    if not source.is_file():
        raise FileNotFoundError(f"Missing official tag image: {source}")

    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        if rgba.size != (MODULES, MODULES):
            raise ValueError(f"Expected a 10x10 tag image, got {rgba.size}: {source}")
        pixels = rgba.load()
        grid = []
        for y in range(MODULES):
            row = []
            for x in range(MODULES):
                red, green, blue, alpha = pixels[x, y]
                if alpha != 255 or (red, green, blue) not in ((0, 0, 0), (255, 255, 255)):
                    raise ValueError(f"Tag image is not opaque black/white: {source}")
                row.append(red == 0)
            grid.append(row)

    if any(grid[0]) or any(grid[-1]) or any(row[0] or row[-1] for row in grid):
        raise ValueError(f"Official white border is missing: {source}")
    return grid


def write_svg(path: Path, grid: list[list[bool]], edge_mm: float) -> None:
    black_cells = []
    for y, row in enumerate(grid):
        for x, is_black in enumerate(row):
            if is_black:
                black_cells.append(f'  <rect x="{x}" y="{y}" width="1" height="1"/>')

    content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{edge_mm:g}mm" '
            f'height="{edge_mm:g}mm" viewBox="0 0 {MODULES} {MODULES}" '
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


def draw_tag(
    pdf: canvas.Canvas,
    grid: list[list[bool]],
    x_pt: float,
    y_pt: float,
    edge_pt: float,
) -> None:
    module_pt = edge_pt / MODULES
    pdf.setFillColor(white)
    pdf.rect(x_pt, y_pt, edge_pt, edge_pt, stroke=0, fill=1)
    pdf.setFillColor(black)
    for row, values in enumerate(grid):
        for col, is_black in enumerate(values):
            if is_black:
                pdf.rect(
                    x_pt + col * module_pt,
                    y_pt + (MODULES - 1 - row) * module_pt,
                    module_pt,
                    module_pt,
                    stroke=0,
                    fill=1,
                )


def draw_crop_marks(pdf: canvas.Canvas, x: float, y: float, size: float) -> None:
    offset = mm(1.0)
    length = mm(3.0)
    pdf.setStrokeColor(Color(0.55, 0.55, 0.55))
    pdf.setLineWidth(0.25)

    corners = (
        (x, y, -1, -1),
        (x + size, y, 1, -1),
        (x, y + size, -1, 1),
        (x + size, y + size, 1, 1),
    )
    for cx, cy, sx, sy in corners:
        pdf.line(cx + sx * offset, cy, cx + sx * (offset + length), cy)
        pdf.line(cx, cy + sy * offset, cx, cy + sy * (offset + length))


def page_positions(spec: CubeSpec) -> list[tuple[float, float]]:
    page_w, page_h = A4
    edge = mm(spec.edge_mm)

    if spec.edge_mm <= 60:
        cols, rows = 3, 2
        gap_x = mm(12.0 if spec.edge_mm == 50 else 4.0)
        gap_y = mm(14.0)
    else:
        cols, rows = 2, 3
        gap_x = mm(18.0)
        gap_y = mm(10.0)

    grid_w = cols * edge + (cols - 1) * gap_x
    grid_h = rows * edge + (rows - 1) * gap_y
    origin_x = (page_w - grid_w) / 2.0
    origin_y = (page_h - grid_h) / 2.0 - mm(5.0)

    positions = []
    for index in range(6):
        col = index % cols
        row = index // cols
        x = origin_x + col * (edge + gap_x)
        y = origin_y + (rows - 1 - row) * (edge + gap_y)
        positions.append((x, y))
    return positions


def draw_page_header(pdf: canvas.Canvas, spec: CubeSpec) -> None:
    page_w, page_h = A4
    title = (
        f"DexHand cube {spec.edge_mm:g} mm | tag36h11 | "
        f"full label {spec.edge_mm:g} mm | detector tag size {spec.tag_size_mm:g} mm"
    )
    font_name = "Helvetica-Bold"
    font_size = 10
    while stringWidth(title, font_name, font_size) > page_w - mm(16.0):
        font_size -= 0.5
    pdf.setFillColor(black)
    pdf.setFont(font_name, font_size)
    pdf.drawCentredString(page_w / 2.0, page_h - mm(12.0), title)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawCentredString(
        page_w / 2.0,
        page_h - mm(17.0),
        "Print at 100% / Actual size. Cut on the tag's white square boundary; crop marks stay on scrap.",
    )
    pdf.drawCentredString(
        page_w / 2.0,
        page_h - mm(21.0),
        "Face names are the CUBE's own axes: RIGHT +X is the face on YOUR LEFT "
        "while you look at FRONT +Y.",
    )


def write_print_pdf(
    output: Path,
    grids: dict[int, list[list[bool]]],
) -> None:
    pdf = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
    pdf.setTitle("DexHand in-hand manipulation cube AprilTags")
    pdf.setAuthor("robot-assets")
    pdf.setSubject("Print-ready AprilTag 3 tag36h11 labels for 50, 60, and 70 mm cubes")

    for spec in CUBES:
        draw_page_header(pdf, spec)
        edge = mm(spec.edge_mm)
        for (face_key, face_label, tag_id, _), (x, y) in zip(FACES, page_positions(spec)):
            draw_tag(pdf, grids[tag_id], x, y, edge)
            draw_crop_marks(pdf, x, y, edge)
            pdf.setFillColor(black)
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawCentredString(x + edge / 2.0, y - mm(3.5), f"{face_label} | ID {tag_id:02d}")
        pdf.showPage()

    pdf.save()


def write_mapping(path: Path) -> None:
    lines = [
        "family: tag36h11",
        "layout: AprilTag 3 official 10x10 image",
        "print_scale: 1.0",
        "size_definition: detection corners at the 8x8 black-square boundary",
        "ids_reused_across_cube_sizes: true",
        "layout_authority: physical attachment on the pine cubes; matches "
        "physical_cube_tag_layout.yaml",
        "simultaneous_multi_size_identification_by_id: false",
        "cubes:",
    ]
    for spec in CUBES:
        lines.extend(
            (
                f"  {spec.name}:",
                f"    edge_size_m: {spec.edge_mm / 1000.0:g}",
                f"    full_label_size_m: {spec.edge_mm / 1000.0:g}",
                f"    detector_tag_size_m: {spec.tag_size_mm / 1000.0:g}",
                "    faces:",
            )
        )
        for face_key, _, tag_id, orientation in FACES:
            lines.extend(
                (
                    f"      {face_key}:",
                    f"        id: {tag_id}",
                    f"        orientation: {orientation}",
                )
            )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing official tag36_11_XXXXX.png files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "generated",
        help="Output directory (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    svg_dir = args.output_dir / "svg"
    svg_dir.mkdir(exist_ok=True)
    for old_svg in svg_dir.glob("cube_*_id*_*.svg"):
        old_svg.unlink()

    ids = sorted({face[2] for face in FACES})
    grids = {tag_id: load_tag_grid(args.source_dir, tag_id) for tag_id in ids}

    for spec in CUBES:
        for face_key, _, tag_id, _ in FACES:
            svg_path = svg_dir / f"{spec.name}_{face_key}_id{tag_id:02d}_{spec.edge_mm:g}mm.svg"
            write_svg(svg_path, grids[tag_id], spec.edge_mm)

    write_print_pdf(args.output_dir / "dexhand_cube_tag36h11_A4.pdf", grids)
    write_mapping(args.output_dir / "cube_tag_mapping.yaml")

    print(f"Generated {len(CUBES) * len(FACES)} SVG files in {svg_dir}")
    print(args.output_dir / "dexhand_cube_tag36h11_A4.pdf")
    print(args.output_dir / "cube_tag_mapping.yaml")


if __name__ == "__main__":
    main()
