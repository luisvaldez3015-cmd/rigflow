"""UI previews must fail with an actionable error in standalone."""

from __future__ import annotations

import unittest

from rigflow.core.errors import UnsupportedError
from rigflow.scene.viewport import create_model_panel


class ViewportBatchTests(unittest.TestCase):
    def test_requires_interactive_maya(self):
        with self.assertRaises(UnsupportedError) as caught:
            create_model_panel("missingLayout")
        self.assertEqual(caught.exception.message, "Viewport previews need the Maya UI")
        self.assertTrue(caught.exception.hint)
