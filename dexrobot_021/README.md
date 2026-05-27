# DexRobot021 Assets

This directory keeps DexRobot021 geometry and simulator descriptions as assets,
not runtime control code.

## Layout

- `meshes/`: source and simplified mesh geometry.
- `urdf/`: URDF variants used for conversion and visualization.
- `mjcf/`: MuJoCo variants, including mimic/equality-joint models.
- `usd/`: Isaac Sim / IsaacLab USD assets and conversion metadata.
- `tools/`: asset-local conversion and repair utilities.

## USD Conversion Note

`tools/patch_link_geometry_refs.py` repairs a USD composition issue seen after
IsaacLab/Isaac Sim URDF conversion with instanceable assets. Some converter
outputs keep geometry under sibling configuration-layer prims such as
`/visuals/<link>` and `/colliders/<link>`. When a downstream scene references
only the main USD defaultPrim, those sibling prims may not compose into the robot
instance.

The script adds explicit references from each link-local `visuals` and
`collisions` prim back to the matching configuration-layer prim. It is an
offline post-conversion tool. Keeping it under `tools/` preserves the asset
library boundary: consumers can load USD/MJCF/URDF files without importing
IsaacLab or running this script.

Example:

```bash
cd /path/to/robot-assets/dexrobot_021
python tools/patch_link_geometry_refs.py \
  --usd usd/dexhand021_left_collision_convex.usd \
  --headless
```
