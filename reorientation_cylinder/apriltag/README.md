# DexHand Cylinder AprilTags

Print-ready AprilTag 3 `tag36h11` labels for the nominal 60 mm diameter by
80 mm tall wooden cylinder.

## Proposed attachment

| Face | ID | Outward normal | Complete label | Detector `tagSize` |
|---|---:|---:|---:|---:|
| top | 6 | +Z | 36 mm | 28.8 mm (`0.0288`) |
| bottom | 7 | -Z | 36 mm | 28.8 mm (`0.0288`) |

IDs 6 and 7 avoid collisions with the prepared cube's IDs 0 through 5. A
36 mm square has a 50.91 mm diagonal, leaving about 4.54 mm radial margin to a
60 mm circular face. Print at `100%` / `Actual size`, then measure the 8x8 black
square boundary rather than assuming the nominal value.

The machine-readable planned physical record is
[`physical_cylinder_tag_layout.yaml`](physical_cylinder_tag_layout.yaml). Tag
centering and in-plane orientation remain pending until attachment is measured;
the file is therefore not yet a complete metric `T_cylinder_tag` layout.

## Regeneration

```bash
python3 reorientation_cylinder/apriltag/generate_cylinder_apriltags.py
```

This writes two SVG files, an A4 PDF, and a generation manifest under
`generated/`. It requires ReportLab. The frozen marker payloads were generated
from OpenCV 4.12 `DICT_APRILTAG_36h11` and are detector-verified during asset
validation.
