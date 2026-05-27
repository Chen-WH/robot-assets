"""Patch DexRobot021 URDF-converted USD geometry references.

Isaac Sim 5.0 URDF conversion can place visual and collision geometry under
top-level ``/visuals`` and ``/colliders`` prims in configuration layers. When the
main USD is referenced through its defaultPrim, those sibling prims are not
composed into the spawned robot.

This asset-local conversion utility adds explicit link-local references from
each link's ``visuals`` and ``collisions`` prim to the corresponding
configuration-layer prim, then marks those local reference prims as
non-instanceable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from isaaclab.app import AppLauncher

DEXROBOT021_DIR = Path(__file__).resolve().parents[1]
DEFAULT_USD = DEXROBOT021_DIR / "usd" / "dexhand021_left_collision_convex.usd"


def _count_collision_prims(stage) -> int:
    from pxr import UsdPhysics

    return sum(1 for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.CollisionAPI))


def _patch_usd(root_usd: Path) -> tuple[int, int]:
    from pxr import Usd

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
        visual.SetInstanceable(False)
        visual_refs = visual.GetReferences()
        visual_refs.ClearReferences()
        visual_refs.AddReference(str(base_ref), f"/visuals/{link_name}")

        collision = stage.DefinePrim(f"{root_path}/{link_name}/collisions", "Xform")
        collision.SetInstanceable(False)
        collision_refs = collision.GetReferences()
        collision_refs.ClearReferences()
        collision_refs.AddReference(str(physics_ref), f"/colliders/{link_name}")

    stage.GetRootLayer().Save()

    patched_stage = Usd.Stage.Open(str(root_usd))
    if patched_stage is None:
        raise RuntimeError(f"Failed to reopen patched USD: {root_usd}")
    return len(link_names), _count_collision_prims(patched_stage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usd", type=Path, default=DEFAULT_USD, help="Root USD to patch.")
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()

    launcher = AppLauncher(args)
    simulation_app = launcher.app
    try:
        link_count, collision_count = _patch_usd(args.usd)
        print(f"usd: {args.usd}", flush=True)
        print(f"patched_link_count: {link_count}", flush=True)
        print(f"collision_count_after_patch: {collision_count}", flush=True)
        if collision_count == 0:
            raise SystemExit("Patch completed but no CollisionAPI prims are visible.")
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
