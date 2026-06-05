#!/usr/bin/env python3
"""Convert official DexRobot021 URDF variants to IsaacLab USD assets.

Outputs use instanceable visuals, direct collision geometry, and PhysX mimic
constraints for URDF mimic joints.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from isaaclab.app import AppLauncher


DEXROBOT021_DIR = Path(__file__).resolve().parents[1]
URDF_DIR = DEXROBOT021_DIR / "urdf"
USD_DIR = DEXROBOT021_DIR / "usd"

OFFICIAL_ASSETS = (
    "dexhand021_left_full_visual",
    "dexhand021_right_full_visual",
    "dexhand021_left_convex_collision",
    "dexhand021_right_convex_collision",
    "dexhand021_left_convex_mimic",
    "dexhand021_right_convex_mimic",
    "dexhand021_left_primitive_mimic",
    "dexhand021_right_primitive_mimic",
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--assets",
    nargs="+",
    choices=OFFICIAL_ASSETS,
    default=OFFICIAL_ASSETS,
    help="Official asset stems to convert.",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg  # noqa: E402
from patch_link_geometry_refs import _patch_usd  # noqa: E402


def _convert_asset(stem: str) -> None:
    urdf_path = URDF_DIR / f"{stem}.urdf"
    if not urdf_path.exists():
        raise FileNotFoundError(urdf_path)

    cfg = UrdfConverterCfg(
        asset_path=str(urdf_path.resolve()),
        usd_dir=str(USD_DIR.resolve()),
        usd_file_name=f"{stem}.usd",
        force_usd_conversion=True,
        make_instanceable=True,
        fix_base=True,
        root_link_name=None,
        link_density=0.0,
        merge_fixed_joints=False,
        convert_mimic_joints_to_normal_joints=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            drive_type="force",
            target_type="position",
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=100.0,
                damping=1.0,
            ),
        ),
        collider_type="convex_hull",
        self_collision=False,
        replace_cylinders_with_capsules=False,
        collision_from_visuals=False,
    )
    converter = UrdfConverter(cfg)
    link_count, collision_count, mimic_count = _patch_usd(Path(converter.usd_path))
    print(f"asset: {stem}", flush=True)
    print(f"  usd: {converter.usd_path}", flush=True)
    print(f"  patched_link_count: {link_count}", flush=True)
    print(f"  direct_collision_count: {collision_count}", flush=True)
    print(f"  physx_mimic_count: {mimic_count}", flush=True)
    if collision_count == 0:
        raise RuntimeError(f"No direct CollisionAPI prims are visible after patching {converter.usd_path}")


def main() -> None:
    try:
        for stem in args_cli.assets:
            _convert_asset(stem)
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
