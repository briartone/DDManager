import os
import sys


def _runtime_root():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


root = _runtime_root()
tcl_library = os.path.join(root, "_tcl_data")
tk_library = os.path.join(root, "_tk_data")

if os.path.isdir(tcl_library):
    os.environ["TCL_LIBRARY"] = tcl_library
if os.path.isdir(tk_library):
    os.environ["TK_LIBRARY"] = tk_library
