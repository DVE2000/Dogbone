import json

import adsk.core
import adsk.fusion

from ...lib.utils import debugFace, getTopFace 
from ...lib.classes import DbParams, Selection, groupContext 

from ...lib.common.log import logging
# from ...lib.utils import makeNative, reValidateFace
from ...constants import DB_GROUP, DB_NAME

logger = logging.getLogger('dogbone.createCommand.main')

def createStaticDogbones(param: DbParams, selection: Selection):

    logger.info("Creating static dogbones")

    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    for occurrenceFaces in selection.selectedOccurrences.values():
        with groupContext():
            topFace = None
            toolBodies = None

            if param.fromTop:
                topFace, topFaceRefPoint = getTopFace(occurrenceFaces[0].native)
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

