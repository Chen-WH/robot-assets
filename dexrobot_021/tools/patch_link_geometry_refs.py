"""Patch DexRobot021 URDF-converted USD geometry references.

Isaac Sim 5.0 URDF conversion can place visual and collision geometry under
top-level ``/visuals`` and ``/colliders`` prims in configuration layers. When the
main USD is referenced through its defaultPrim, those sibling prims are not
composed into the spawned robot.

This asset-local conversion utility adds explicit link-local references from
each link's ``visuals`` and ``collisions`` prim to the corresponding
configuration-layer prim. Visual references are left instanceable to keep cloned
IsaacLab scenes compact. Collision references stay non-instanceable so PhysX
sees direct ``CollisionAPI`` prims instead of collision APIs hidden behind USD
instance proxies. URDF ``mimic`` tags are also re-authored as
``PhysxMimicJointAPI:rotZ`` constraints on the follower joints.
"""

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from isaaclab.app import AppLauncher

DEXROBOT021_DIR = Path(__file__).resolve().parents[1]
DEFAULT_USD = DEXROBOT021_DIR / "usd" / "dexhand021_left_convex_collision.usd"
URDF_DIR = DEXROBOT021_DIR / "urdf"


def _count_collision_prims(stage) -> int:
    from pxr import UsdPhysics

    return sum(1 for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.CollisionAPI))


def _read_urdf_mimics(urdf_path: Path) -> list[tuple[str, str, float, float]]:
    if not urdf_path.exists():
        return []

    root = ET.parse(urdf_path).getroot()
    mimics = []
    for joint in root.findall("joint"):
        mimic = joint.find("mimic")
        if mimic is None:
            continue
        follower = joint.attrib["name"]
        driver = mimic.attrib["joint"]
        multiplier = float(mimic.attrib.get("multiplier", "1.0"))
        offset = float(mimic.attrib.get("offset", "0.0"))
        mimics.append((follower, driver, multiplier, offset))
    return mimics


def _apply_api_schema(prim, schema_name: str) -> None:
    from pxr import Sdf

    schemas = [str(schema) for schema in prim.GetAppliedSchemas()]
    if schema_name not in schemas:
        schemas.insert(0, schema_name)
    prim.SetMetadata("apiSchemas", Sdf.TokenListOp.Create(prependedItems=schemas))


def _patch_physx_mimics(stage, root_path, root_usd: Path) -> int:
    from pxr import Sdf

    urdf_path = URDF_DIR / f"{root_usd.stem}.urdf"
    mimic_specs = _read_urdf_mimics(urdf_path)
    for follower, driver, multiplier, offset in mimic_specs:
        joint = stage.GetPrimAtPath(f"{root_path}/joints/{follower}")
        if not joint.IsValid():
            raise RuntimeError(f"Missing mimic follower joint prim: {root_path}/joints/{follower}")
        driver_path = Sdf.Path(f"{root_path}/joints/{driver}")
        if not stage.GetPrimAtPath(driver_path).IsValid():
            raise RuntimeError(f"Missing mimic reference joint prim: {driver_path}")

        # PhysX uses: target + gearing * reference + offset = 0.
        # USD angular joint positions/offsets are authored in degrees, while URDF
        # mimic offsets are radians.
        usd_offset = math.degrees(offset) if joint.GetTypeName() == "PhysicsRevoluteJoint" else offset
        _apply_api_schema(joint, "PhysxMimicJointAPI:rotZ")
        joint.CreateRelationship("physxMimicJoint:rotZ:referenceJoint").SetTargets([driver_path])
        joint.CreateAttribute("physxMimicJoint:rotZ:referenceJointAxis", Sdf.ValueTypeNames.Token).Set("rotZ")
        joint.CreateAttribute("physxMimicJoint:rotZ:gearing", Sdf.ValueTypeNames.Float).Set(-multiplier)
        joint.CreateAttribute("physxMimicJoint:rotZ:offset", Sdf.ValueTypeNames.Float).Set(-usd_offset)
        joint.CreateAttribute("physxMimicJoint:rotZ:naturalFrequency", Sdf.ValueTypeNames.Float).Set(100.0)
        joint.CreateAttribute("physxMimicJoint:rotZ:dampingRatio", Sdf.ValueTypeNames.Float).Set(1.0)
        joint.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(0.0)
        joint.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(0.0)
    return len(mimic_specs)


def _patch_usd(root_usd: Path) -> tuple[int, int, int]:
    from pxr import Usd

    root_usd = root_usd.expanduser().resolve()
    stage = Usd.Stage.Open(str(root_usd))
    if stage is None:
        raise RuntimeError(f"Failed to open USD: {root_usd}")

    default_prim = stage.GetDefaultPrim()
    if not default_prim.IsValid():
        raise RuntimeError(f"USD has no valid defaultPrim: {root_usd}")

    stem = root_usd.stem
    base_ref = root_usd.parent / "configuration" / f"{stem}_base.usd"
    physics_ref = root_usd.parent / "configuration" / f"{stem}_physics.usd"
    for ref_path in (base_ref, physics_ref):
        if not ref_path.exists():
            raise FileNotFoundError(ref_path)
    base_asset = base_ref.relative_to(root_usd.parent).as_posix()
    physics_asset = physics_ref.relative_to(root_usd.parent).as_posix()

    root_path = default_prim.GetPath()
    link_names = [
        child.GetName()
        for child in default_prim.GetChildren()
        if child.GetTypeName() == "Xform" and child.GetName() not in {"Looks"}
    ]
    if not link_names:
        raise RuntimeError(f"No link Xforms found under defaultPrim {root_path}.")

    for link_name in link_names:
        visual = stage.DefinePrim(f"{root_path}/{link_name}/visuals", "Xform")
        visual.SetInstanceable(True)
        visual_refs = visual.GetReferences()
        visual_refs.ClearReferences()
        visual_refs.AddReference(base_asset, f"/visuals/{link_name}")

        collision = stage.DefinePrim(f"{root_path}/{link_name}/collisions", "Xform")
        collision.SetInstanceable(False)
        collision_refs = collision.GetReferences()
        collision_refs.ClearReferences()
        collision_refs.AddReference(physics_asset, f"/colliders/{link_name}")

    mimic_count = _patch_physx_mimics(stage, root_path, root_usd)

    stage.GetRootLayer().Save()

    patched_stage = Usd.Stage.Open(str(root_usd))
    if patched_stage is None:
        raise RuntimeError(f"Failed to reopen patched USD: {root_usd}")
    return len(link_names), _count_collision_prims(patched_stage), mimic_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--usd",
        type=Path,
        nargs="+",
        default=[DEFAULT_USD],
        help="Root USD file(s) to patch.",
    )
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()

    launcher = AppLauncher(args)
    simulation_app = launcher.app
    try:
        for usd in args.usd:
            link_count, collision_count, mimic_count = _patch_usd(usd)
            print(f"usd: {usd}", flush=True)
            print(f"patched_link_count: {link_count}", flush=True)
            print(f"collision_count_after_patch: {collision_count}", flush=True)
            print(f"physx_mimic_count_after_patch: {mimic_count}", flush=True)
            if collision_count == 0:
                raise SystemExit(f"Patch completed but no CollisionAPI prims are visible: {usd}")
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
