#!/usr/bin/env python3
"""Generate a print-ready wrap-around net carrying 2x2 tag36h11 tiles per face.

Why tiles.  With one full-face tag, a finger lying across any part of a face's
border destroys the whole face: AprilTag needs four unbroken border edges to fit
a quadrilateral, so partial occlusion is total loss, not degradation.  Measured
on hardware 2026-09-09 over 337 blind frames, 57-69 % of them had no cube face
decode at all while the wrist tag decoded at full margin in the very same image.
Four independent tiles a face mean a finger takes out one tile, not the face.

Why a wrap-around net rather than six labels.  Every face-to-id error this
project has had -- the 2/4 exchange of 2026-09-05, and the 90 degree layout
before it -- came from a human filling in a degree of freedom: which id goes on
which face, and which way up.  A single net fixes the in-face tile positions,
the face-to-id assignment and the edge adjacencies at print time, leaving the
operator none of them.

What that leaves.  Three global failure modes replace the per-face ones:

*   **Mirrored** (wrapped inside out).  Self-announcing: a mirrored tag36h11
    contains no legal codeword and simply fails to decode.
*   **Rotated as a whole** by 90 or 180 degrees about some axis.  The six ids and
    the in-face layout are unchanged, so no self-consistency check can see it.
    Only `faceaudit.py` against the physical cube can.
*   **The net itself drawn with the wrong handedness.**  This is what produced the
    2/4 exchange: the record's unfolding was drawn from the observer's side, and
    reading "the cell to the right of ID 1" as +X put two opposite faces the
    wrong way round.

The third is the one a generator can eliminate, and this file does, by refusing
to reason about the unfolding at all.  `_fold()` walks the net's adjacency from a
root face, rotating 90 degrees about each shared edge, and reports the outward
normal and printed-up direction each cell actually lands on once folded.  The
required orientation comes from `FACE_FRAMES`, which is `deploy/cube.py`'s
`PHYSICAL_LAYOUT` -- the table the tracker already agrees with.  Any cell whose
folded up-direction disagrees is rotated in the net until it does, and the run
fails loudly if no rotation works.  The layout is derived, not drawn.

Tag images.  The official `apriltag-imgs` set is not on this machine beyond id 0,
so bitmaps come from OpenCV's `DICT_APRILTAG_36h11`.  **That dictionary's module
layout is the official one rotated 180 degrees**, which would have put every tile
frame half a turn out with nothing to announce it.  Corrected here by
`_ROT_TO_OFFICIAL`, established two independent ways on 2026-09-09: the corrected
bitmap for id 0 is bit-for-bit identical to the one official image available, and
decoding all 24 corrected bitmaps gives first-corner azimuth 135.070 deg with
**zero** spread, the same value the official id 0 decodes to.  A per-id
difference in convention would have scattered that across 90 degree steps.

    python3 generate_cube_apriltag_tiles.py
    python3 generate_cube_apriltag_tiles.py --edge-mm 60 --out-dir generated
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

MM_TO_PT = 72.0 / 25.4
MODULES = 10
DETECTION_MODULES = 8

#: Turns of `np.rot90` carrying an OpenCV `DICT_APRILTAG_36h11` bitmap onto the
#: official `apriltag-imgs` layout.  Measured, see the module docstring.
_ROT_TO_OFFICIAL = 2

#: Outward normal and printed-up axis per face, in the cube frame
#: (+X right, +Y front, +Z top).  **This is `deploy/cube.py`'s `PHYSICAL_LAYOUT`
#: with the tag ids removed** -- the same table the tracker fuses against, so the
#: printed cube and the code cannot drift apart.  RIGHT (+X) is the cube's own
#: right, which is on your LEFT while you face the FRONT face.
FACE_FRAMES = {
    "top":    ("+Z", "-Y"),
    "front":  ("+Y", "+Z"),
    "right":  ("+X", "+Z"),
    "back":   ("-Y", "+Z"),
    "left":   ("-X", "+Z"),
    "bottom": ("-Z", "+Y"),
}

AXES = {
    "+X": np.array([1.0, 0.0, 0.0]), "-X": np.array([-1.0, 0.0, 0.0]),
    "+Y": np.array([0.0, 1.0, 0.0]), "-Y": np.array([0.0, -1.0, 0.0]),
    "+Z": np.array([0.0, 0.0, 1.0]), "-Z": np.array([0.0, 0.0, -1.0]),
}

#: The 1-4-1 cross, as `(column, row)` in a 3-wide by 4-tall grid with row 0 at
#: the TOP of the sheet.  Bounding box 3 x 4 cells = 180 x 240 mm at a 60 mm
#: edge, which fits A4 portrait (210 x 297) with 15 mm of side margin and 28 mm
#: top and bottom.  **Only this orientation fits**: laid on its side the 240 mm
#: runs past A4's 210 mm width.
#:
#: **LEFT sits to the paper-right of FRONT, and RIGHT to the paper-left.**  That
#: is not a typo: the cube's own RIGHT (+X) is on the reader's LEFT while the
#: reader faces the FRONT face.  Writing it the intuitive way round was the first
#: thing tried here, and `solve_spins` rejected it -- "cell for right folds to
#: normal [-1, 0, 0], expected +X" -- which is the same exchange of two opposite
#: side faces that took two weeks to find on hardware in 2026-09 (docs/04 no. 19).
#: The fold check costs nothing and does not care what the layout looks like.
NET_CELLS = {
    "top":    (1, 0),
    "front":  (1, 1),
    "right":  (0, 1),
    "left":   (2, 1),
    "bottom": (1, 2),
    "back":   (1, 3),
}

def tile_cells(grid: int):
    """Tile slots within a face, in that face's own printed frame, reading order.

    `(name, column, row)` with row 0 at the top.  A 2x2 keeps the historical
    TL/TR/BL/BR names so the sheet printed on 2026-09-09 stays readable against
    its mapping file; larger grids are named `r{row}c{col}`.
    """
    if grid == 2:
        return (("TL", 0, 0), ("TR", 1, 0), ("BL", 0, 1), ("BR", 1, 1))
    return tuple((f"r{r}c{c}", c, r) for r in range(grid) for c in range(grid))

#: Face order for handing out tile ids.  Matches `generate_cube_apriltags.py`'s
#: `FACES` so the two generators tell the same story.
FACE_ORDER = ("top", "front", "right", "back", "left", "bottom")

#: Tile ids start here.  0-5 are the single-face tags this supersedes and 10 is
#: the wrist tag, so 20-43 collides with neither -- and the leading digit alone
#: tells an operator which scheme a decoded id belongs to.
FIRST_TILE_ID = 20


def mm(value: float) -> float:
    return value * MM_TO_PT


# --------------------------------------------------------------------------- #
# Folding
# --------------------------------------------------------------------------- #

def _rot(axis: int, turns: int) -> np.ndarray:
    """Rotation by `turns` * 90 degrees about local axis 0, 1 or 2."""
    c, s = int(np.cos(np.pi / 2 * turns)), int(np.sin(np.pi / 2 * turns))
    R = np.eye(3, dtype=int)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    R[i, i], R[i, j], R[j, i], R[j, j] = c, -s, s, c
    return R


def _fold(cells: dict[str, tuple[int, int]], spins: dict[str, int]) -> dict[str, np.ndarray]:
    """Fold the net and report each face's orientation once folded.

    Returns `{face: M}` where `M`'s columns are the face's paper-local right, up
    and outward directions expressed in the cube frame.  So `M[:, 2]` is the
    outward normal and `M[:, 1]` the printed-up direction -- exactly the pair
    `FACE_FRAMES` constrains.

    The walk starts at the root with an arbitrary but fixed placement and folds
    every neighbour away from the reader, which is what happens when a net
    printed face-out is wrapped around a cube.  Crossing a shared edge rotates
    the neighbour 90 degrees about that edge:

    *   right neighbour -- about local up, carrying `out` onto `right`
    *   left  neighbour -- about local up, the other way
    *   below neighbour -- about local right, carrying `out` onto `-up`
    *   above neighbour -- about local right, the other way

    `spins[face]` turns a cell's printed content in its own plane before it is
    folded, which is how a face whose folded up-direction is wrong gets fixed.
    """
    by_cell = {cell: face for face, cell in cells.items()}
    root = "front"
    # Root placement: printed side out, paper-right along the cube's -X (because
    # +X is the cube's own right, which faces the reader's left), paper-up along
    # +Z, and the outward normal +Y toward the reader.
    M = {root: np.array([AXES["-X"], AXES["+Z"], AXES["+Y"]], dtype=int).T}
    # (paper dx, paper dy, local rotation axis, turns); dy grows downward.
    steps = ((+1, 0, 1, +1), (-1, 0, 1, -1), (0, +1, 0, +1), (0, -1, 0, -1))

    pending = [root]
    while pending:
        face = pending.pop()
        cx, cy = cells[face]
        for dx, dy, axis, turns in steps:
            neighbour = by_cell.get((cx + dx, cy + dy))
            if neighbour is None or neighbour in M:
                continue
            M[neighbour] = M[face] @ _rot(axis, turns)
            pending.append(neighbour)

    return {f: m @ _rot(2, spins.get(f, 0)) for f, m in M.items()}


def solve_spins(cells: dict[str, tuple[int, int]]) -> dict[str, int]:
    """In-plane turns per cell that make the folded net match `FACE_FRAMES`.

    Raises if the net cannot be made to agree, which is the check that the cell
    layout itself is sane: a cell holding the wrong face lands on the wrong
    normal, and no in-plane spin can repair a normal.
    """
    spins = {face: 0 for face in cells}
    folded = _fold(cells, spins)
    for face, (normal, up) in FACE_FRAMES.items():
        got_n = folded[face][:, 2]
        if not np.array_equal(got_n, AXES[normal].astype(int)):
            raise SystemExit(
                f"net cell for {face} folds to normal {got_n.tolist()}, "
                f"expected {normal} -- the cell layout is wrong, not the spin"
            )
        for turns in range(4):
            trial = folded[face] @ _rot(2, turns)
            if np.array_equal(trial[:, 1], AXES[up].astype(int)):
                spins[face] = turns
                break
        else:
            raise SystemExit(f"no in-plane rotation puts {face}'s up on {up}")
    return spins


def verify(cells, spins) -> list[str]:
    """Re-fold with the solved spins and confirm every face lands correctly."""
    folded = _fold(cells, spins)
    report = []
    for face in FACE_ORDER:
        normal, up = FACE_FRAMES[face]
        M = folded[face]
        ok = (np.array_equal(M[:, 2], AXES[normal].astype(int))
              and np.array_equal(M[:, 1], AXES[up].astype(int)))
        report.append(f"  {face:7s} cell {cells[face]} spin {spins[face]*90:3d} deg"
                      f"  -> normal {normal} up {up}   {'ok' if ok else 'FAILED'}")
        if not ok:
            raise SystemExit(f"fold verification failed for {face}")
    return report


# --------------------------------------------------------------------------- #
# Tag bitmaps
# --------------------------------------------------------------------------- #

def tile_bitmap(tag_id: int) -> np.ndarray:
    """10x10 boolean grid, True where a module is black, official convention."""
    import cv2

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    inner = cv2.aruco.generateImageMarker(dictionary, tag_id, DETECTION_MODULES,
                                          borderBits=1)
    inner = np.rot90(inner // 255, _ROT_TO_OFFICIAL)
    grid = np.ones((MODULES, MODULES), np.uint8)
    grid[1:-1, 1:-1] = inner
    return grid == 0


def check_bitmaps(ids) -> str:
    """Decode every generated bitmap and confirm id and in-plane azimuth.

    The azimuth must be identical across ids: `pupil_apriltags` reads the tag's
    orientation out of the code, so a per-id difference in the source layout
    shows up here as a 90 degree step, and nothing downstream would notice it.
    """
    from pupil_apriltags import Detector

    det = Detector(families="tag36h11", nthreads=4, quad_decimate=1.0,
                   refine_edges=True)
    azimuths = []
    for tag_id in ids:
        grid = tile_bitmap(tag_id).astype(np.uint8)
        image = np.pad(np.kron(1 - grid, np.ones((20, 20), np.uint8)) * 255, 60,
                       constant_values=255)
        found = det.detect(image)
        if len(found) != 1 or int(found[0].tag_id) != tag_id:
            raise SystemExit(f"tile {tag_id} did not decode back to itself")
        corners = np.asarray(found[0].corners, float)
        vector = corners[0] - corners.mean(0)
        azimuths.append(np.degrees(np.arctan2(vector[1], vector[0])))
    spread = float(np.max(azimuths) - np.min(azimuths))
    if spread > 1e-6:
        raise SystemExit(f"tile azimuth is not uniform across ids: {spread:.3f} deg")
    return (f"  {len(ids)} tiles decoded back to their own id; "
            f"azimuth {np.median(azimuths):.3f} deg, spread {spread:.1e}")


# --------------------------------------------------------------------------- #
# Layout and drawing
# --------------------------------------------------------------------------- #

def assign_tiles(grid: int) -> dict[str, list[tuple[str, int, int, int]]]:
    """`{face: [(corner, column, row, tag_id), ...]}`, ids from `FIRST_TILE_ID`."""
    out, next_id = {}, FIRST_TILE_ID
    for face in FACE_ORDER:
        entries = []
        for corner, col, row in tile_cells(grid):
            entries.append((corner, col, row, next_id))
            next_id += 1
        out[face] = entries
    return out


def tile_offsets(face: str, spins: dict[str, int], cells, edge_mm: float,
                 grid: int):
    """Each tile's centre offset from the face centre, in the CUBE frame (metres).

    Taken from the folded frame rather than from the face name, so it stays
    correct whatever spin the solver chose.  `deploy/cube.py` needs exactly this
    to place `T_cube_tag` off the face centre.
    """
    M = _fold(cells, spins)[face]
    right, up = M[:, 0].astype(float), M[:, 1].astype(float)
    cell = edge_mm / grid / 1000.0
    mid = (grid - 1) / 2.0
    out = {}
    for corner, col, row in tile_cells(grid):
        out[corner] = ((col - mid) * cell * right + (mid - row) * cell * up)
    return out


#: Margin a consumer printer cannot reach, millimetres. A net laid closer to the
#: paper edge than this comes out of the printer with its outermost tiles clipped
#: -- and clipped exactly where the quiet zone is, so the loss is silent until a
#: face stops decoding on the bench.
PRINTABLE_MARGIN_MM = 5.0


def choose_page(edge_mm: float):
    """Smallest page the net fits on with a printable margin, and its name."""
    from reportlab.lib.pagesizes import A3, A4

    net_w, net_h = mm(3 * edge_mm), mm(4 * edge_mm)
    need = 2 * mm(PRINTABLE_MARGIN_MM)
    for name, size in (("A4", A4), ("A3", A3)):
        if net_w + need <= size[0] and net_h + need <= size[1]:
            return name, size
    raise SystemExit(
        f"a {edge_mm:g} mm net is {3 * edge_mm:g} x {4 * edge_mm:g} mm and does "
        f"not fit A3 with a {PRINTABLE_MARGIN_MM:g} mm printable margin")


def draw(path: Path, edge_mm: float, cells, spins, tiles, grid: int,
         cut_border_mm: float = 0.0) -> str:
    from reportlab.lib.colors import Color, black, white
    from reportlab.pdfgen import canvas

    page_name, (page_w, page_h) = choose_page(edge_mm)
    edge = mm(edge_mm)
    net_w, net_h = 3 * edge, 4 * edge
    # Vertical layout, stated rather than nudged. A title above and everything
    # else -- the scale bar and the instructions -- in ONE block below, because
    # two blocks plus the net do not fit A4 at 60 mm: 240 + 25 + 28 + 10 is 303
    # against 297. The earlier layout got away with it only by having nothing
    # under the net and the title 3.6 mm from the paper edge.
    top_block = mm(10.0)
    bottom_block = mm(30.0)
    # A millimetre inside the printable margin, not on it: glyphs carry a little
    # side bearing and the renderer antialiases, so text drawn AT 5.0 mm measures
    # 4.8 mm of ink and the margin check -- correctly -- rejects it.
    margin = mm(PRINTABLE_MARGIN_MM + 1.0)
    origin_x = (page_w - net_w) / 2.0
    low = margin + bottom_block
    high = page_h - margin - top_block
    origin_y = low + ((high - low) - net_h) / 2.0

    pdf = canvas.Canvas(str(path), pagesize=(page_w, page_h))
    pdf.setTitle(f"DexHand cube {grid}x{grid} tag36h11 tiles, {edge_mm:g} mm")

    def cell_origin(col: int, row: int) -> tuple[float, float]:
        return origin_x + col * edge, origin_y + (3 - row) * edge

    # Pale construction grid across the whole 3x4 rectangle. It runs through the
    # empty label cells too, where there is no face boundary to carry a black
    # line, so it still has a job; inside the cross the black lines drawn later
    # cover it.
    pdf.setStrokeColor(Color(0.82, 0.82, 0.82))
    pdf.setLineWidth(0.3)
    pdf.setDash(2, 3)
    for col in range(4):
        pdf.line(origin_x + col * edge, origin_y, origin_x + col * edge, origin_y + net_h)
    for row in range(5):
        pdf.line(origin_x, origin_y + row * edge, origin_x + net_w, origin_y + row * edge)
    pdf.setDash()

    tile_edge = edge / grid
    module = tile_edge / MODULES
    for face in FACE_ORDER:
        col, row = cells[face]
        x0, y0 = cell_origin(col, row)
        pdf.setFillColor(white)
        pdf.rect(x0, y0, edge, edge, stroke=0, fill=1)
        for corner, tcol, trow, tag_id in tiles[face]:
            # Named `bits`, not `grid`: `grid` is this function's tiles-per-edge
            # parameter, and shadowing it here fed a bitmap array into the cell
            # arithmetic -- reportlab then failed deep inside `fp_str` with
            # "truth value of an array is ambiguous", nowhere near the cause.
            bits = np.rot90(tile_bitmap(tag_id), spins[face])
            # Spin the tile's slot within the face by the same amount as its
            # content: a 90 degree turn sends (col, row) to (row, grid-1-col).
            pc, pr = tcol, trow
            for _ in range(spins[face] % 4):
                pc, pr = pr, grid - 1 - pc
            # PDF y grows upward while row indices grow downward.
            px, py = pc, grid - 1 - pr
            tx, ty = x0 + px * tile_edge, y0 + py * tile_edge
            pdf.setFillColor(black)
            for r, values in enumerate(bits):
                for c, is_black in enumerate(values):
                    if is_black:
                        pdf.rect(tx + c * module,
                                 ty + (MODULES - 1 - r) * module,
                                 module, module, stroke=0, fill=1)

    # Every face boundary gets a black line, but a CUT and a FOLD are different
    # instructions and must not look the same -- six identical black rectangles
    # leave the operator guessing which lines to cut, which is worse than no line
    # at all.
    #
    #   silhouette (blank paper on the other side)  ->  solid, and drawn just
    #       OUTSIDE the face, so it costs no quiet zone at all;
    #   internal boundary (another face on the other side)  ->  dashed, black,
    #       which is a fold.
    #
    # Why the offset matters. The white ring outside a tile's black square is its
    # quiet zone -- at 70 mm with a 2x2 grid that ring is 3.5 mm, exactly the one
    # module the format asks for -- and a line centred on the boundary eats half
    # its width off it. Measured (`--check-print`, one subprocess per cell):
    # 0, 0.5, 1.2 and 2.0 mm all decode 24/24 at every span from 66 px down to
    # 29 px, and the forced-failure row at 7.0 mm, which swallows the ring
    # entirely, decodes 0/24. So the flat-on test does not punish a centred line;
    # it also cannot see obliquity or motion blur, which is why the silhouette is
    # offset outward anyway -- free is better than measured-harmless.
    if cut_border_mm > 0.0:
        half = mm(cut_border_mm) / 2.0
        faces = set(cells[f] for f in FACE_ORDER)
        pdf.setLineWidth(mm(cut_border_mm))
        pdf.setLineCap(0)
        for face in FACE_ORDER:
            col, row = cells[face]
            x0, y0 = cell_origin(col, row)
            #            (neighbour cell,  segment,                  outward)
            for dcol, drow, seg, out in (
                (0, -1, ((x0, y0 + edge), (x0 + edge, y0 + edge)), (0.0, 1.0)),
                (0, 1, ((x0, y0), (x0 + edge, y0)), (0.0, -1.0)),
                (-1, 0, ((x0, y0), (x0, y0 + edge)), (-1.0, 0.0)),
                (1, 0, ((x0 + edge, y0), (x0 + edge, y0 + edge)), (1.0, 0.0)),
            ):
                (ax, ay), (bx, by) = seg
                if (col + dcol, row + drow) in faces:
                    pdf.setStrokeColor(black)
                    pdf.setDash(3, 2)
                    pdf.line(ax, ay, bx, by)
                    pdf.setDash()
                else:
                    # Outward by half a line width, plus half again on each end so
                    # the corners of the silhouette close cleanly.
                    ox, oy = out[0] * half, out[1] * half
                    ex, ey = (half, 0.0) if ay == by else (0.0, half)
                    pdf.setStrokeColor(black)
                    pdf.line(ax + ox - ex, ay + oy - ey, bx + ox + ex, by + oy + ey)

    # Labels live in the empty cells of the 3x4 grid, never inside a face: a
    # tag's outer white ring is its quiet zone and text laid in it stops that
    # tile decoding.  Each label sits in a cell that SHARES AN EDGE with the face
    # it names, hugging that edge with an arrowhead pointing across it -- a label
    # merely dropped into the next free cell put "RIGHT +X" beside the BOTTOM
    # face on the first draft, which is the sort of thing this whole net exists
    # to stop an operator having to get right.
    #
    # FRONT is the one face with no empty neighbour: it is the centre of the
    # cross, so it is named as such instead.
    label_cells = {
        "top":    ((0, 0), "right"),
        "left":   ((2, 0), "down"),
        "right":  ((0, 2), "up"),
        "bottom": ((2, 2), "left"),
        "back":   ((0, 3), "right"),
    }
    def clamped(x: float, text: str, size: float = 7.5) -> float:
        """Left x for `text` that keeps it inside the printable box."""
        w = pdf.stringWidth(text, "Helvetica", size)
        return min(max(x, margin), page_w - margin - w)

    pdf.setFont("Helvetica", 7.5)
    for face, (cell, side) in label_cells.items():
        col, row = cell
        x0, y0 = cell_origin(col, row)
        ids = ", ".join(str(t[3]) for t in tiles[face])
        text = f"{face.upper()} {FACE_FRAMES[face][0]}: {ids}"
        pdf.setFillColor(Color(0.35, 0.35, 0.35))
        pad, tip = mm(3.0), mm(2.2)
        if side in ("right", "left"):
            sign = 1 if side == "right" else -1
            ex = x0 + (edge if side == "right" else 0.0)
            pdf.drawRightString(ex - sign * (pad + tip), y0 + edge / 2 - mm(1),
                                text) if side == "right" else \
                pdf.drawString(clamped(ex - sign * (pad + tip), text),
                               y0 + edge / 2 - mm(1), text)
            pdf.setFillColor(Color(0.45, 0.45, 0.45))
            cy = y0 + edge / 2
            pdf.lines([(ex - sign * pad, cy, ex - sign * mm(0.4), cy)])
        else:
            up = side == "up"
            ey = y0 + (edge if up else 0.0)
            w = pdf.stringWidth(text, "Helvetica", 7.5)
            pdf.drawString(clamped(x0 + edge / 2 - w / 2, text),
                           ey - (1 if up else -1) * (pad + tip), text)
            pdf.setFillColor(Color(0.45, 0.45, 0.45))
            cx = x0 + edge / 2
            pdf.lines([(cx, ey - (1 if up else -1) * pad,
                        cx, ey - (1 if up else -1) * mm(0.4))])
    x0, y0 = cell_origin(2, 3)
    pdf.setFillColor(Color(0.35, 0.35, 0.35))
    ids = ", ".join(str(t[3]) for t in tiles["front"])
    pdf.drawCentredString(x0 + edge / 2, y0 + edge / 2 + mm(2),
                          f"FRONT +Y: {ids}")
    pdf.drawCentredString(x0 + edge / 2, y0 + edge / 2 - mm(2.5),
                          "(the CENTRE cell of the cross)")

    # A ruler, because "print at 100 %" is an instruction nobody can check.
    # Every recovered distance scales with the print, and a sheet that came out
    # of a "fit to page" dialog looks exactly like one that did not -- the tags
    # still decode, the pose is just wrong by a constant ratio, which is the
    # hardest kind of error to notice (docs/04 #35 is the same shape: a tag
    # solved at the wrong size only scales the translation, so nothing looks
    # broken). A 100 mm bar with 10 mm ticks turns that into a two-second check
    # with any ruler.
    bar_mm = 100.0
    bar_y = origin_y - mm(9.0)
    pdf.setStrokeColor(black)
    pdf.setLineWidth(mm(0.4))
    pdf.setFillColor(black)
    pdf.setDash()
    # The two end ticks are pulled IN by half a line width so the bar's total INK
    # is exactly `bar_mm`. Drawn on the nominal endpoints they straddle them, and
    # the ruler a person actually measures comes out 0.4 mm long -- a 0.4 % error
    # in the very thing that exists to detect a scaled print.
    lw = mm(0.4)
    pdf.line(margin + lw / 2, bar_y, margin + mm(bar_mm) - lw / 2, bar_y)
    for i in range(int(bar_mm // 10) + 1):
        x = margin + mm(10.0 * i)
        if i == 0:
            x += lw / 2
        elif i == int(bar_mm // 10):
            x -= lw / 2
        pdf.line(x, bar_y, x, bar_y + (mm(3.0) if i % 5 == 0 else mm(1.8)))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margin + mm(bar_mm) + mm(3.0), bar_y - mm(0.6),
                   f"MEASURE ME: exactly {bar_mm:g} mm")
    tile_mm = edge_mm / grid * DETECTION_MODULES / MODULES
    lines = (
        f"If that bar is not {bar_mm:g} mm the print was SCALED: the tile black "
        f"square is then not {tile_mm:g} mm, and every recovered distance is "
        f"wrong by the same ratio.",
        f"Sheet {page_name}.  Net {3 * edge_mm:g} x {4 * edge_mm:g} mm (the solid "
        f"black outline).  Cube edge {edge_mm:g} mm.  Tile black square "
        f"{tile_mm:g} mm ({edge_mm / grid:g} mm label, {MODULES} modules).",
        "CUT AWAY the solid black outline -- it is drawn OUTSIDE the net, so its "
        "INNER edge is the true size; cutting outside it leaves every face "
        f"{cut_border_mm:g} mm oversized.  CREASE on the black dashed lines: they "
        "fall on the tiles' white quiet zones, and a fold through a black module "
        "breaks that tile entirely.",
        "RIGHT +X is the cube's OWN right: facing the FRONT face, it is on your "
        "LEFT.  Wrap printed side OUT -- a mirrored tag decodes as nothing.",
    )
    # Fit the block to the PAGE, not to the net: at 50 mm the net is 150 mm wide
    # and these lines are not, so starting them at the net's left edge ran them
    # off the sheet.
    usable = page_w - 2 * margin
    size = 7.5
    while size > 4.5 and max(
            pdf.stringWidth(line, "Helvetica", size) for line in lines) > usable:
        size -= 0.25
    pdf.setFont("Helvetica", size)
    for i, line in enumerate(lines):
        pdf.drawString(margin, bar_y - mm(6.0) - i * mm(3.6), line)

    pdf.setFillColor(black)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, origin_y + net_h + mm(4.0),
                   f"DexHand reorientation cube -- {grid}x{grid} tag36h11 tiles, "
                   f"{edge_mm:g} mm edge, print on {page_name} at 100 %")
    pdf.showPage()
    pdf.save()
    return page_name


def write_mapping(path: Path, edge_mm: float, cells, spins, tiles,
                  grid: int) -> None:
    lines = [
        "# Generated by generate_cube_apriltag_tiles.py -- do not edit by hand.",
        "#",
        "# The 2x2 tile layout that supersedes the single full-face tags for the",
        "# external-camera pipeline.  `deploy/cube.py` places each tile at its",
        "# face centre plus `offset_m`, expressed in the cube frame.",
        "scheme: tag36h11_2x2_tiles",
        f"edge_size_m: {edge_mm / 1000.0:.4f}",
        f"grid: {grid}",
        f"tiles_per_face: {grid * grid}",
        f"tile_label_size_m: {edge_mm / grid / 1000.0:.4f}",
        f"detector_tag_size_m: "
        f"{edge_mm / grid * DETECTION_MODULES / MODULES / 1000.0:.4f}",
        f"first_tile_id: {FIRST_TILE_ID}",
        "reserved_ids:",
        "  full_face_tags: [0, 1, 2, 3, 4, 5]",
        "  wrist_tag: 10",
        "object_frame: '+X right, +Y front, +Z top'",
        "faces:",
    ]
    for face in FACE_ORDER:
        normal, up = FACE_FRAMES[face]
        offsets = tile_offsets(face, spins, cells, edge_mm, grid)
        lines += [
            f"  {face}:",
            f"    normal_in_cube_frame: '{normal}'",
            f"    printed_up_in_cube_frame: '{up}'",
            f"    net_cell: [{cells[face][0]}, {cells[face][1]}]",
            f"    net_spin_deg: {spins[face] * 90}",
            "    tiles:",
        ]
        for corner, _, _, tag_id in tiles[face]:
            o = offsets[corner]
            lines.append(f"      - {{id: {tag_id}, corner: {corner}, "
                         f"offset_m: [{o[0]:+.4f}, {o[1]:+.4f}, {o[2]:+.4f}]}}")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def check_print(pdf_path: Path, edge_mm: float, grid: int, ids,
                dpi: int = 600) -> str:
    """Rasterise the finished PDF at print resolution and decode every tile.

    The generator already round-trips each tag's BITMAP, which proves the payload
    is right. It does not prove the PAGE is readable: the bitmap check never sees
    the fold lines, the labels, or the cut border, and all three land near a
    tag's quiet zone. This renders what the printer will actually put on paper
    and asks the detector the only question that matters -- how many of the
    tiles come back, and with how much margin.

    Returns a one-line summary; raises if any tile is lost.
    """
    import subprocess
    import tempfile

    import numpy as np
    from pupil_apriltags import Detector

    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png",
                        str(pdf_path), str(stem)], check=True,
                       capture_output=True)
        pages = sorted(Path(tmp).glob("page*.png"))
        if not pages:
            raise RuntimeError("pdftoppm produced no page")
        from PIL import Image
        image = np.asarray(Image.open(pages[0]).convert("L"))

    # Where the ink actually is. `choose_page` reasons about the NET, but the
    # labels and the scale bar stick out beyond it, and a margin computed from
    # the net says nothing about them. Measured here on the rendered page, which
    # is the only thing that knows where the last pixel landed: the 50 and 60 mm
    # sheets were sitting with 0.0 mm of right margin -- label text against the
    # paper edge, which every printer clips.
    ink = image < 200
    rows, cols = np.where(ink)
    page_w_mm = image.shape[1] / dpi * 25.4
    page_h_mm = image.shape[0] / dpi * 25.4
    margins = {
        "left": cols.min() / dpi * 25.4,
        "right": page_w_mm - (cols.max() + 1) / dpi * 25.4,
        "top": rows.min() / dpi * 25.4,
        "bottom": page_h_mm - (rows.max() + 1) / dpi * 25.4,
    }
    tight = {k: round(v, 1) for k, v in margins.items()
             if v < PRINTABLE_MARGIN_MM}
    if tight:
        raise RuntimeError(
            f"ink reaches within {tight} mm of the paper edge (need "
            f"{PRINTABLE_MARGIN_MM:g} mm all round). A printer cannot reach "
            "there, so that ink is cut off -- and if it is a tile, the loss is "
            "silent until a face stops decoding.")

    # Where the ink actually is. `choose_page` reasons about the NET, but the
    # labels and the scale bar stick out beyond it, and a margin computed from
    # the net says nothing about them. Measured here on the rendered page, which
    # is the only thing that knows where the last pixel landed: the 50 and 60 mm
    # sheets were sitting with 0.0 mm of right margin -- label text against the
    # paper edge, which every printer clips.
    ink = image < 200
    rows, cols = np.where(ink)
    page_w_mm = image.shape[1] / dpi * 25.4
    page_h_mm = image.shape[0] / dpi * 25.4
    margins = {
        "left": cols.min() / dpi * 25.4,
        "right": page_w_mm - (cols.max() + 1) / dpi * 25.4,
        "top": rows.min() / dpi * 25.4,
        "bottom": page_h_mm - (rows.max() + 1) / dpi * 25.4,
    }
    tight = {k: round(v, 1) for k, v in margins.items()
             if v < PRINTABLE_MARGIN_MM}
    if tight:
        raise RuntimeError(
            f"ink reaches within {tight} mm of the paper edge (need "
            f"{PRINTABLE_MARGIN_MM:g} mm all round). A printer cannot reach "
            "there, so that ink is cut off -- and if it is a tile, the loss is "
            "silent until a face stops decoding.")

    det = Detector(families="tag36h11", nthreads=4, quad_decimate=1.0,
                   refine_edges=True)
    found = det.detect(image)
    seen = {d.tag_id: d.decision_margin for d in found
            if d.tag_id in set(ids)}
    missing = sorted(set(ids) - set(seen))
    if missing:
        raise RuntimeError(
            f"{len(missing)} of {len(ids)} tiles did not decode off the rendered "
            f"page at {dpi} dpi: {missing}. Something on the page is inside a "
            "quiet zone -- the cut border and the labels are the candidates.")
    scores = np.array(list(seen.values()))
    return (f"  {len(seen)}/{len(ids)} tiles decoded off the rendered page at "
            f"{dpi} dpi; decision margin min {scores.min():.1f} "
            f"median {np.median(scores):.1f}; paper margins "
            f"{ {k: round(v, 1) for k, v in margins.items()} } mm")


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edge-mm", type=float, default=60.0)
    ap.add_argument("--grid", type=int, default=2,
                    help="tiles per face edge: 2 gives 4 tiles a face and "
                         "24 ids, 3 gives 9 and 54")
    ap.add_argument("--cut-border-mm", type=float, default=0.8,
                    help="black line width on every face boundary, mm: solid on "
                         "the silhouette (cut), dashed inside (fold). 0 "
                         "disables. The dashed ones sit in the tiles' quiet "
                         "zone, so widening is not free -- re-run --check-print")
    ap.add_argument("--check-print", action="store_true",
                    help="rasterise the finished PDF at print resolution and "
                         "decode every tile, with and without the border")
    ap.add_argument("--out-dir", type=Path, default=here / "generated")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    spins = solve_spins(NET_CELLS)
    print("fold verification (derived, not drawn):")
    for line in verify(NET_CELLS, spins):
        print(line)

    tiles = assign_tiles(args.grid)
    ids = [t[3] for face in FACE_ORDER for t in tiles[face]]
    print("\ntag bitmap round-trip:")
    print(check_bitmaps(ids))

    g = args.grid
    # The paper size is chosen from the edge length, so the NAME has to come from
    # the same place -- a file called `_A4` that is actually A3 is a printing
    # instruction that lies.
    page_name = choose_page(args.edge_mm)[0]
    pdf = (args.out_dir /
           f"dexhand_cube_tiles_{g}x{g}_{args.edge_mm:g}mm_{page_name}.pdf")
    draw(pdf, args.edge_mm, NET_CELLS, spins, tiles, g,
         cut_border_mm=args.cut_border_mm)
    # The edge length is in the NAME. Without it, generating a 70 mm sheet
    # silently overwrote the 60 mm cube's record -- the same shape of error as
    # docs/04 #40, one directory over.
    mapping = args.out_dir / f"cube_tile_mapping_{g}x{g}_{args.edge_mm:g}mm.yaml"
    write_mapping(mapping, args.edge_mm, NET_CELLS, spins, tiles, g)

    if args.check_print:
        print("\nrendered-page decode:")
        print(f"  border {args.cut_border_mm:g} mm (as written):")
        print(check_print(pdf, args.edge_mm, g, ids))

        control = args.out_dir / f"_control_{pdf.name}"
        draw(control, args.edge_mm, NET_CELLS, spins, tiles, g, cut_border_mm=0.0)
        print("  no border at all (control):")
        print(check_print(control, args.edge_mm, g, ids))

        # The row that MUST fail. Without it, "every tile decoded" is equally
        # consistent with "the border is harmless" and with "this harness cannot
        # see a damaged quiet zone" -- and the second is what a 600 dpi, flat-on
        # render of a clean page looks like. A border two modules wide swallows
        # the ring the detector fits its border against, so nothing may decode.
        smoke = args.edge_mm / g * 2.0 / MODULES
        draw(control, args.edge_mm, NET_CELLS, spins, tiles, g,
             cut_border_mm=smoke)
        try:
            line = check_print(control, args.edge_mm, g, ids)
        except RuntimeError:
            print(f"  self-check at {smoke:g} mm (must fail): FAILED as required "
                  "-- the harness can see a swallowed quiet zone")
        else:
            control.unlink()
            raise SystemExit(
                f"SELF-CHECK DID NOT FAIL: a {smoke:g} mm border covers the "
                f"tiles' quiet zone entirely and still decoded -- {line.strip()}. "
                "Nothing this harness says about the real border means anything.")
        control.unlink()

    tile_mm = args.edge_mm / g * DETECTION_MODULES / MODULES
    print(f"\nwrote {pdf}")
    print(f"wrote {mapping}")
    print(f"\nnet {3 * args.edge_mm:g} x {4 * args.edge_mm:g} mm on {page_name}; "
          f"tile black square {tile_mm:g} mm; ids {ids[0]}-{ids[-1]}; "
          f"cut border {args.cut_border_mm:g} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
