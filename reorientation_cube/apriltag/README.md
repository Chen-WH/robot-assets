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

All three cube sizes reuse the same face IDs from 0 through 5. Use only one cube size
at a time if the tracker identifies objects solely by tag ID.

```text
                          TOP ID 4
                   top edge toward BACK

LEFT ID 3      FRONT ID 0      RIGHT ID 1      BACK ID 2
top -> TOP     top -> TOP      top -> TOP       top -> TOP

                        BOTTOM ID 5
                  top edge toward FRONT
```

The word `top` refers to the top edge of the official PNG/SVG image. Mark the backing
paper before separating the labels so the face and orientation remain unambiguous.

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
