import logging
import traceback
from typing import cast

import adsk.core
import adsk.fusion
from . import dbutils as dbUtils
from .DbData import DbParams
from .DbClasses import Selection
from .UserParameter import create_user_parameter, DB_RADIUS
from .log import logger
from .util import makeNative, reValidateFace

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)
_rootComp = _design.rootComponent


def debugFace(face):
    if logger.level < logging.DEBUG:
        return
    for edge in face.edges:
        logger.debug(
            f"edge {edge.tempId}; startVertex: {edge.startVertex.geometry.asArray()}; endVertex: {edge.endVertex.geometry.asArray()}"
        )


def createParametricDogbones(param: DbParams, selection: Selection):
    userParams = create_user_parameter(param)
    radius = userParams.itemByName(DB_RADIUS).value

    # TODO: offset is not used
    logger.info("Creating parametric dogbones")
    if not _design:
        raise RuntimeError("No active Fusion design")

    offsetByStr = adsk.core.ValueInput.createByString("dbHoleOffset")
    centreDistance = radius * (
        1 + param.minimalPercent / 100
        if param.dbType == "Minimal Dogbone"
        else 1
    )

    for occurrenceFaces in selection.selectedOccurrences.values():
        startTlMarker = _design.timeline.markerPosition

        comp: adsk.fusion.Component = occurrenceFaces[0].component

        if param.fromTop:
            (topFace, topFaceRefPoint) = dbUtils.getTopFace(
                occurrenceFaces[0].native
            )
            logger.info(
                f"Processing holes from top face - {topFace.body.name}"
            )

            logger.debug(f"topFace isValid = {topFace.isValid}")
            transformVector = dbUtils.getTranslateVectorBetweenFaces(
                face, topFace
            )
            logger.debug(
                f"creating transformVector to topFace = ({transformVector.x},{transformVector.y},{transformVector.z}) length = {transformVector.length}"
            )

            for selectedEdge in selection.selectedEdges:
                logger.debug(f"Processing edge - {selectedEdge.edge.tempId}")
                edge: adsk.fusion.BRepEdge = selectedEdge.native

                if not selectedEdge.isSelected:
                    logger.debug("  Not selected. Skipping...")
                    continue

                if not face.isValid:
                    logger.debug("Revalidating face")
                    face = (
                        selection.revalidate()
                    )  # = reValidateFace(comp, selection.refPoint)

                if not edge.isValid:
                    continue  # edges that have been processed already will not be valid any more - at the moment this is easier than removing the
                #                    affected edge from self.edges after having been processed
                try:
                    if not dbUtils.isEdgeAssociatedWithFace(face, edge):
                        continue  # skip if edge is not associated with the face currently being processed
                except:
                    pass

                extentToEntity = dbUtils.findExtent(face, edge)
                extentToEntity = [face for face in selectedEdge.endVertex.faces if selection.faceNormal.isParallelTo(dbUtils.getFaceNormal(face))][0]

                # extentToEntity = makeNative(extentToEntity)
                logger.debug(f"extentToEntity - {extentToEntity.isValid}")
                if not extentToEntity.isValid:
                    logger.debug("To face invalid")

                try:
                    edge1, edge2 = dbUtils.getCornerEdgesAtFace(face, edge)
                except:
                    logger.exception("Failed at findAdjecentFaceEdges")
                    dbUtils.messageBox(
                        f"Failed at findAdjecentFaceEdges:\n{traceback.format_exc()}"
                    )

                centrePoint: adsk.fusion.BRepVertex = selectedEdge.startVertex.geometry
                # centrePoint = startVertex.geometry.copy()

                #calculate center placement vector away from corner 
                selectedEdgeFaces = edge.faces

                dirVect: adsk.core.Vector3D = dbUtils.getFaceNormal(
                    selectedEdgeFaces[0]
                ).copy()
                dirVect.add(dbUtils.getFaceNormal(selectedEdgeFaces[1]))
                dirVect.normalize()
                dirVect.scaleBy(
                    centreDistance
                )  # ideally radius should be linked to parameters,

                if param.dbType == "Mortise Dogbone":
                    direction0 = dbUtils.correctedEdgeVector(edge1, selectedEdge.startVertex)
                    direction1 = dbUtils.correctedEdgeVector(edge2, selectedEdge.startVertex)

                    if param.longSide:
                        if edge1.length > edge2.length:
                            dirVect = direction0
                            edge1OffsetByStr = adsk.core.ValueInput.createByReal(0)
                            edge2OffsetByStr = offsetByStr
                        else:
                            dirVect = direction1
                            edge2OffsetByStr = adsk.core.ValueInput.createByReal(0)
                            edge1OffsetByStr = offsetByStr
                    else:
                        if edge1.length > edge2.length:
                            dirVect = direction1
                            edge2OffsetByStr = adsk.core.ValueInput.createByReal(0)
                            edge1OffsetByStr = offsetByStr
                        else:
                            dirVect = direction0
                            edge1OffsetByStr = adsk.core.ValueInput.createByReal(0)
                            edge2OffsetByStr = offsetByStr
                else:
                    dirVect: adsk.core.Vector3D = dbUtils.getFaceNormal(selectedEdgeFaces[0]).copy()
                    dirVect.add(
                        dbUtils.getFaceNormal(selectedEdgeFaces[1])
                    )
                    edge1OffsetByStr = offsetByStr
                    edge2OffsetByStr = offsetByStr

                centrePoint.translateBy(dirVect)
                logger.debug(
                    f"centrePoint = ({centrePoint.x},{centrePoint.y},{centrePoint.z})"
                )

                holeDirection = selection.faceNormal
                holeDirection.scaleBy(-1)

                if param.fromTop:
                    centrePoint.translateBy(transformVector)
                    logger.debug(
                        f"centrePoint at topFace = {centrePoint.asArray()}"
                    )
                    holePlane = topFace if param.fromTop else face
                    if not holePlane.isValid:
                        holePlane = reValidateFace(comp, topFaceRefPoint)
                else:
                    holePlane = makeNative(face)

                holes = comp.features.holeFeatures
                holeInput = holes.createSimpleInput(
                    adsk.core.ValueInput.createByString("dbRadius*2")
                )
                #                    holeInput.creationOccurrence = occ #This needs to be uncommented once AD fixes component copy issue!!
                holeInput.isDefaultDirection = True
                holeInput.tipAngle = adsk.core.ValueInput.createByString("180 deg")
                #                    holeInput.participantBodies = [face.nativeObject.body if occ else face.body]  #Restore this once AD fixes occurrence bugs
                holeInput.participantBodies = [face.body]

                logger.debug(
                    f"extentToEntity before setPositionByPlaneAndOffsets - {extentToEntity.isValid}"
                )
                holeInput.setPositionByPlaneAndOffsets(
                    holePlane,
                    centrePoint,
                    edge1,
                    edge1OffsetByStr,
                    edge2,
                    edge2OffsetByStr,
                )
                logger.debug(
                    f"extentToEntity after setPositionByPlaneAndOffsets - {extentToEntity.isValid}"
                )
                holeInput.setOneSideToExtent(extentToEntity, False, holeDirection)
                logger.info(f"hole added to list - {centrePoint.asArray()}")

                holeFeature = holes.add(holeInput)
                holeFeature.name = "dogbone"
                holeFeature.isSuppressed = True

            for hole in holes:
                if hole.name[:7] != "dogbone":
                    break
                hole.isSuppressed = False

        endTlMarker = _design.timeline.markerPosition - 1
        if endTlMarker - startTlMarker > 0:
            timelineGroup = _design.timeline.timelineGroups.add(
                startTlMarker, endTlMarker
            )
            timelineGroup.name = "dogbone"
    # logger.debug('doEvents - allowing display to refresh')
    #            adsk.doEvents()


def createStaticDogbones(param: DbParams, selection: Selection):
    logger.info("Creating static dogbones")

    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    for occurrenceFaces in selection.selectedOccurrences.values():
        startTlMarker = _design.timeline.markerPosition
        topFace = None
        toolBodies = None

        if param.fromTop:
            topFace, topFaceRefPoint = dbUtils.getTopFace(occurrenceFaces[0].native)
            logger.debug(f"topFace ref point: {topFaceRefPoint.asArray()}")
            logger.info(f"Processing holes from top face - {topFace.tempId}")
            debugFace(topFace)

        for selectedFace in occurrenceFaces:
            component = selectedFace.component
            toolCollection = adsk.core.ObjectCollection.create()

            for edge in selectedFace.selectedEdges:
                if not toolBodies:
                    toolBodies = edge.getToolBody(
                        params=param,
                        topFace=topFace
                    )
                else:
                    tempBrepMgr.booleanOperation(
                        toolBodies,
                        edge.getToolBody(params=param,
                                            topFace=topFace),
                        adsk.fusion.BooleanTypes.UnionBooleanType,
                    )

        targetBody: adsk.fusion.BRepBody = selectedFace.body
        baseFeatures = component.features.baseFeatures
        baseFeature = baseFeatures.add()
        baseFeature.name = "dogbone"

        baseFeature.startEdit()
        
        dbB = component.bRepBodies.add(toolBodies, baseFeature)
        dbB.name = "dogboneTool"

        baseFeature.finishEdit()

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
        combine = component.features.combineFeatures.add(combineFeatureInput)
        logger.debug(f"combine: {combine.healthState}")

        endTlMarker = _design.timeline.markerPosition - 1
        if endTlMarker - startTlMarker > 0:
            timelineGroup = _design.timeline.timelineGroups.add(
                startTlMarker, endTlMarker
            )
            timelineGroup.name = "dogbone"
