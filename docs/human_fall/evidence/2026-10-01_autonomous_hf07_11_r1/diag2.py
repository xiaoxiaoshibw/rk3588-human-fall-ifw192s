import os
import sys

import core

print("core.__file__", core.__file__)
print("core.__path__", list(getattr(core, "__path__", [])))
print("sys.path[:8]")
for entry in sys.path[:8]:
    print("   ", entry)
