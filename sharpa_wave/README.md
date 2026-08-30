# Sharpa Wave assets

This directory contains fixed-base left- and right-hand descriptions for the
Sharpa Wave 01. Each hand has 22 independently actuated revolute joints.

## Layout and variants

- `mjcf/`: MuJoCo models with position actuators.
- `urdf/`: URDF models with repository-relative mesh paths.
- `meshes/{left,right}/`: visual and collision STL meshes.

For each side, three model variants are available:

| File suffix | Root interface |
| --- | --- |
| none | Bare hand base |
| `_with_flange` | Flange-level mounting interface |
| `_with_wrist` | Wrist structure and collision geometry |

For example, the right-hand flange model can be loaded directly with:

```bash
python -m mujoco.viewer --mjcf=mjcf/right_sharpa_wave_with_flange.xml
```

## Provenance

- Upstream: <https://github.com/sharpa-robotics/sharpa-urdf-usd-xml>
- Upstream revision: `6eea427eb24189519f32b9f21674cd534d3f973c`
- Imported paths: `wave_01/left_sharpa_wave` and
  `wave_01/right_sharpa_wave`
- Imported on: 2026-08-30

The mesh geometry, kinematics, inertial parameters, joint limits, and MJCF
actuators are unchanged from upstream. To make the models self-contained in
this repository layout, MJCF `meshdir` values point to `../meshes/<side>`, URDF
`package://<side>_sharpa_wave/meshes/` references point to the same relative
asset directory, and the URDF-only MuJoCo compiler `meshdir` is set to `.`.
Floating-base, dual-hand, and USD variants remain available upstream and are
not duplicated here.

The upstream files are distributed under the Apache License 2.0; see
[LICENSE.txt](LICENSE.txt) and [NOTICE.txt](NOTICE.txt).
