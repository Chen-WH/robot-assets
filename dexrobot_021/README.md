# DexRobot021 Assets

This directory keeps DexRobot021 geometry and simulator descriptions as assets,
not runtime control code.

## Layout

- `meshes/`: source and simplified mesh geometry.
- `urdf/`: URDF variants used for conversion and visualization.
- `mjcf/`: MuJoCo variants, including mimic/equality-joint models.
- `usd/`: Isaac Sim / IsaacLab USD assets and conversion metadata.
- `tools/`: asset-local conversion and repair utilities.

## Variants

- `dexhand021_<side>_full_visual`: full visual meshes for rendering and inspection.
- `dexhand021_<side>_convex_collision`: convex collision meshes with independent joints for routine kinematics and dynamics.
- `dexhand021_<side>_convex_mimic`: convex collision meshes with mimic constraints for RL training.
- `dexhand021_<side>_primitive_mimic`: primitive collision geometry with mimic constraints for RL training.

URDF/USD mimic assets use linear mimic joints. MJCF mimic assets use
equality-joint polynomial fits from `params.txt`.

## Tactile Feedback Guidance

Mimic variants intentionally remove `*_tip` links and keep the five `*_pad`
links. The pad links are the tactile/contact observation anchors; `usd/config.yaml`
keeps `merge_fixed_joints: false` so IsaacLab can still target them as rigid
bodies after URDF conversion.

For MuJoCo-Warp/MJLab RL, the MJCF mimic variants use pad-site contact sensors
as the default tactile signal:

```xml
<contact name="contact_l_f_link1_pad_force" site="site_l_f_link1_pad" data="force" reduce="netforce" />
```

Each pad reports a 3D net contact force in the world frame. The XML keeps
commented alternatives for normal-only scalar `<touch>` sensors and binary
`<contact data="found">` contact detection.

For IsaacSim/IsaacLab RL, define tactile sensors in the task config rather than
inside URDF/USD:

```python
pad_contact = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Robot/.*_pad",
    history_length=1,
    track_pose=True,
)

# Binary contact: torch.linalg.norm(pad_contact.data.net_forces_w, dim=-1) > threshold
# Filtered normal force to an object: set filter_prim_paths_expr, usually one pad sensor per filter.
# Newer IsaacLab builds can expose friction_forces_w with track_friction_forces=True;
# combine that with net_forces_w for a closer 3D force-vector approximation.
```

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
  --usd usd/dexhand021_left_convex_collision.usd \
  --headless
```
