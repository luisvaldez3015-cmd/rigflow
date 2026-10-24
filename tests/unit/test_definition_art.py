"""Contract for the shipped definition layout and its role vocabulary."""
import json
import math
from pathlib import Path
import unittest

from rigflow.skeleton.roles import FINGER_PARTS, REQUIRED_ROLES, SIDE_PARTS


class DefinitionArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2] / "assets" / "definition" / "layout.json"
        cls.layout = json.loads(path.read_text(encoding="utf-8"))

    def test_layout_roles_match_expected_vocabulary(self):
        body = {"Hips", "Spine", "Spine1", "Spine2", "Spine3", "Neck", "Head"}
        body.update(side + part for side in ("Left", "Right") for part in SIDE_PARTS)
        hands = {side + "Hand" for side in ("Left", "Right")}
        hands.update(side + part + str(index) for side in ("Left", "Right")
                     for part in FINGER_PARTS for index in (1, 2, 3))
        for view, expected in (("body", body), ("hands", hands)):
            data = self.layout[view]
            self.assertEqual(set(data["joints"]), expected)
            label_roles = expected if view == "body" else {side + part for side in ("Left", "Right")
                                                           for part in ("Hand",) + FINGER_PARTS}
            self.assertEqual(set(data["labels"]), label_roles)
            self.assertTrue(all(a in expected and b in expected for a, b in data["bones"]))
            self.assertEqual({role for role, joint in data["joints"].items() if joint["required"]},
                             set(REQUIRED_ROLES) & expected)
        self.assertEqual(set(self.layout["body"]["labels"]), body)

    def test_body_leaders_run_from_label_to_joint(self):
        body = self.layout["body"]
        for role, label in body["labels"].items():
            with self.subTest(role=role):
                leader = label["leader"]
                self.assertGreaterEqual(len(leader), 3)
                x, y = leader[0]
                self.assertLessEqual(math.hypot(x - label["x"], y - label["y"]), 6.1)
                if label["align"] == "right":
                    self.assertGreater(x, label["x"])
                else:
                    self.assertLess(x, label["x"])
                joint = body["joints"][role]
                self.assertEqual(leader[-1], [joint["x"], joint["y"]])
        self.assertTrue(all("leader" not in label for label in self.layout["hands"]["labels"].values()))


if __name__ == "__main__":
    unittest.main()
