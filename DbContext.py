import adsk.fusion
from typing import cast
from contextlib import contextmanager

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)

@contextmanager
def baseFeatureContext(baseFeature: adsk.fusion.BaseFeature):
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