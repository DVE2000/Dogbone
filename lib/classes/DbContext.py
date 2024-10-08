import adsk.fusion, adsk.cam, adsk.core
from contextlib import contextmanager
from ...constants import DB_NAME

@contextmanager
def baseFeatureContext(baseFeature: adsk.fusion.BaseFeature):
    app = adsk.core.Application.get()
    design: adsk.fusion.Design = app.activeProduct
    try:
        bfTLO = baseFeature.timelineObject
        parentGroup = bfTLO.parentGroup
        isCollapsed =parentGroup.isCollapsed
        parentGroup.isCollapsed =False 
        startPosition = design.timeline.markerPosition
        bfTLO.rollTo(False)
        yield

    finally:
        design.timeline.item(startPosition-1).rollTo(False)
        parentGroup.isCollapsed = isCollapsed
        refresh()

def refresh():
    app = adsk.core.Application.get()
    design: adsk.fusion.Design = app.activeProduct
    if app.activeProduct.workspaces.itemById("MfgWorkingModelEnv").isActive:
        pass

@contextmanager
def groupContext():
    app = adsk.core.Application.get()
    design: adsk.fusion.Design = app.activeProduct
    try:
        startTlMarker = design.timeline.markerPosition
        yield

    finally:
        endTlMarker = design.timeline.markerPosition - 1

        if endTlMarker - startTlMarker > 0:
            timelineGroup = design.timeline.timelineGroups.add(
                startTlMarker, 
                endTlMarker
            )
            timelineGroup.name = DB_NAME
        refresh()
