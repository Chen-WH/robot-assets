# DexHand Cube AprilTags

Print-ready AprilTag 3 `tag36h11` labels for 50, 60, and 70 mm pine cubes.

## Generated sizes

The complete 10x10 label, including its official white border, covers the full cube face.
The detector size is the 8x8 black-square boundary used by AprilTag pose estimation.

| Cube edge | Full label | Detector `tagSize` |
| ---: | ---: | ---: |
| 50 mm | 50 mm | 40 mm (`0.040`) |
| 60 mm | 60 mm | 48 mm (`0.048`) |
| 70 mm | 70 mm | 56 mm (`0.056`) |

Use the measured black-square size after printing if it differs from these nominal values.

## Face mapping

One mapping, used by the generator, the YAML, the SVG filenames and any tracker.
**Face names are the cube's own axes, and the unfolding below is drawn as you see
it while facing the FRONT face** -- so the cube's RIGHT face (+X) appears on your
*left*, the way a person facing you has their right hand on your left:

```text
                          TOP ID 0 (+Z)

RIGHT ID 4 (+X)  FRONT ID 1 (+Y)   LEFT ID 2 (-X)   BACK ID 3 (-Y)
   your left        facing you      your right       (behind)

                        BOTTOM ID 5 (-Z)
```

Reading that mirror backwards -- taking the neighbour drawn to the right of ID 1
to be the +X face -- is what put IDs 2 and 4 on each other's faces until
2026-09-05. The ID order across the strip, `4 1 2 3`, is what the cube physically
has and has never changed; only the axis names attached to the two side positions
were wrong.

Machine-readable in [`physical_cube_tag_layout.yaml`](physical_cube_tag_layout.yaml)
and [`generated/cube_tag_mapping.yaml`](generated/cube_tag_mapping.yaml); these two
agree. IDs 1, 2, 3 and 4 are upright, each tag's top edge pointing at the cube TOP
face. ID 0's top edge points at the BACK face and ID 5's at the FRONT face, which
follows from the two edge adjacencies the operator froze:

- the bottom edge of ID 0 joins the top edge of ID 1 across the TOP/FRONT edge;
- the top edge of ID 5 joins the bottom edge of ID 1 across the BOTTOM/FRONT edge.

The four side tags close the loop laterally, in each tag image's own left/right:
ID 1 left joins ID 4 right, ID 1 right joins ID 2 left, ID 2 right joins ID 3
left, ID 3 right joins ID 4 left. Walking image-right that is the cycle
`1 -> 2 -> 3 -> 4`, which the mapping above now reproduces.

**What checks what.** `Cube.verify_layout()` in
`armhand-mjlab/src/armhand_mjlab/deploy/cube.py` checks the constructed tag frames
against *this record* -- outward normals, printed up directions, right-handedness,
and that each origin lies on its face. It pins the tag frame convention (`+z`
outward face normal, `+y` down the printed image, `+x = y cross z`) rather than
leaving it assumed, and it is the check that a code change broke the table. It
cannot tell you the record itself is wrong about the cube, and it passed
throughout the period when it was: the lateral adjacencies, the one part of the
record that disagreed, are deliberately not checked there.

The check against the physical cube is `faceaudit.py` in the same repository. It
scores every pair of faces that appears in one camera frame against every other,
so a swapped or rotated face shows up as a pose disagreement of tens of degrees.
Two things it will not do: score a face that never shares a frame with a
neighbour (it names those instead of passing them), and score anything at all if
the cube is only ever shown one face at a time.

> **History.** Until 2026-09-04 the generator emitted a different assignment --
> ID 0 on the front, ID 4 on top -- and the physical cubes were stickered to the
> layout above instead, so `generated/cube_tag_mapping.yaml` and
> `physical_cube_tag_layout.yaml` disagreed by a 90 degree rotation. A pipeline
> that only tracks position never notices that; one that tracks orientation is
> wrecked by it. The generator now emits the physical layout and the two files
> agree. The in-plane orientations were already the same for every face position;
> only the id-to-face assignment moved.
>
> **2026-09-05: IDs 2 and 4 were exchanged.** RIGHT (+X) carries ID 4 and LEFT
> (-X) carries ID 2; before this they were the other way round. Cause and
> evidence are in `physical_cube_tag_layout.yaml` under `corrections`. In short:
> the tracker saw IDs 3 and 4 on the real cube at once and their pose votes
> disagreed by 179.2 deg about the cube z axis, which is what an exchange of two
> opposite side faces looks like; a 180 deg about z alone cannot say whether the
> exchanged pair is {1,3} or {2,4}, and the operator's unfolding is what picked
> {2,4}. Re-audited afterwards over two runs: 11 of the 12 observable face pairs
> scored, all between 0.63 and 1.52 deg, and those 11 connect all six faces. The
> other three pairs are opposite faces and can never share a frame. What such an
> audit can never see is a rotation common to all six faces -- and that is
> necessarily a cube symmetry, so there is nothing left in it to find.
>
> **`generated/dexhand_cube_tag36h11_A4.pdf` has NOT been regenerated** and still
> carries the old face labels under each tag (`FRONT | ID 00`, `TOP | ID 04`, ...).
> Regenerating needs `reportlab` and a local copy of `apriltag-imgs`, neither of
> which was available. The tag images themselves are correct -- only the printed
> captions are stale, and after 2026-09-05 they are stale in a second way: the
> sheet cut for the RIGHT face carries ID 2, which now belongs on the LEFT face,
> and the page is missing the header line that says whose left and right these
> are. Re-run the generator before printing a new set. The SVGs in
> `generated/svg/` are correct: each file keeps the tag image it always had and
> was renamed to the face that tag actually sits on.

## Printing

Use [generated/dexhand_cube_tag36h11_A4.pdf](generated/dexhand_cube_tag36h11_A4.pdf):

1. Print at `100%` / `Actual size`; disable `Fit to page`.
2. Prefer a monochrome laser printer at 600 dpi or better and matte adhesive paper.
3. Measure the black-square boundary on each page before attaching the labels.
4. Cut at the full white-square boundary. Gray crop marks and face labels stay on the scrap.
5. Keep the sticker flush with the face and do not fold it across a cube edge.

## Regeneration

The generator consumes the unmodified 10x10 PNGs from the official
[`AprilRobotics/apriltag-imgs`](https://github.com/AprilRobotics/apriltag-imgs) repository:

```bash
python3 reorientation_cube/apriltag/generate_cube_apriltags.py \
  --source-dir /path/to/apriltag-imgs/tag36h11
```

It requires Pillow and ReportLab.
