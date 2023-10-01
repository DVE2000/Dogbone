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

from .log import logger
from .DbClasses import Selection

import time
import traceback
from typing import cast

<<<<<<< HEAD
=======
import adsk.core
import adsk.fusion

import traceback

import time
from . import dbutils as dbUtils
from .decorators import eventHandler, parseDecorator
from math import sqrt as sqrt

# Globals
_app = adsk.core.Application.get()
_design = _app.activeProduct
_ui = _app.userInterface
_rootComp = _design.rootComponent
>>>>>>> 3932879 (found and corrected combine error  - 99% sure it's an F360 issue)
_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f"{_appPath}", "py_packages")
if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    sys.path.insert(0, "")
from .DbClasses import DbFace
from .DbData import DbParams

from .log import logger
from .DbClasses import Selection

import time
import traceback
from typing import cast

import adsk.core
import adsk.fusion

from . import dbutils as dbUtils
from .DbData import DbParams
from .DogboneUi import DogboneUi
from .decorators import eventHandler
from .createDogbone import createParametricDogbones, createStaticDogbones

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

<<<<<<< HEAD
    def run(self, context):
=======
    param = DbParams()
    registeredEdgesDict = {}

    faces = []
    edges = []

    selectedOccurrences = {}  # key hash(occurrence.entityToken) value:[DbFace,...]
    selectedFaces = {}  # key: hash(face.entityToken) value:[DbFace,...]
    selectedEdges = {}  # kay: hash(edge.entityToken) value:[DbEdge, ...]

    def __init__(self):
        # set in various methods, but should be initialized in __init__
        self.offset = None
        self.radius = None
        self.selections = None
        self.errorCount = None

        self.faceSelections = adsk.core.ObjectCollection.create()
        self.param = DbParams()
        self.loggingLevels = {
            "Notset": 0,
            "Debug": 10,
            "Info": 20,
            "Warning": 30,
            "Error": 40,
        }

        self.levels = {}
        self.logger = logging.getLogger("dogbone")

        for handler in self.logger.handlers:
            handler.flush()
            handler.close()
            self.logger.removeHandler(handler)

        self.formatter = logging.Formatter(
            "%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s"
        )
        self.logHandler = logging.FileHandler(
            os.path.join(_appPath, "dogbone.log"), mode="a"
        )
        self.logHandler.setFormatter(self.formatter)
        self.logHandler.flush()
        self.logger.addHandler(self.logHandler)

        self.logger.debug("\n"*3 + "*"*80)

        # for _ in ("decorators"):
        #     self.logger.getLogger(_).setLevel(logging.NOTSET)

    def writeDefaults(self):
        self.logger.info("config file write")

        json_file = open(os.path.join(_appPath, "defaults.dat"), "w", encoding="UTF-8")
        json_file.write(self.param.to_json())
        json_file.close()

    def readDefaults(self):
        self.logger.info("config file read")
        if not os.path.isfile(os.path.join(_appPath, "defaults.dat")):
            return
        json_file = open(os.path.join(_appPath, "defaults.dat"), "r", encoding="UTF-8")
        jsonString = json_file.read()
>>>>>>> 3932879 (found and corrected combine error  - 99% sure it's an F360 issue)
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

<<<<<<< HEAD
    def register_commands(self):
=======
    def debugFace(self, face):
        if self.logger.level < logging.DEBUG:
            return
        for edge in face.edges:
            sx,sy,sz = edge.startVertex.geometry.asArray()
            ex,ey,ez = edge.endVertex.geometry.asArray()

            self.logger.debug(
                f"\nFace - native"
                f"\nedge: {edge.tempId}"
                f"\nstartVertex:({sx:.2f},{sy:.2f},{sz:.2f}) endVertex: ({ex:.2f},{ey:.2f},{ez:.2f})"
            )

        # for edge in face.nativeObject.edges:
        #     sx,sy,sz = edge.startVertex.geometry.asArray()
        #     ex,ey,ez = edge.endVertex.geometry.asArray()
            
        #     self.logger.debug(
        #         f"\nFace - Native"
        #         f"\nedge: {edge.tempId}"
        #         f"\nstartVertex:({sx:.2f},{sy:.2f},{sz:.2f}) endVertex: ({ex:.2f},{ey:.2f},{ez:.2f})"
        #     )

        return

    # def addRefreshButton(self):
    #     try:
    #     # clean up any crashed instances of the button if existing
    #         self.removeButton()
    #     except:
    #         pass

    #     # Create button definition and command event handler
    #     refreshButtonDogbone = _ui.commandDefinitions.addButtonDefinition(
    #         self.REFRESH_COMMAND_ID,
    #         'DogboneRefresh',
    #         'Refreshes already created dogbones',
    #         'Resources')

    #     self.onRefreshCreate(event=refreshButtonDogbone.commandCreated)
    #     # Create controls for Manufacturing Workspace
    #     mfgEnv = _ui.workspaces.itemById('MfgWorkingModelEnv')
    #     mfgTab = mfgEnv.toolbarTabs.itemById('MfgSolidTab')
    #     mfgSolidPanel = mfgTab.toolbarPanels.itemById('SolidCreatePanel')
    #     buttonControlMfg = mfgSolidPanel.controls.addCommand(refreshButtonDogbone, 'refreshDogboneBtn')

    #     # Make the button available in the Mfg panel.
    #     buttonControlMfg.isPromotedByDefault = True
    #     buttonControlMfg.isPromoted = True

    #     # Create controls for the Design Workspace
    #     createPanel = _ui.allToolbarPanels.itemById('SolidCreatePanel')
    #     buttonControl = createPanel.controls.addCommand(refreshButtonDogbone, 'refreshDogboneBtn')

    #     # Make the button available in the panel.
    #     buttonControl.isPromotedByDefault = True
    #     buttonControl.isPromoted = True

    def addButton(self):
        try:
            # clean up any crashed instances of the button if existing
            self.removeButton()
        except:
            pass
>>>>>>> 3932879 (found and corrected combine error  - 99% sure it's an F360 issue)

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
<<<<<<< HEAD
=======
        self.readDefaults()

        self.edges = []
        self.faces = []
        self.selectedEdges = {}
        self.selectedFaces = {}
        self.selectedOccurrences = {}

        inputs: adsk.core.CommandInputs = args.command.commandInputs

        selInput0 = inputs.addSelectionInput(
            "faceSelect",
            "Face",
            "Select a face to apply dogbones to all internal corner edges",
        )
        selInput0.tooltip = "Select a face to apply dogbones to all internal corner edges\n*** Select faces by clicking on them. DO NOT DRAG SELECT! ***"
        selInput0.addSelectionFilter("PlanarFaces")
        selInput0.setSelectionLimits(1, 0)

        selInput1 = inputs.addSelectionInput(
            "edgeSelect",
            "DogBone Edges",
            "SELECT OR de-SELECT ANY internal edges dropping down FROM a selected face (TO apply dogbones TO",
        )
        selInput1.tooltip = "SELECT OR de-SELECT ANY internal edges dropping down FROM a selected face (TO apply dogbones TO)"
        selInput1.addSelectionFilter("LinearEdges")
        selInput1.setSelectionLimits(1, 0)
        selInput1.isVisible = False

        inp = inputs.addValueInput(
            "toolDia",
            "Tool Dia               ",
            _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaStr),
        )
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."

        offsetInp = inputs.addValueInput(
            "toolDiaOffset",
            "Tool diameter offset",
            _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaOffsetStr),
        )
        offsetInp.tooltip = "Increases the tool diameter"
        offsetInp.tooltipDescription = (
            "Use this to create an oversized dogbone.\n"
            "Normally set to 0.  \n"
            "A value of .010 would increase the dogbone diameter by .010 \n"
            "Used when you want to keep the tool diameter and oversize value separate"
        )

        modeGroup: adsk.core.GroupCommandInput = inputs.addGroupCommandInput(
            "modeGroup", "Mode"
        )
        modeGroup.isExpanded = self.param.expandModeGroup
        modeGroupChildInputs = modeGroup.children

        modeRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput("modeRow", "Mode", False)
        )
        modeRowInput.listItems.add(
            "Static", not self.param.parametric, "resources/staticMode"
        )
        modeRowInput.listItems.add(
            "Parametric", self.param.parametric, "resources/parametricMode"
        )
        modeRowInput.tooltipDescription = (
            "Static dogbones do not move with the underlying component geometry. \n"
            "\nParametric dogbones will automatically adjust position with parametric changes to underlying geometry. "
            "Geometry changes must be made via the parametric dialog.\nFusion has more issues/bugs with these!"
        )

        typeRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput("dogboneType", "Type", False)
        )
        typeRowInput.listItems.add(
            "Normal Dogbone", self.param.dbType == "Normal Dogbone", "resources/normal"
        )
        typeRowInput.listItems.add(
            "Minimal Dogbone",
            self.param.dbType == "Minimal Dogbone",
            "resources/minimal",
        )
        typeRowInput.listItems.add(
            "Mortise Dogbone",
            self.param.dbType == "Mortise Dogbone",
            "resources/hidden",
        )
        typeRowInput.tooltipDescription = (
            "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit "
            "that, for example, will require a larger force to insert a tenon into a mortise.\n"
            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n"
            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        )

        mortiseRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput(
                "mortiseType", "Mortise Type", False
            )
        )
        mortiseRowInput.listItems.add(
            "On Long Side", self.param.longSide, "resources/hidden/longSide"
        )
        mortiseRowInput.listItems.add(
            "On Short Side", not self.param.longSide, "resources/hidden/shortside"
        )
        mortiseRowInput.tooltipDescription = (
            "Along Longest will have the dogbones cut into the longer sides."
            "\nAlong Shortest will have the dogbones cut into the shorter sides."
        )
        mortiseRowInput.isVisible = self.param.dbType == "Mortise Dogbone"

        minPercentInp = modeGroupChildInputs.addValueInput(
            "minimalPercent",
            "Percentage Reduction",
            "",
            adsk.core.ValueInput.createByReal(self.param.minimalPercent),
        )
        minPercentInp.tooltip = "Percentage of tool radius added to push out dogBone - leaves actual corner exposed"
        minPercentInp.tooltipDescription = "This should typically be left at 10%, but if the fit is too tight, it should be reduced"
        minPercentInp.isVisible = self.param.dbType == "Minimal Dogbone"

        depthRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput(
                "depthExtent", "Depth Extent", False
            )
        )
        depthRowInput.listItems.add(
            "From Selected Face", not self.param.fromTop, "resources/fromFace"
        )
        depthRowInput.listItems.add(
            "From Top Face", self.param.fromTop, "resources/fromTop"
        )
        depthRowInput.tooltipDescription = (
            'When "From Top Face" is selected, all dogbones will be extended to the top most face\n'
            "\nThis is typically chosen when you don't want to, or can't do, double sided machining."
        )

        angleDetectionGroupInputs: adsk.core.GroupCommandInput = (
            inputs.addGroupCommandInput("angleDetectionGroup", "Detection Mode")
        )
        angleDetectionGroupInputs.isExpanded = self.param.angleDetectionGroup

        angleDetectionGroupInputs.isVisible = (
            not self.param.parametric
        )  # disables angle selection if in parametric mode

        enableAcuteAngleInput: adsk.core.BoolValueCommandInput = (
            angleDetectionGroupInputs.children.addBoolValueInput(
                "acuteAngle", "Acute Angle", True, "", self.param.acuteAngle
            )
        )
        enableAcuteAngleInput.tooltip = (
            "Enables detection of corner angles less than 90"
        )
        minAngleSliderInput: adsk.core.FloatSliderCommandInput = (
            angleDetectionGroupInputs.children.addFloatSliderCommandInput(
                "minSlider", "Min Limit", "", 10.0, 89.0
            )
        )
        minAngleSliderInput.isVisible = self.param.acuteAngle
        minAngleSliderInput.valueOne = self.param.minAngleLimit

        enableObtuseAngleInput: adsk.core.BoolValueCommandInput = (
            angleDetectionGroupInputs.children.addBoolValueInput(
                "obtuseAngle", "Obtuse Angle", True, "", self.param.obtuseAngle
            )
        )  #
        enableObtuseAngleInput.tooltip = (
            "Enables detection of corner angles greater than 90"
        )

        maxAngleSliderInput: adsk.core.FloatSliderCommandInput = (
            angleDetectionGroupInputs.children.addFloatSliderCommandInput(
                "maxSlider", "Max Limit", "", 91.0, 170.0
            )
        )
        maxAngleSliderInput.isVisible = self.param.obtuseAngle
        maxAngleSliderInput.valueOne = self.param.maxAngleLimit

        settingGroup: adsk.core.GroupCommandInput = inputs.addGroupCommandInput(
            "settingsGroup", "Settings"
        )
        settingGroup.isExpanded = self.param.expandSettingsGroup
        settingGroupChildInputs = settingGroup.children

        benchMark = settingGroupChildInputs.addBoolValueInput(
            "benchmark", "Benchmark time", True, "", self.param.benchmark
        )
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = (
            "When enabled, shows overall time taken to process all selected dogbones."
        )

        logDropDownInp: adsk.core.DropDownCommandInput = (
            settingGroupChildInputs.addDropDownCommandInput(
                "logging",
                "Logging level",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
        )
        logDropDownInp.tooltip = "Enables logging"
        logDropDownInp.tooltipDescription = (
            "Creates a dogbone.log file. \n"
            f"Location: {os.path.join(_appPath, 'dogBone.log')}"
        )

        logDropDownInp.listItems.add("Notset", self.param.logging == 0)
        logDropDownInp.listItems.add("Debug", self.param.logging == 10)
        logDropDownInp.listItems.add("Info", self.param.logging == 20)
>>>>>>> 3932879 (found and corrected combine error  - 99% sure it's an F360 issue)

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
            createParametricDogbones(params, selection)
        else:  # Static dogbones
            createStaticDogbones(params, selection)

        logger.info(
            "all dogbones complete\n-------------------------------------------\n"
        )

        self.closeLogger()

        if params.benchmark:
            dbUtils.messageBox(
                f"Benchmark: {time.time() - start:.02f} sec processing {len(selection.edges)} edges"
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

<<<<<<< HEAD
=======
    # The main algorithm for parametric dogbones
    def createParametricDogbones(self):
        self.logger.info("Creating parametric dogbones")
        self.errorCount = 0
        if not _design:
            raise RuntimeError("No active Fusion design")
        holeInput: adsk.fusion.HoleFeatureInput = None
        offsetByStr = adsk.core.ValueInput.createByString("dbHoleOffset")
        centreDistance = self.radius * (
            1 + self.param.minimalPercent / 100
            if self.param.dbType == "Minimal Dogbone"
            else 1
        )

        for occurrenceFaces in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition

            comp: adsk.fusion.Component = occurrenceFaces[0].component
            occ: adsk.fusion.Occurrence = occurrenceFaces[0].occurrence

            if self.param.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(
                    occurrenceFaces[0].native
                )
                self.logger.info(
                    f"Processing holes from top face - {topFace.body.name}"
                )

            for selectedFace in occurrenceFaces:
                if len(selectedFace.selectedEdges) < 1:
                    self.logger.debug("Face has no edges")

                face = selectedFace.native

                if not face.isValid:
                    self.logger.debug("revalidating Face")
                    face = selectedFace.revalidate()
                self.logger.debug(f"Processing Face = {face.tempId}")

                # faceNormal = dbUtils.getFaceNormal(face.nativeObject)
                if self.param.fromTop:
                    self.logger.debug(f"topFace type {type(topFace)}")
                    if not topFace.isValid:
                        self.logger.debug("revalidating topFace")
                        topFace = reValidateFace(comp, topFaceRefPoint)

                    topFace = makeNative(topFace)

                    self.logger.debug(f"topFace isValid = {topFace.isValid}")
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(
                        face, topFace
                    )
                    self.logger.debug(
                        f"creating transformVector to topFace = ({transformVector.x},{transformVector.y},{transformVector.z}) length = {transformVector.length}"
                    )

                for selectedEdge in selectedFace.selectedEdges:
                    self.logger.debug(f"Processing edge - {selectedEdge.edge.tempId}")

                    if not selectedEdge.isSelected:
                        self.logger.debug("  Not selected. Skipping...")
                        continue

                    if not face.isValid:
                        self.logger.debug("Revalidating face")
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
                    self.logger.debug(f"extentToEntity - {extentToEntity.isValid}")
                    if not extentToEntity.isValid:
                        self.logger.debug("To face invalid")

                    try:
                        (edge1, edge2) = dbUtils.getCornerEdgesAtFace(face, edge)
                    except:
                        self.logger.exception("Failed at findAdjecentFaceEdges")
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

                    if self.param.dbType == "Mortise Dogbone":
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
                    self.logger.debug(
                        f"centrePoint = ({centrePoint.x},{centrePoint.y},{centrePoint.z})"
                    )

                    if self.param.fromTop:
                        centrePoint.translateBy(transformVector)
                        self.logger.debug(
                            f"centrePoint at topFace = {centrePoint.asArray()}"
                        )
                        holePlane = topFace if self.param.fromTop else face
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

                    self.logger.debug(
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
                    self.logger.debug(
                        f"extentToEntity after setPositionByPlaneAndOffsets - {extentToEntity.isValid}"
                    )
                    holeInput.setOneSideToExtent(extentToEntity, False)
                    self.logger.info(f"hole added to list - {centrePoint.asArray()}")

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
        # self.logger.debug('doEvents - allowing display to refresh')
        #            adsk.doEvents()

        if self.errorCount > 0:
            dbUtils.messageBox(
                f"Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created"
            )

    def createStaticDogbones(self):
        self.logger.info("Creating static dogbones")
        self.errorCount = 0
        if not _design:
            raise RuntimeError("No active Fusion design")

        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

        for occurrenceFaces in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition
            comp: adsk.fusion.Component = occurrenceFaces[0].component
            occ: adsk.fusion.Occurrence = occurrenceFaces[0].occurrence
            topFace = None

            if self.param.fromTop:
                topFace, topFaceRefPoint = dbUtils.getTopFace(occurrenceFaces[0].native)
                self.logger.debug(f"topFace ref point: {topFaceRefPoint.asArray()}")
                self.logger.info(f"Processing holes from top face - {topFace.tempId}")
                self.debugFace(topFace)

            for selectedFace in occurrenceFaces:
                component = selectedFace.component
                toolCollection = adsk.core.ObjectCollection.create()
                toolBodies = None

                for edge in selectedFace.selectedEdges:
                    if not toolBodies:
                        toolBodies = edge.getToolBody(
                            params=self.param,
                            topFace=topFace
                        )
                    else:
                        tempBrepMgr.booleanOperation(
                            toolBodies,
                            edge.getToolBody(params=self.param,
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
                self.logger.debug(f"combine: {combine.healthState}")

            endTlMarker = _design.timeline.markerPosition - 1
            if endTlMarker - startTlMarker > 0:
                timelineGroup = _design.timeline.timelineGroups.add(
                    startTlMarker, endTlMarker
                )
                timelineGroup.name = "dogbone"
        # self.logger.debug('doEvents - allowing fusion to refresh')
        #            adsk.doEvents()

        if self.errorCount > 0:
            dbUtils.messageBox(
                f"Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created"
            )

>>>>>>> 3932879 (found and corrected combine error  - 99% sure it's an F360 issue)

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
