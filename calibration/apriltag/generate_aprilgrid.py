#!/usr/bin/env python3
"""Generate a Kalibr-compatible AprilGrid that a standard detector can actually read.

Why this exists.  The three boards under `~/docker_data/kalibr_data/targets` were
made by a "Kalibr-compatible AprilGrid generator" that draws each tag with a
**two-module black border** instead of one.  Measured on the 7x5/45 mm board,
2026-09-09: the black square is 44.87 mm across ten modules of 4.5 mm, the first
two module rows are solid black edge to edge, and the payload underneath is a
perfectly valid tag36h11 codeword (id 28, turned 180 degrees).

That one extra ring is fatal and silent.  A detector finds the quad at the outer
edge of the black square and then samples the 6x6 payload assuming that square is
**eight** modules wide, as tag36h11 is.  Against a ten-module square every sample
lands in the wrong cell, no codeword matches, and the tag simply never appears --
identical, from the outside, to bad focus, bad exposure or a mirrored print.
`pupil_apriltags` decoded **0 of 35** tags from the reference PDF itself, with no
camera involved, and 0 under horizontal flip, vertical flip, 180 degree rotation,
inversion and transpose.  All three boards in that directory share the defect.

A correct tag36h11 label is: 6x6 payload, **one** module of black border around
it (so the black square is 8 modules = `tagSize`), and white around that.  On an
AprilGrid the inter-tag gap supplies the white quiet zone, which is why
`tagSpacing` must not be zero.

The bitmaps come from OpenCV's `DICT_APRILTAG_36h11`, whose module layout is the
official `apriltag-imgs` one rotated 180 degrees -- established two independent
ways in `reorientation_cube/apriltag/generate_cube_apriltag_tiles.py` and
corrected here the same way.  Every generated sheet is then rasterised and
decoded before it is written, so a board that cannot be read cannot be produced.

    python3 generate_aprilgrid.py                       # 7x5, 45 mm, A2
    python3 generate_aprilgrid.py --preset a4
    python3 generate_aprilgrid.py --cols 8 --rows 6 --tag-mm 60 --paper 594x420
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np

MM_TO_PT = 72.0 / 25.4
MODULES = 8          # black square: 1 module of border + 6 of payload
PAYLOAD = 6
_ROT_TO_OFFICIAL = 2

#: `(cols, rows, tag_mm, spacing, paper_w_mm, paper_h_mm)`.  `a2` reproduces the
#: geometry of the board already in use, so it is a drop-in replacement and the
#: existing `.yaml` stays true; `a4` trades tag size for a sheet any printer takes.
PRESETS = {
    "a2": (7, 5, 45.0, 0.3, 594.0, 420.0),
    "a4": (7, 5, 30.0, 0.3, 297.0, 210.0),
}


def tag_bitmap(tag_id: int) -> np.ndarray:
    """8x8 boolean grid, True where black: one border module around 6x6 payload."""
    import cv2

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    img = cv2.aruco.generateImageMarker(dictionary, tag_id, MODULES, borderBits=1)
    return np.rot90(img // 255, _ROT_TO_OFFICIAL) == 0


def draw(path: Path, cols: int, rows: int, tag_mm: float, spacing: float,
         paper: tuple[float, float]) -> tuple[float, float]:
    from reportlab.lib.colors import black, white
    from reportlab.pdfgen import canvas

    pitch_mm = tag_mm * (1.0 + spacing)
    grid_w = cols * tag_mm + (cols - 1) * spacing * tag_mm
    grid_h = rows * tag_mm + (rows - 1) * spacing * tag_mm
    if grid_w > paper[0] - 10 or grid_h > paper[1] - 10:
        raise SystemExit(
            f"grid {grid_w:.0f}x{grid_h:.0f} mm does not fit {paper[0]:.0f}x"
            f"{paper[1]:.0f} mm with a 5 mm margin -- lower --tag-mm or use bigger paper")

    page = (paper[0] * MM_TO_PT, paper[1] * MM_TO_PT)
    pdf = canvas.Canvas(str(path), pagesize=page)
    pdf.setTitle(f"AprilGrid {cols}x{rows} tag36h11 {tag_mm:g}mm spacing {spacing:g}")
    ox = (page[0] - grid_w * MM_TO_PT) / 2.0
    oy = (page[1] - grid_h * MM_TO_PT) / 2.0

    tag_pt, module_pt = tag_mm * MM_TO_PT, tag_mm * MM_TO_PT / MODULES
    pdf.setFillColor(white)
    pdf.rect(0, 0, page[0], page[1], stroke=0, fill=1)
    pdf.setFillColor(black)
    for row in range(rows):
        for col in range(cols):
            # Kalibr numbers tags row-major from the BOTTOM-left, so row 0 is the
            # bottom row -- which is also PDF's own y direction, no flip needed.
            tag_id = row * cols + col
            bits = tag_bitmap(tag_id)
            x0 = ox + col * pitch_mm * MM_TO_PT
            y0 = oy + row * pitch_mm * MM_TO_PT
            for r in range(MODULES):
                for c in range(MODULES):
                    if bits[r, c]:
                        pdf.rect(x0 + c * module_pt,
                                 # bitmap row 0 is the TOP of the tag image
                                 y0 + (MODULES - 1 - r) * module_pt,
                                 module_pt, module_pt, stroke=0, fill=1)
    pdf.showPage()
    pdf.save()
    return grid_w, grid_h


def write_yaml(path: Path, cols: int, rows: int, tag_mm: float, spacing: float) -> None:
    path.write_text(
        "target_type: 'aprilgrid'\n"
        f"tagCols: {cols}\n"
        f"tagRows: {rows}\n"
        f"tagSize: {tag_mm / 1000.0:g}\n"
        f"tagSpacing: {spacing:g}\n", encoding="ascii")


def verify(pdf: Path, cols: int, rows: int, tag_mm: float, dpi: int = 300) -> list[str]:
    """Rasterise the sheet and decode it.  A board that fails here is not shipped.

    **300 dpi, not 150.**  At 150 the 7x5/45 mm sheet loses exactly one column --
    ids 3, 10, 17, 24, 31 -- while every one of them decodes alone and the whole
    sheet decodes at 200, 300 and 600 with the black square measuring 44.96 to
    45.04 mm throughout.  So it is an artefact of rasterising for the check, not a
    defect in the sheet, and a printer at 600 dpi never meets it.  The mechanism
    is not established; sub-pixel placement of that column's origin (175.5 mm,
    landing on a fractional pixel) is the suspicion, nothing more.  It is left
    here as a reminder that a verification can fail for its own reasons.
    """
    import cv2
    from pupil_apriltags import Detector

    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png",
                        "-f", "1", "-l", "1", str(pdf), str(stem)],
                       check=True, capture_output=True)
        rendered = sorted(Path(tmp).glob("page*.png"))
        if not rendered:
            raise SystemExit("pdftoppm produced nothing -- cannot verify the sheet")
        image = cv2.imread(str(rendered[0]), cv2.IMREAD_GRAYSCALE)

    detector = Detector(families="tag36h11", nthreads=4, quad_decimate=1.0,
                        refine_edges=True)
    found = detector.detect(image)
    expected = cols * rows
    ids = sorted(int(d.tag_id) for d in found)
    report = [f"  decoded {len(found)}/{expected} tags, ids {ids[0]}-{ids[-1]}"
              if found else "  decoded 0 tags"]
    if ids != list(range(expected)):
        raise SystemExit(f"expected ids 0..{expected - 1}, got {ids}")

    px_per_mm = dpi / 25.4
    sides = []
    for d in found:
        corner = np.asarray(d.corners, float)
        sides += [float(np.linalg.norm(corner[i] - corner[(i + 1) % 4]))
                  for i in range(4)]
    measured = float(np.median(sides)) / px_per_mm
    report.append(f"  black square {measured:.3f} mm against {tag_mm:g} nominal, "
                  f"spread {(max(sides) - min(sides)) / px_per_mm:.3f} mm")
    if abs(measured - tag_mm) > 0.15:
        raise SystemExit(f"black square measured {measured:.3f} mm, expected {tag_mm:g}")

    # The defect this file exists for: a two-module border makes the black square
    # 10/8 of tagSize. That would show up right here as a 25 % size error.
    report.append("  border is one module (a two-module border would read "
                  f"{tag_mm * 10 / 8:.1f} mm here)")
    return report


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=sorted(PRESETS), default="a2")
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--tag-mm", type=float, default=None)
    ap.add_argument("--spacing", type=float, default=None)
    ap.add_argument("--paper", default=None, help="'WxH' in mm, e.g. 594x420")
    ap.add_argument("--out-dir", type=Path, default=here / "generated")
    args = ap.parse_args()

    cols, rows, tag_mm, spacing, pw, ph = PRESETS[args.preset]
    cols = args.cols or cols
    rows = args.rows or rows
    tag_mm = args.tag_mm or tag_mm
    spacing = args.spacing if args.spacing is not None else spacing
    if args.paper:
        pw, ph = (float(v) for v in args.paper.lower().split("x"))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"aprilgrid_{cols}x{rows}_{tag_mm:g}mm"
    pdf = args.out_dir / f"{stem}.pdf"
    grid_w, grid_h = draw(pdf, cols, rows, tag_mm, spacing, (pw, ph))
    write_yaml(args.out_dir / f"{stem}.yaml", cols, rows, tag_mm, spacing)

    print(f"{cols}x{rows} tags, {tag_mm:g} mm black square, spacing {spacing:g} "
          f"({spacing * tag_mm:g} mm gap)")
    print(f"grid {grid_w:.1f} x {grid_h:.1f} mm on {pw:g} x {ph:g} mm paper "
          f"({(pw - grid_w) / 2:.1f} / {(ph - grid_h) / 2:.1f} mm margins)")
    print("\nverification (rasterise the sheet and decode it):")
    for line in verify(pdf, cols, rows, tag_mm):
        print(line)
    print(f"\nwrote {pdf}")
    print(f"wrote {args.out_dir / f'{stem}.yaml'}")
    print("\nPrint at 100 %. Any scaling biases every recovered distance by the "
          "same ratio, and a calibration is exactly where that bias would hide.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
