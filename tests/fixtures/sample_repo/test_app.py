from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import greet


class GreetingTests(unittest.TestCase):
    def test_greet(self) -> None:
        self.assertEqual(greet("Agent"), "Hello, Agent")
