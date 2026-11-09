"""AC-10: zero runtime dependencies, standard library only."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import json, sys
before = set(sys.modules)
import llm_format_guard
new = {m.split('.')[0] for m in set(sys.modules) - before}
print(json.dumps(sorted(new)))
"""


class TestStdlibOnly(unittest.TestCase):
    def test_import_loads_only_stdlib_and_self(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, env=env, check=True)
        loaded = set(json.loads(out.stdout))
        allowed = set(sys.stdlib_module_names) | {"llm_format_guard"}
        self.assertEqual(loaded - allowed, set(), "runtime import pulled in a third-party module")
        self.assertNotIn("kss", loaded)

    def test_metadata_has_no_runtime_requirements(self):
        from importlib.metadata import PackageNotFoundError, requires

        try:
            reqs = requires("llm-format-guard") or []
        except PackageNotFoundError:
            self.skipTest("package is not installed")
        # the optional kss extra shows up with a marker; nothing may be unconditional
        self.assertEqual([r for r in reqs if "extra ==" not in r], [])


if __name__ == "__main__":
    unittest.main()
