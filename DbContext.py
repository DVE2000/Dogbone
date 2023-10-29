import adsk.fusion, adsk.cam, adsk.core
from typing import cast
from contextlib import contextmanager
from .constants import DB_GROUP, DB_NAME
from pynput.keyboard import Key, Controller  #imported as a workaround for refresh problem in manufacturing model edit and editing 

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)
_cam: adsk.cam.CAM = cast(adsk.cam.CAM, _app.activeProduct)
_ui: adsk.core.UserInterface = _app.userInterface

kbd: Controller = Controller()

@contextmanager
def baseFeatureContext(baseFeature: adsk.fusion.BaseFeature):
    global _app, _design
    try:
        bfTLO = baseFeature.timelineObject
        parentGroup = bfTLO.parentGroup
        isCollapsed =parentGroup.isCollapsed
        parentGroup.isCollapsed =False 
        startPosition = _design.timeline.markerPosition
        bfTLO.rollTo(False)
        yield

    finally:
        _design.timeline.item(startPosition-1).rollTo(False)
        parentGroup.isCollapsed = isCollapsed
        refresh()

def refresh():
    if _app.activeProduct.workspaces.itemById("MfgWorkingModelEnv").isActive:
        pass


        # currentId = [x.id for x in _app.activeProduct.workspaces if x.isActive][0]
        # _ui.workspaces.itemById("CAMEnvironment").activate()
        # _cam: adsk.can.CAM = cast(adsk.cam.CAM, _app.activeProduct)
        # _cam.manufacturingModels.itemById(currentId).activate()



@contextmanager
def groupContext():
    global _design
    _app = adsk.core.Application.get()
    _design = cast(adsk.fusion.Design, _app.activeProduct)
    try:
        startTlMarker = _design.timeline.markerPosition
        yield

    finally:
        endTlMarker = _design.timeline.markerPosition - 1

        if endTlMarker - startTlMarker > 0:
            timelineGroup = _design.timeline.timelineGroups.add(
                startTlMarker, 
                endTlMarker
            )
            timelineGroup.name = DB_NAME
        refresh()
