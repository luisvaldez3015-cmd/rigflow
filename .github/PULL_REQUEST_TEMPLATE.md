## Summary

What does this change and why?

## How it was tested

- [ ] `mayapy -I scripts/run_tests.py` (unit) passes
- [ ] `mayapy -I scripts/run_tests.py --integration` passes (if Maya code changed)
- [ ] Verified inside interactive Maya (version: ____) for UI/viewport changes

## Checklist

- [ ] Maya-dependent code stays in `rigflow/scene`, `retargeting`, `animation`, `ui`
- [ ] New behaviour has tests
- [ ] `CHANGELOG.md` updated under **Unreleased**
- [ ] Documentation updated if the user-facing behaviour changed
- [ ] No proprietary assets, local paths or debug output committed
