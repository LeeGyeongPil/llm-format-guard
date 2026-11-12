"""Import this first in CLI tests: it pins the output language to English.

The command line follows LANG when nothing else is set, so without this a developer
whose shell is Korean would see Korean text and the English assertions would fail.
"""

import os

os.environ["LLM_FORMAT_GUARD_LANG"] = "en"
