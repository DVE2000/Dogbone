import logging
import traceback
import re
import json
from typing import cast

import adsk.core
import adsk.fusion
from . import dbutils as dbUtils
from .DbData import DbParams
from .DbClasses import Selection, DbFace
from .DbContext import baseFeatureContext, groupContext

from .UserParameter import create_user_parameter, DB_RADIUS
from .log import logger
from .util import makeNative, reValidateFace
from .constants import DB_GROUP, DB_NAME

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)#this should be dynamically set according to the Product/Design context!  
                                                                        #For the moment it works, but should be fixed in the futur

def debugFace(face):
    if logger.level < logging.DEBUG:
        return
    for edge in face.edges:
        logger.debug(
            f"edge {edge.tempId}; startVertex: {edge.startVertex.geometry.asArray()}; endVertex: {edge.endVertex.geometry.asArray()}"
        )


def createStaticDogbones(param: DbParams, selection: Selection):
    logger.info("Creating static dogbones")

    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    for occurrenceFaces in selection.selectedOccurrences.values():
        # startTlMarker = _design.timeline.markerPosition
        with groupContext():
            topFace = None
            toolBodies = None

            if param.fromTop:
                topFace, topFaceRefPoint = dbUtils.getTopFace(occurrenceFaces[0].native)
                logger.debug(f"topFace ref point: {topFaceRefPoint.asArray()}")
                logger.info(f"Processing holes from top face - {topFace.tempId}")
                debugFace(topFace)

            for selectedFace in occurrenceFaces:
                component = selectedFace.component
                selectedFace.save()
                toolCollection = adsk.core.ObjectCollection.create()

                for edgeObj in selectedFace.selectedEdges:
                    edgeObj.save()
                    if not toolBodies:
                        toolBodies = edgeObj.getToolBody(
                            topFace=topFace
                        )
                    else:
                        tempBrepMgr.booleanOperation(
                            toolBodies,
                            edgeObj.getToolBody(
                                topFace=topFace),
                            adsk.fusion.BooleanTypes.UnionBooleanType,
                        )

            targetBody: adsk.fusion.BRepBody = selectedFace.body
            baseFeatures: adsk.fusion.BaseFeature = component.features.baseFeatures
            baseFeature = baseFeatures.add()
            baseFeature.name = DB_NAME

            baseFeature.startEdit()
            
            dbB = component.bRepBodies.add(toolBodies, baseFeature)
            dbB.name = "dogboneTool"

            baseFeature.finishEdit()

            faces = [f.faceId for f in occurrenceFaces]

            baseFeature.attributes.add(groupName=DB_GROUP,
                                name="basefeature:",
                                value=json.dumps(faces))

            [toolCollection.add(body) for body in baseFeature.bodies]  #add baseFeature bodies into toolCollection

            combineFeatureInput = component.features.combineFeatures.createInput(
                targetBody=targetBody,
                toolBodies=toolCollection
            )

            combineFeatureInput.isKeepToolBodies = False
            combineFeatureInput.isNewComponent = False
            combineFeatureInput.operation = (
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            combine:adsk.fusion.CombineFeature = component.features.combineFeatures.add(combineFeatureInput)

            logger.debug(f"combine: {combine.name}")

def updateDogBones():
    """
    Recalculates and updates existing dogbones
    
    """
    baseFeaturesAttrs: adsk.core.Attributes = _design.findAttributes(DB_GROUP, "re:basefeature:.*")

    for bfAttr in baseFeaturesAttrs:

        baseFeature: adsk.fusion.BaseFeature = bfAttr.parent
        faces = json.loads(bfAttr.value)
        faceList = '|'.join(map(str, faces))
        regex = "re:face:("+faceList+")"
        faceAttrs = _design.findAttributes(DB_GROUP, regex)

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
        toolBodies = None
        
        with baseFeatureContext(baseFeature= baseFeature):
            for faceAtt in faceAttrs:
                if not faceAtt.parent:
                    continue
                selectedFace: DbFace = DbFace(face=faceAtt.parent,
                            restoreState=True)
                topFace, _ = dbUtils.getTopFace(selectedFace=selectedFace.face)
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

