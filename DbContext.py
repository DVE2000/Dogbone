import adsk.fusion, adsk.cam, adsk.core
from typing import cast
from contextlib import contextmanager
from .constants import DB_GROUP, DB_NAME

from . import globalvars as g

# _app = adsk.core.Application.get()
# _design: adsk.fusion.Design = _app.activeProduct
if g._app:
    _cam: adsk.cam.CAM = g._app.activeProduct
else:
    _cam = None
# _ui: adsk.core.UserInterface = _app.userInterface

@contextmanager
def baseFeatureContext(baseFeature: adsk.fusion.BaseFeature):
    # global g._app, g._design
    try:
        bfTLO = baseFeature.timelineObject
        parentGroup = bfTLO.parentGroup
        isCollapsed =parentGroup.isCollapsed
        parentGroup.isCollapsed =False 
        startPosition = g._design.timeline.markerPosition
        bfTLO.rollTo(False)
        yield

    finally:
        g._design.timeline.item(startPosition-1).rollTo(False)
        parentGroup.isCollapsed = isCollapsed
        refresh()

def refresh():
    if g._app.activeProduct.workspaces.itemById("MfgWorkingModelEnv").isActive:
        pass


        # currentId = [x.id for x in _app.activeProduct.workspaces if x.isActive][0]
        # _ui.workspaces.itemById("CAMEnvironment").activate()
        # _cam: adsk.can.CAM = cast(adsk.cam.CAM, _app.activeProduct)
        # _cam.manufacturingModels.itemById(currentId).activate()



@contextmanager
def groupContext():
    # global g._design
    _app = adsk.core.Application.get()
    _design = cast(adsk.fusion.Design, _app.activeProduct)
    try:
        startTlMarker = g._design.timeline.markerPosition
        yield

    finally:
        endTlMarker = g._design.timeline.markerPosition - 1

        if endTlMarker - startTlMarker > 0:
            timelineGroup = g._design.timeline.timelineGroups.add(
                startTlMarker, 
                endTlMarker
            )
            timelineGroup.name = DB_NAME
        refresh()
