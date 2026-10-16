# Animation Transfer Guide

This page explains what happens between **Review Animation** and the moment
the transferred motion lands on your character, and which choices you have.

## The workflow in one picture

```
Source skeleton (animated)        Destination skeleton (your rig)
        │                                   │
        └──── joint mapping (roles) ────────┘
                        │
              1. Preview (live, nothing written)
                        │
              2. Confirm → bake keys
                        │
     destination joints keyed on an animation layer (default)
```

## Backends

RigFlow chooses the best available engine automatically and tells you which
one is active in the review view.

| Backend | When | What you get |
|---------|------|--------------|
| **HumanIK** (default) | The HumanIK plugins that ship with Maya load correctly | Proportion-aware full-body retargeting with a live preview: the destination follows the source as you scrub. Bone lengths are preserved exactly; root motion is scaled by the hip-height ratio. |
| **Matrix fallback** | HumanIK is unavailable | World-space rotation transfer with root translation scaled by hip height. No live preview (the source plays while the destination waits for the bake), no IK, no floor contact, no twist distribution. |

Both backends only touch the destination joints that appear in the mapping
with a complete source and destination. Facial joints, twist helpers, props
and anything you excluded are never written.

## What "stance pose" means and why it matters

HumanIK compares both skeletons in a reference pose. RigFlow puts each
skeleton back into its **bind pose** automatically before characterising it:

- if the skeleton has a Maya bind pose node (skinned characters), that pose is restored;
- otherwise all joint rotations are zeroed, which is the bind pose for
  skeletons exported from Maya and from Mixamo (their T-pose lives in the
  joint orients).

The source animation is disconnected only for that instant and reconnected
immediately; nothing is lost. The hips position of the stance is taken from
the first frame of the clip. If a clip starts mid-air or crouched, expect a
small vertical offset in the result; a future version will let you pick the
stance frame.

## Baking options

**Bake to animation layer** (default, recommended). RigFlow creates an
override animation layer named `rigflow_transfer` (numbered if it already
exists) and writes the keys there. Your existing animation on the destination
stays untouched on the base layer. Mute or delete the layer to go back; blend
its weight to mix.

**Bake directly** replaces the keys on the destination joints. Use it only on
a clean skeleton.

In both cases:

- rotation is keyed on every mapped joint, on every frame of the clip
  (`sampleBy` 1), no key reduction, no keys outside the clip range;
- translation is keyed on the hips (root motion) and on any destination joint
  that was already translating;
- the time slider is set to the clip range during preview and restored afterwards;
- the transient HumanIK nodes are deleted after the bake, so the scene only
  contains your characters plus animation curves.

## Verification RigFlow performs for you

After every bake RigFlow checks that the baked motion matches the preview
(maximum position difference under 0.001 cm) and that destination bone
lengths did not change. The numbers are stored with the clip and shown in
the Animation list tooltip. If they are off, the transfer is reported as an
error with a hint instead of silently succeeding.

## Undo

- **Preview** is one undo step (it creates the HumanIK characters and the
  live connection).
- **Confirm / Transfer** is one undo step: Ctrl+Z removes the layer and the
  keys. If you had a preview running, a second Ctrl+Z removes it as well.
- Closing the window or removing a clip cancels its preview and restores the
  destination's original inputs.

## Continuing to animate the face

The destination's facial joints and controls are classified as *ignored* by
the matching step, so they receive no keys and keep their constraints and
drivers. After the body transfer you can keep keying jaw, eyes, brows and
any control that is not part of the body mapping. The demo scene that ships
with RigFlow (`Help → Create demo scene`) includes a jaw control precisely to
show this.

## Known limitations

- Rigs whose joints are driven by animation controls (FK/IK control rigs)
  receive the bake on the joints; baking onto controls is planned.
- Non-humanoid characters are not supported.
- Non-zero `rotateAxis` on destination joints triggers a warning with the
  matrix fallback (HumanIK handles it).
- Clips whose first frame is not a grounded pose may need a manual height
  adjustment of the hips layer.
