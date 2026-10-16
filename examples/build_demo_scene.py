"""Create the RigFlow demo scene in the current Maya session.

Run from the Script Editor (Python tab) after installing RigFlow::

    import rigflow.scene.demo as demo
    demo.build_demo_scene(new_scene=True)

Or execute this file. The scene contains a Mixamo-style source skeleton
performing a jump (frames 1–48) and a short destination character with its
own joint names, a skinned proxy mesh and a small facial setup. Open RigFlow,
select ``root_JNT`` and press *Use selection* in the Rig section, then use
*From scene…* in the Animation section and pick ``mixamorig:Hips``.
"""

from rigflow.scene.demo import build_demo_scene

if __name__ == "__main__":
    scene = build_demo_scene(new_scene=True)
    print("Source root: {}\nDestination root: {}\nMesh: {}".format(
        scene.source_root, scene.destination_root, scene.destination_mesh))
