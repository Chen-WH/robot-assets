# Wuji Hand assets

This directory contains the left- and right-hand descriptions for the original
Wuji Hand. Each hand has 20 independently actuated revolute joints.

## Layout

- `mjcf/{left,right}.xml`: fixed-base MuJoCo models with position actuators.
- `urdf/{left,right}.urdf`: fixed-base URDF models with repository-relative
  mesh paths.
- `meshes/{left,right}/`: visual and collision STL meshes.

The MJCF files can be loaded directly, for example:

```bash
python -m mujoco.viewer --mjcf=mjcf/right.xml
```

## Provenance

- Upstream: <https://github.com/wuji-technology/wuji-description>
- Upstream revision: `4c1073d0a3ad1daaf6546d219db751d8448d3888`
- Imported path: `hand/body`
- Imported on: 2026-08-30

The mesh geometry, kinematics, inertial parameters, joint limits, and MJCF
actuators are unchanged from upstream. The URDF-only MuJoCo compiler `meshdir`
is set to `.` so MuJoCo resolves the URDF's existing relative mesh paths
without prepending the mesh directory a second time. ROS-specific launch/RViz
files, USD, and STEP files are outside this asset subset.

The upstream files are distributed under the MIT License; see [LICENSE](LICENSE).
