import adsk.fusion, adsk.cam, adsk.core
from typing import cast
from contextlib import contextmanager
from .constants import DB_GROUP, DB_NAME
from .errors import UpdateError

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)
_cam: adsk.cam.CAM = cast(adsk.cam.CAM, _app.activeProduct)
_ui: adsk.core.UserInterface = _app.userInterface

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
        bodiesMissing = False
        yield

    except UpdateError:
        bodiesMissing = True

    finally:
        _design.timeline.item(startPosition-1).rollTo(False)
        parentGroup.isCollapsed = isCollapsed
        if bodiesMissing:
            parentGroup.isCollapsed = True
            parentGroup.deleteMe(deleteGroupAndContents=True)
        refresh()

def refresh():
    pass


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
