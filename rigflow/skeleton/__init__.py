"""Pure-Python skeleton model and analysis (no Maya dependency).

* :mod:`rigflow.skeleton.model` — joint graph (:class:`Skeleton`, :class:`JointInfo`).
* :mod:`rigflow.skeleton.roles` — canonical humanoid roles (HumanIK vocabulary).
* :mod:`rigflow.skeleton.naming` — role inference from joint names.
* :mod:`rigflow.skeleton.topology` — role inference from hierarchy and rest pose.
"""

from rigflow.skeleton.model import JointInfo, Skeleton  # noqa: F401
from rigflow.skeleton.roles import Side  # noqa: F401
