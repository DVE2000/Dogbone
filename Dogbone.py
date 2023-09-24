# Author-Peter Ludikar, Gary Singer
# Description-An Add-In for making dog-bone fillets.

# Peter completely revamped the dogbone add-in by Casey Rogers and Patrick Rainsberry and David Liu
# Some of the original utilities have remained, but a lot of the other functionality has changed.

# The original add-in was based on creating sketch points and extruding - Peter found using sketches and extrusion to be very heavy
# on processing resources, so this version has been designed to create dogbones directly by using a hole tool. So far the
# the performance of this approach is day and night compared to the original version.

# Select the face you want the dogbones to drop from. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diamater equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.
import logging
import os
import sys



_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f"{_appPath}", "py_packages")
if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    sys.path.insert(0, "")

from .UserParameter import create_user_parameter, DB_RADIUS, DB_HOLE_OFFSET
from .log import logger
from .Selection import Selection

import time
import traceback
from math import sqrt as sqrt
from typing import cast

import adsk.core
import adsk.fusion

from . import dbutils as dbUtils
from .DbData import DbParams
from .DogboneUi import DogboneUi
from .decorators import eventHandler
from .util import makeNative, reValidateFace

# Globals
_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)
_ui = _app.userInterface
_rootComp = _design.rootComponent

# constants - to keep attribute group and names consistent
DOGBONE_GROUP = "dogBoneGroup"
# FACE_ID = 'faceID'
REV_ID = "revId"
ID = "id"
DEBUGLEVEL = logging.DEBUG

COMMAND_ID = "dogboneBtn"
CONFIG_PATH = os.path.join(_appPath, "defaults.dat")


# noinspection PyMethodMayBeStatic
class DogboneCommand(object):
    # REFRESH_COMMAND_ID = "refreshDogboneBtn"

    registeredEdgesDict = {}

    def __init__(self):
        # set in various methods, but should be initialized in __init__
        self.selections = None

        # TODO: check where this is used and find the correct place
        self.faceSelections = adsk.core.ObjectCollection.create()

    def run(self, context):
        try:
            self.cleanup_commands()
            self.register_commands()
        except Exception as e:
            logger.exception(e)
            raise e

    def stop(self, context):
        try:
            self.cleanup_commands()
        except Exception as e:
            logger.exception(e)
            raise e

    def write_defaults(self, param: DbParams):
        logger.info("config file write")
        self.write_file(CONFIG_PATH, param.to_json())

    def write_file(self, path: str, data: str):
        with open(path, "w", encoding="UTF-8") as file:
            file.write(data)

    def read_file(self, path: str) -> str:
        with open(path, "r", encoding="UTF-8") as file:
            return file.read()

    def read_defaults(self) -> DbParams:
        logger.info("config file read")

        if not os.path.isfile(CONFIG_PATH):
            return DbParams()

        try:
            json = self.read_file(CONFIG_PATH)
            return DbParams().from_json(json)
        except ValueError:
            return DbParams()

    def debugFace(self, face):
        if logger.level < logging.DEBUG:
            return
        for edge in face.edges:
            logger.debug(
                f"edge {edge.tempId}; startVertex: {edge.startVertex.geometry.asArray()}; endVertex: {edge.endVertex.geometry.asArray()}"
            )

        return

    def register_commands(self):

        # Create button definition and command event handler
        button = _ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            "Dogbone",
            "Creates dogbones at all inside corners of a face",
            "resources"
        )

        self.onCreate(event=button.commandCreated)
        # Create controls for Manufacturing Workspace

        control = self.get_solid_create_panel().controls.addCommand(
            button, COMMAND_ID
        )

        # Make the button available in the Mfg panel.
        control.isPromotedByDefault = True
        control.isPromoted = True

        # Create controls for the Design Workspace
        createPanel = _ui.allToolbarPanels.itemById("SolidCreatePanel")
        buttonControl = createPanel.controls.addCommand(button, COMMAND_ID)

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

    def get_solid_create_panel(self):
        env = _ui.workspaces.itemById("MfgWorkingModelEnv")
        tab = env.toolbarTabs.itemById("MfgSolidTab")
        return tab.toolbarPanels.itemById("SolidCreatePanel")

    def cleanup_commands(self):
        self.remove_from_all()
        self.remove_from_solid()
        self.remove_command_definition()

    def remove_from_all(self):
        panel = _ui.allToolbarPanels.itemById("SolidCreatePanel")
        if not panel:
            return

        command = panel.controls.itemById(COMMAND_ID)
        command and command.deleteMe()

    def remove_from_solid(self):
        control = self.get_solid_create_panel().controls.itemById(COMMAND_ID)
        control and control.deleteMe()

    def remove_command_definition(self):
        if cmdDef := _ui.commandDefinitions.itemById(COMMAND_ID):
            cmdDef.deleteMe()

    @eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
    def onCreate(self, args: adsk.core.CommandCreatedEventArgs):
        """
        important persistent variables:
        self.selectedOccurrences  - Lookup dictionary
        key: activeOccurrenceId - hash of entityToken
        value: list of selectedFaces (DbFace objects)
            provides a quick lookup relationship between each occurrence and in particular which faces have been selected.

        self.selectedFaces - Lookup dictionary
        key: faceId =  - hash of entityToken
        value: [DbFace objects, ....]

        self.selectedEdges - reverse lookup
        key: edgeId - hash of entityToken
        value: [DbEdge objects, ....]
        """
        # inputs:adsk.core.CommandCreatedEventArgs = args
        self.faceSelections.clear()

        if _design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
            returnValue = _ui.messageBox(
                "DogBone only works in Parametric Mode \n Do you want to change modes?",
                "Change to Parametric mode",
                adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                adsk.core.MessageBoxIconTypes.WarningIconType,
            )
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            _design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        params = self.read_defaults()
        cmd: adsk.core.Command = args.command
        ui = DogboneUi(params, cmd, self.createDogbones)

    def createDogbones(self, params: DbParams, selection: Selection):
        start = time.time()

        # logger.log(0, "logging Level = %(levelname)")
        # self.parseInputs(args.firingEvent.sender.commandInputs)
        # logger.setLevel(self.param.logging)

        self.write_defaults(params)

        if params.parametric:
            self.createParametricDogbones(params, selection)
        else:  # Static dogbones
            self.createStaticDogbones(params, selection)

        logger.info(
            "all dogbones complete\n-------------------------------------------\n"
        )

        self.closeLogger()

        if params.benchmark:
            dbUtils.messageBox(
                f"Benchmark: {time.time() - start:.02f} sec processing {len(self.edges)} edges"
            )

    # ==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    # ==============================================================================

    def closeLogger(self):
        for handler in logger.handlers:
            handler.flush()
            handler.close()

    @property
    def originPlane(self):
        return (
            _rootComp.xZConstructionPlane if self.yUp else _rootComp.xYConstructionPlane
        )

    # The main algorithm for parametric dogbones
    def createParametricDogbones(self, param: DbParams, selection: Selection):

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

            for selectedFace in occurrenceFaces:
                if len(selectedFace.selectedEdges) < 1:
                    logger.debug("Face has no edges")

                face = selectedFace.native

                if not face.isValid:
                    logger.debug("revalidating Face")
                    face = selectedFace.revalidate()
                logger.debug(f"Processing Face = {face.tempId}")

                # faceNormal = dbUtils.getFaceNormal(face.nativeObject)
                if param.fromTop:
                    logger.debug(f"topFace type {type(topFace)}")
                    if not topFace.isValid:
                        logger.debug("revalidating topFace")
                        topFace = reValidateFace(comp, topFaceRefPoint)

                    topFace = makeNative(topFace)

                    logger.debug(f"topFace isValid = {topFace.isValid}")
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(
                        face, topFace
                    )
                    logger.debug(
                        f"creating transformVector to topFace = ({transformVector.x},{transformVector.y},{transformVector.z}) length = {transformVector.length}"
                    )

                for selectedEdge in selectedFace.selectedEdges:
                    logger.debug(f"Processing edge - {selectedEdge.edge.tempId}")

                    if not selectedEdge.isSelected:
                        logger.debug("  Not selected. Skipping...")
                        continue

                    if not face.isValid:
                        logger.debug("Revalidating face")
                        face = (
                            selectedFace.revalidate()
                        )  # = reValidateFace(comp, selectedFace.refPoint)

                    if not selectedEdge.edge.isValid:
                        continue  # edges that have been processed already will not be valid any more - at the moment this is easier than removing the
                    #                    affected edge from self.edges after having been processed
                    edge = selectedEdge.native
                    try:
                        if not dbUtils.isEdgeAssociatedWithFace(face, edge):
                            continue  # skip if edge is not associated with the face currently being processed
                    except:
                        pass

                    startVertex: adsk.fusion.BRepVertex = dbUtils.getVertexAtFace(
                        face, edge
                    )
                    extentToEntity = dbUtils.findExtent(face, edge)

                    extentToEntity = makeNative(extentToEntity)
                    logger.debug(f"extentToEntity - {extentToEntity.isValid}")
                    if not extentToEntity.isValid:
                        logger.debug("To face invalid")

                    try:
                        (edge1, edge2) = dbUtils.getCornerEdgesAtFace(face, edge)
                    except:
                        logger.exception("Failed at findAdjecentFaceEdges")
                        dbUtils.messageBox(
                            f"Failed at findAdjecentFaceEdges:\n{traceback.format_exc()}"
                        )

                    centrePoint = makeNative(startVertex).geometry.copy()

                    selectedEdgeFaces = makeNative(selectedEdge.edge).faces

                    dirVect: adsk.core.Vector3D = dbUtils.getFaceNormal(
                        selectedEdgeFaces[0]
                    ).copy()
                    dirVect.add(dbUtils.getFaceNormal(selectedEdgeFaces[1]))
                    dirVect.normalize()
                    dirVect.scaleBy(
                        centreDistance
                    )  # ideally radius should be linked to parameters,

                    if param.dbType == "Mortise Dogbone":
                        direction0 = dbUtils.correctedEdgeVector(edge1, startVertex)
                        direction1 = dbUtils.correctedEdgeVector(edge2, startVertex)

                        if self.longSide:
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
                        dirVect: adsk.core.Vector3D = dbUtils.getFaceNormal(
                            makeNative(selectedEdgeFaces[0])
                        ).copy()
                        dirVect.add(
                            dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[1]))
                        )
                        edge1OffsetByStr = offsetByStr
                        edge2OffsetByStr = offsetByStr

                    centrePoint.translateBy(dirVect)
                    logger.debug(
                        f"centrePoint = ({centrePoint.x},{centrePoint.y},{centrePoint.z})"
                    )

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
                    holeInput.participantBodies = [makeNative(face.body)]

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
                    holeInput.setOneSideToExtent(extentToEntity, False)
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

    def createStaticDogbones(self, param: DbParams, selection: Selection):
        logger.info("Creating static dogbones")

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

        for occurrenceFaces in selection.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition
            topFace = None

            if param.fromTop:
                topFace, topFaceRefPoint = dbUtils.getTopFace(occurrenceFaces[0].native)
                logger.debug(f"topFace ref point: {topFaceRefPoint.asArray()}")
                logger.info(f"Processing holes from top face - {topFace.tempId}")
                self.debugFace(topFace)

            for selectedFace in occurrenceFaces:
                toolCollection = adsk.core.ObjectCollection.create()
                toolBodies = None

                for edge in selectedFace.selectedEdges:
                    if not toolBodies:
                        toolBodies = edge.getToolBody(
                            params=param, topFace=topFace
                        )
                    else:
                        tempBrepMgr.booleanOperation(
                            toolBodies,
                            edge.getToolBody(params=param, topFace=topFace),
                            adsk.fusion.BooleanTypes.UnionBooleanType,
                        )

                baseFeatures = _rootComp.features.baseFeatures
                baseFeature = baseFeatures.add()
                baseFeature.name = "dogbone"

                baseFeature.startEdit()
                dbB = _rootComp.bRepBodies.add(toolBodies, baseFeature)
                dbB.name = "dogboneTool"
                baseFeature.finishEdit()

                toolCollection.add(baseFeature.bodies.item(0))

                activeBody = selectedFace.native.body

                combineInput = _rootComp.features.combineFeatures.createInput(
                    targetBody=activeBody, toolBodies=toolCollection
                )
                combineInput.isKeepToolBodies = False
                combineInput.isNewComponent = False
                combineInput.operation = (
                    adsk.fusion.FeatureOperations.CutFeatureOperation
                )
                combine = _rootComp.features.combineFeatures.add(combineInput)

            endTlMarker = _design.timeline.markerPosition - 1
            if endTlMarker - startTlMarker > 0:
                timelineGroup = _design.timeline.timelineGroups.add(
                    startTlMarker, endTlMarker
                )
                timelineGroup.name = "dogbone"


dog = DogboneCommand()


def run(context):
    try:
        dog.run(context)
    except Exception as e:
        logger.exception(e)
        dbUtils.messageBox(traceback.format_exc())


def stop(context):
    try:
        _ui.terminateActiveCommand()
        adsk.terminate()
        dog.stop(context)
    except Exception as e:
        logger.exception(e)
        dbUtils.messageBox(traceback.format_exc())
