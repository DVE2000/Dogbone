# Globals

import adsk.core
import adsk.fusion
# try:
_app = adsk.core.Application.get()
_design: adsk.fusion.Design = _app.activeProduct
_ui = _app.userInterface
_rootComp = _design.rootComponent
    
# except RuntimeError:
#     _app = None
#     _design = None
#     _ui = None
#     _rootComp = None

