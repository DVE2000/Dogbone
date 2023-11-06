#
import os, sys
_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f"{_appPath}", "py_packages")
if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    sys.path.insert(0, "")
