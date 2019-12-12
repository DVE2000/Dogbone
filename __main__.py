import sys, os

appPath = os.path.dirname(os.path.abspath(__file__))
if appPath not in sys.path:
    sys.path.insert(0, appPath[0])