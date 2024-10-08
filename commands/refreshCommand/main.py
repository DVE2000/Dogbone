import json

import adsk.core
import adsk.fusion

# from ... import dbutils as dbUtils
from ...lib.classes import DbFace, baseFeatureContext 

from ...lib.utils import getTopFace
from ...constants import DB_GROUP


def updateDogBones():
    """
    Recalculates and updates existing dogbones
    
    """
    app = adsk.core.Application.get()
    design: adsk.fusion.Design = app.activeProduct #this should be dynamically set according to the Product/Design context!  
                                                                        # For the moment it works, but should be fixed in the future
    baseFeaturesAttrs: adsk.core.Attributes = design.findAttributes(DB_GROUP, "re:basefeature:.*")

    for bfAttr in baseFeaturesAttrs:

        baseFeature: adsk.fusion.BaseFeature = bfAttr.parent
        faces = json.loads(bfAttr.value)
        faceList = '|'.join(map(str, faces))
        regex = "re:face:("+faceList+")"
        faceAttrs = design.findAttributes(DB_GROUP, regex)

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
        toolBodies = None
        
        with baseFeatureContext(baseFeature= baseFeature):
            for faceAtt in faceAttrs:
                if not faceAtt.parent:
                    continue
                selectedFace: DbFace = DbFace(face=faceAtt.parent,
                            restoreState=True)
                topFace, _ = getTopFace(selectedFace=selectedFace.face)
                topFace = topFace.nativeObject if topFace.nativeObject else topFace
                for edge in selectedFace.selectedEdges:
                    if not toolBodies:
                        toolBodies = edge.getToolBody(
                            topFace=topFace
                        )
                    else:
                        tempBrepMgr.booleanOperation(
                            toolBodies,
                            edge.getToolBody(topFace=topFace),
                            adsk.fusion.BooleanTypes.UnionBooleanType,
                        )
                if toolBodies:
                    [baseFeature.updateBody(body, toolBodies) for body in baseFeature.sourceBodies]

