"""Main create dogbone User Interface Dialog """
import os
from typing import cast

import adsk.core
import adsk.fusion
import logging

from ..utils import getFaceNormal
from . import DbParams, Selection, DbFace
from ..utils.decorators import eventHandler, parseDecorator
from ..common.log import LEVELS, startLogger, stopLogger
from ..utils.util import calcId
from ...constants import (
    ACUTE_ANGLE,
    ANGLE_DETECTION_GROUP,
    BENCHMARK,
    DEPTH_EXTENT,
    DOGBONE_TYPE,
    EDGE_SELECT,
    FACE_SELECT,
    FROM_SELECTED_FACE,
    FROM_TOP_FACE,
    LOGGING,
    MAX_SLIDER,
    MINIMAL_DOGBONE,
    MINIMAL_PERCENT,
    MIN_SLIDER,
    MODE_GROUP,
    MODE_ROW,
    MORTISE_DOGBONE,
    MORTISE_TYPE,
    NORMAL_DOGBONE,
    OBTUSE_ANGLE,
    ON_LONG_SIDE,
    ON_SHORT_SIDE,
    PARAMETRIC,
    PREVIEW_ENABLE,
    SETTINGS_GROUP,
    STATIC,
    TOOL_DIAMETER,
    TOOL_DIAMETER_OFFSET,
    EDGE_TOOLTIP,
    FACE_TOOLTIP,
    EDGE_TOOLTIP_PREVIEW,
    FACE_TOOLTIP_PREVIEW,
    EDGE_TOOLTIP_DESCRIPTION,
    FACE_TOOLTIP_DESCRIPTION)

_appPath = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger('dogbone.ui')

# noinspection SqlDialectInspection,SqlNoDataSourceInspection,PyMethodMayBeStatic
class DogboneUi:
    """
    important persistent variables:
    selectedOccurrences  - Lookup dictionary
    key: activeOccurrenceId - hash of entityToken
    value: list of selectedFaces (DbFace objects)
        provides a quick lookup relationship between each occurrence and in particular which faces have been selected.

    selectedFaces - Lookup dictionary
    key: faceId =  - hash of entityToken
    value: [DbFace objects, ....]

    selectedEdges - reverse lookup
    key: edgeId - hash of entityToken
    value: [DbEdge objects, ....]
    """

    def __init__(self, params: DbParams, command: adsk.core.Command, executeHandler) -> None:
        super().__init__()

        app = adsk.core.Application.get()
        self.design: adsk.fusion.Design = app.activeProduct
        self.ui = app.userInterface
        self.param = params
        self.command = command
        self.executeHandler = executeHandler

        self.selection = Selection()
        self.previewActive = True

        self.inputs = command.commandInputs

        if self.param.logging == 0:
            stopLogger()
        else:
            startLogger()

        self.create_ui()
        self.onInputChanged(event=command.inputChanged)
        self.onValidate(event=command.validateInputs)
        self.onFaceSelect(event=command.selectionEvent)
        self.onExecute(event=command.execute)
        self.onExecutePreview(event=command.executePreview)
        self.onKeyDown(event=command.keyDown)
        self.onKeyUp(event=command.keyUp)

    def create_ui(self):
        self.face_select()
        self.edge_select()
        self.tool_diameter()
        self.offset()
        self.mode()
        self.detection_mode()
        self.settings()

    def parseInputs(self, cmdInputs):
        """==============================================================================
        put the selections into variables that can be accessed by the main routine
        ==============================================================================
        """

        logger.debug("parsing Inputs")

        inputs = {inp.id: inp for inp in cmdInputs}

        self.param.logging = LEVELS[inputs[LOGGING].selectedItem.name]
        self.param.toolDiaStr = inputs[TOOL_DIAMETER].expression
        self.param.toolDiaOffsetStr = inputs[TOOL_DIAMETER_OFFSET].expression
        self.param.benchmark = inputs[BENCHMARK].value
        self.param.dbType = inputs[DOGBONE_TYPE].selectedItem.name
        self.param.minimalPercent = inputs[MINIMAL_PERCENT].value
        self.param.fromTop = inputs[DEPTH_EXTENT].selectedItem.name == FROM_TOP_FACE
        self.param.longSide = inputs[MORTISE_TYPE].selectedItem.name == ON_LONG_SIDE
        self.param.angleDetectionGroup = inputs[ANGLE_DETECTION_GROUP].isExpanded
        self.param.acuteAngle = inputs[ACUTE_ANGLE].value
        self.param.obtuseAngle = inputs[OBTUSE_ANGLE].value
        self.param.minAngleLimit = inputs[MIN_SLIDER].valueOne
        self.param.maxAngleLimit = inputs[MAX_SLIDER].valueOne
        self.param.expandModeGroup = (inputs[MODE_GROUP]).isExpanded
        self.param.expandSettingsGroup = (inputs[SETTINGS_GROUP]).isExpanded
        self.param.previewEnabled = inputs[PREVIEW_ENABLE].value

        mainlogger = logging.getLogger("dogbone")

        mainlogger.setLevel(self.param.logging)

        self.logParams()

        for i in range(inputs[EDGE_SELECT].selectionCount):
            entity = inputs[EDGE_SELECT].selection(i).entity
            if entity.objectType == adsk.fusion.BRepEdge.classType():
                self.selection.edges.append(entity)

        for i in range(inputs[FACE_SELECT].selectionCount):
            entity = inputs[FACE_SELECT].selection(i).entity
            if entity.objectType == adsk.fusion.BRepFace.classType():
                self.selection.faces.append(entity)

    # noinspection DuplicatedCode
    def logParams(self):
        logger.debug(f"param.fromTop = {self.param.fromTop}")
        logger.debug(f"param.dbType = {self.param.dbType}")
        logger.debug(f"param.toolDiaStr = {self.param.toolDiaStr}")
        logger.debug(f"param.toolDia = {self.param.toolDia}")
        logger.debug(
            f"param.toolDiaOffsetStr = {self.param.toolDiaOffsetStr}"
        )
        logger.debug(f"param.toolDiaOffset = {self.param.toolDiaOffset}")
        logger.debug(f"param.benchmark = {self.param.benchmark}")
        logger.debug(f"param.mortiseType = {self.param.longSide}")
        logger.debug(f"param.expandModeGroup = {self.param.expandModeGroup}")
        logger.debug(
            f"param.expandSettingsGroup = {self.param.expandSettingsGroup}"
        )

    @eventHandler(handler_cls=adsk.core.CommandEventHandler)
    def onExecutePreview(self, args:adsk.core.CommandEventArgs):
        if self.previewActive and self.param.previewEnabled:
            args.isValidResult = True
            self.executeHandler(self.param, self.selection)

    @eventHandler(handler_cls=adsk.core.CommandEventHandler)
    def onExecute(self, args):
        self.executeHandler(self.param, self.selection)

    @eventHandler(handler_cls=adsk.core.KeyboardEventHandler)
    def onKeyDown(self, args:adsk.core.KeyboardEventArgs):
        keyCode = args.keyCode
        modifier = args.modifierMask  
        self.previewActive = not keyCode == adsk.core.KeyCodes.ControlKeyCode
        self.command.doExecutePreview()

    @eventHandler(handler_cls=adsk.core.KeyboardEventHandler)
    def onKeyUp(self, args):
        keyCode = args.keyCode
        modifier = args.modifierMask  
        self.previewActive = keyCode == adsk.core.KeyCodes.ControlKeyCode  
        self.command.doExecutePreview()
  

    @eventHandler(handler_cls=adsk.core.SelectionEventHandler)
    def onFaceSelect(self, args):
        """==============================================================================
         Routine gets called with every mouse movement, if a commandInput select is active
        ==============================================================================
        """
        eventArgs: adsk.core.SelectionEventArgs = args
        # Check which selection input the event is firing for.
        activeIn = eventArgs.firingEvent.activeInput
        if activeIn.id != FACE_SELECT and activeIn.id != EDGE_SELECT:
            return  # jump out if not dealing with either of the two selection boxes

        if self.previewActive and self.param.previewEnabled:
            eventArgs.isSelectable = False
            return

        if activeIn.id == FACE_SELECT:
            # ==============================================================================
            # processing activities when faces are being selected
            #        selection filter is limited to planar faces
            #        makes sure only valid occurrences and components are selectable
            # ==============================================================================


            if not len(
                    self.selection.selectedOccurrences
            ):  # get out if the face selection list is empty
                eventArgs.isSelectable = True
                return
            if not eventArgs.selection.entity.assemblyContext:
                # dealing with a root component body

                activeBodyName = hash(eventArgs.selection.entity.body.entityToken)
                try:
                    faces = self.selection.selectedOccurrences[activeBodyName]
                    for face in faces:
                        if face.isSelected:
                            primaryFace = face
                            break
                    else:
                        eventArgs.isSelectable = True
                        return
                except (KeyError, IndexError) as e:
                    return

                primaryFaceNormal = getFaceNormal(primaryFace.face)
                if primaryFaceNormal.isParallelTo(
                        getFaceNormal(eventArgs.selection.entity)
                ):
                    eventArgs.isSelectable = True
                    return
                eventArgs.isSelectable = False
                return
            # End of root component face processing

            # ==============================================================================
            # Start of occurrence face processing
            # ==============================================================================
            activeOccurrence = eventArgs.selection.entity.assemblyContext
            activeOccurrenceId = hash(activeOccurrence.entityToken)
            activeComponent = activeOccurrence.component

            # we got here because the face is either not in root or is on the existing selected list
            # at this point only need to check for duplicate component selection - Only one component allowed, to save on conflict checking
            try:
                #the comprehension in the middle of this flattens the list of lists of self.selection.selectedOccrrences.values()
                selectedComponentList = [
                    x.face.assemblyContext.component
                    for x in [item for sublist in self.selection.selectedOccurrences.values() for item in sublist]
                    if x.face.assemblyContext
                ]
            except KeyError:
                eventArgs.isSelectable = True
                return

            if activeComponent not in selectedComponentList:
                eventArgs.isSelectable = True
                return

            if (
                    activeOccurrenceId not in self.selection.selectedOccurrences
            ):  # check if mouse is over a face that is not already selected
                eventArgs.isSelectable = False
                return

            try:
                faces = self.selection.selectedOccurrences[activeOccurrenceId]
                for face in faces:
                    if face.isSelected:
                        primaryFace = face
                        break
                    else:
                        eventArgs.isSelectable = True
                        return
            except KeyError:
                return
            primaryFaceNormal = getFaceNormal(primaryFace.face)
            if primaryFaceNormal.isParallelTo(
                    getFaceNormal(eventArgs.selection.entity)
            ):
                eventArgs.isSelectable = True
                return
            eventArgs.isSelectable = False
            return
            # end selecting faces

        else:
            # ==============================================================================
            #             processing edges associated with face - edges selection has focus
            # ==============================================================================
            if self.selection.addingEdges:
                return

            selected = eventArgs.selection
            currentEdge: adsk.fusion.BRepEdge = selected.entity

            edgeId = hash(currentEdge.entityToken)
            if edgeId in self.selection.selectedEdges.keys():
                eventArgs.isSelectable = True
            else:
                eventArgs.isSelectable = False
            return

    @eventHandler(handler_cls=adsk.core.ValidateInputsEventHandler)
    def onValidate(self, args):
        cmd: adsk.core.ValidateInputsEventArgs = args.firingEvent.sender

        for input in cmd.commandInputs:
            if input.id == FACE_SELECT:
                if input.selectionCount < 1:
                    args.areInputsValid = False
            elif input.id == TOOL_DIAMETER:
                if input.value <= 0:
                    args.areInputsValid = False


    @eventHandler(handler_cls=adsk.core.InputChangedEventHandler)
    @parseDecorator
    def onInputChanged(self, args: adsk.core.InputChangedEventArgs):
        input: adsk.core.CommandInput = args.input
        logger.debug(f"input changed- {input.id}")

        # TODO: instead of finding the elements again via id, better to take the reference. Then the casting is
        # not necessary anymore and the code becomes way slimmer

        if input.id == LOGGING:
            if input.commandInputs.itemById(LOGGING).listItems.item(input.commandInputs.itemById(LOGGING).selectedItem.index).name == 'Notset':
                stopLogger()
            else:
                startLogger()

        if input.id == DOGBONE_TYPE:
            input.commandInputs.itemById(MINIMAL_PERCENT).isVisible = (
                    cast(adsk.core.ButtonRowCommandInput, input.commandInputs.itemById(DOGBONE_TYPE)).selectedItem.name
                    == MINIMAL_DOGBONE
            )
            input.commandInputs.itemById(MORTISE_TYPE).isVisible = (
                    cast(adsk.core.ButtonRowCommandInput, input.commandInputs.itemById(DOGBONE_TYPE)).selectedItem.name
                    == MORTISE_DOGBONE
            )
            return

        if input.id == TOOL_DIAMETER:
            self.param.toolDiaStr:adsk.core.ValueCommandInput = input.expression
            return

        if input.id == PREVIEW_ENABLE:
            self.previewActive = self.param.previewEnabled = input.value
            

            edgeSelectInput = input.parentCommand.commandInputs.itemById(EDGE_SELECT)
            faceSelectInput = input.parentCommand.commandInputs.itemById(FACE_SELECT)

            edgeSelectInput.tooltipDescription = EDGE_TOOLTIP_DESCRIPTION
            faceSelectInput.tooltipDescription = FACE_TOOLTIP_DESCRIPTION

            if self.param.previewEnabled:
                edgeSelectInput.commandPrompt = edgeSelectInput.tooltip = EDGE_TOOLTIP_PREVIEW
                faceSelectInput.commandPrompt = faceSelectInput.tooltip = FACE_TOOLTIP_PREVIEW

            else:
                edgeSelectInput.commandPrompt = edgeSelectInput.tooltip = EDGE_TOOLTIP
                faceSelectInput.commandPrompt = faceSelectInput.tooltip = FACE_TOOLTIP

            self.command.doExecutePreview()

            return

        if input.id == MODE_ROW:
            input.parentCommand.commandInputs.itemById(
                ANGLE_DETECTION_GROUP
            ).isVisible = (cast(adsk.core.ButtonRowCommandInput, input).selectedItem.name == STATIC)
            self.param.parametric:adsk.core.ButtonRowCommandInput = input.selectedItem.name == PARAMETRIC  #

        if input.id == ACUTE_ANGLE:
            b = cast(adsk.core.BoolValueCommandInput, input)
            input.commandInputs.itemById(
                MIN_SLIDER
            ).isVisible = b.value
            self.param.acuteAngle = b.value

        if input.id == MIN_SLIDER:
            self.param.minAngleLimit: adsk.core.FloatSliderCommandInput = input.commandInputs.itemById(
                MIN_SLIDER
            ).valueOne

        if input.id == OBTUSE_ANGLE:
            b = cast(adsk.core.BoolValueCommandInput, input)
            input.commandInputs.itemById(
                MAX_SLIDER
            ).isVisible = b.value
            self.param.obtuseAngle = b.value

        if input.id == MAX_SLIDER:
            self.param.maxAngleLimit: adsk.core.FloatSliderCommandInput = input.commandInputs.itemById(
                MAX_SLIDER
            ).valueOne

        #
        if (
                input.id == ACUTE_ANGLE
                or input.id == OBTUSE_ANGLE
                or input.id == MIN_SLIDER
                or input.id == MAX_SLIDER
                or input.id == MODE_ROW
        ):  # refresh edges after specific input changes
            previewState = self.previewActive #need to disable preview, otherwise the wrong entities are displayed/Selected 
            self.previewActive = False
            self.command.doExecutePreview()
            edgeSelectCommand = input.parentCommand.commandInputs.itemById(EDGE_SELECT)
            if not edgeSelectCommand.isVisible:
                return
            focusState:adsk.core.SelectionCommandInput = input.parentCommand.commandInputs.itemById(FACE_SELECT).hasFocus
            edgeSelectCommand.hasFocus = True

            for edgeObj in self.selection.selectedEdges.values():
                self.ui.activeSelections.removeByEntity(edgeObj.edge)

            for faceObj in self.selection.selectedFaces.values():
                faceObj.reSelectEdges()

            input.parentCommand.commandInputs.itemById(FACE_SELECT).hasFocus = focusState
            
            self.previewActive = previewState
            self.command.doExecutePreview()

            return

        if input.id != FACE_SELECT and input.id != EDGE_SELECT:
            return

        logger.debug(f"input changed- {input.id}")
        s = cast(adsk.core.SelectionCommandInput, input)
        if input.id == FACE_SELECT:
            # ==============================================================================
            #            processing changes to face selections
            # ==============================================================================

            if len([x for x in self.selection.selectedFaces.values() if x.isSelected]) > s.selectionCount:
                # a face has been removed

                # If all faces are removed, just reset registers
                if s.selectionCount == 0:
                    self.selection.selectedEdges = {}
                    self.selection.selectedFaces = {}
                    self.selection.selectedOccurrences = {}

                    cast(adsk.core.SelectionCommandInput, input.commandInputs.itemById(EDGE_SELECT)).clearSelection()
                    input.commandInputs.itemById(FACE_SELECT).hasFocus = True
                    input.commandInputs.itemById(EDGE_SELECT).isVisible = False
                    return

                # Else find the missing face in selection
                selectionSet = {
                    hash(cast(adsk.fusion.BRepEdge, s.selection(i).entity).entityToken)
                    for i in range(s.selectionCount)
                }
                missingFaces = set(self.selection.selectedFaces.keys()) ^ selectionSet
                input.commandInputs.itemById(EDGE_SELECT).isVisible = True
                input.commandInputs.itemById(EDGE_SELECT).hasFocus = True

                for missingFace in missingFaces:
                    faceObj = self.selection.selectedFaces[missingFace]
                    faceObj.removeFaceFromSelectedOccurrences()
                    faceObj.deleteEdges()
                    self.selection.selectedFaces.pop(missingFace)

                input.commandInputs.itemById(FACE_SELECT).hasFocus = True

                return

            # ==============================================================================
            #             Face has been added - assume that the last selection entity is the one added
            # ==============================================================================
            input.commandInputs.itemById(EDGE_SELECT).isVisible = True
            input.commandInputs.itemById(EDGE_SELECT).hasFocus = True

            selectionDict = {
                hash(
                    cast(adsk.fusion.BRepEdge, s.selection(i).entity).entityToken
                ): s.selection(i).entity
                for i in range(s.selectionCount)
            }

            addedFaces = set(self.selection.selectedFaces.keys()) ^ set(
                selectionDict.keys()
            )  # get difference -> results in

            for faceId in addedFaces:
                changedEntity = selectionDict[
                    faceId
                ] 
                activeOccurrenceId = (
                    hash(changedEntity.assemblyContext.entityToken)
                    if changedEntity.assemblyContext
                    else hash(changedEntity.body.entityToken)
                )

                faces = self.selection.selectedOccurrences.get(activeOccurrenceId, [])

                faces += (
                    createdFace := [
                        DbFace(
                            face=changedEntity,
                            selection=self.selection,
                            params=self.param,
                            commandInputsEdgeSelect=input.commandInputs.itemById(
                                EDGE_SELECT
                            ),
                        )
                    ]
                )
                self.selection.selectedOccurrences[
                    activeOccurrenceId
                ] = faces  # adds a face to a list of faces associated with this occurrence
                self.selection.selectedFaces.update({faceObj.faceId: faceObj for faceObj in createdFace})

                for face_id in addedFaces:
                    self.selection.selectedFaces[face_id].selectAll()

                input.commandInputs.itemById(FACE_SELECT).hasFocus = True

            return
            # end of processing faces
        # ==============================================================================
        #         Processing changed edge selection
        # ==============================================================================

        if len([x for x in self.selection.selectedEdges.values() if x.isSelected]) > s.selectionCount:
            # ==============================================================================
            #             an edge has been removed
            # ==============================================================================

            changedSelectionList = [
                s.selection(i).entity
                for i in range(s.selectionCount)
            ]
            changedEdgeIdSet = set(
                map(calcId, changedSelectionList)
            )  # converts list of edges to a list of their edgeIds
            missingEdges = set(self.selection.selectedEdges.keys()) - changedEdgeIdSet
            # noinspection PyStatementEffect

            for missingEdge in missingEdges:
                self.selection.selectedEdges[missingEdge].deselect()

            # Note - let the user manually unselect the face if they want to choose a different face

            return
            # End of processing removed edge
        else:
            # ==============================================================================
            #         Start of adding a selected edge
            #         Edge has been added - assume that the last selection entity is the one added
            # ==============================================================================
            selection_command_input = cast(adsk.core.SelectionCommandInput, input)
            edge: adsk.fusion.BRepEdge = cast(adsk.fusion.BRepEdge, selection_command_input.selection(
                selection_command_input.selectionCount - 1
            ).entity)
            # noinspection PyStatementEffect
            self.selection.selectedEdges[
                calcId(edge)
            ].select()  # Get selectedFace then get selectedEdge, then call function

    def detection_mode(self):
        angleDetectionGroupInputs: adsk.core.GroupCommandInput = (
            self.inputs.addGroupCommandInput(ANGLE_DETECTION_GROUP, "Detection Mode")
        )
        angleDetectionGroupInputs.isExpanded = self.param.angleDetectionGroup
        enableAcuteAngleInput: adsk.core.BoolValueCommandInput = (
            angleDetectionGroupInputs.children.addBoolValueInput(
                ACUTE_ANGLE, "Acute Angle", True, "", self.param.acuteAngle
            )
        )
        enableAcuteAngleInput.tooltip = (
            "Enables detection of corner angles less than 90"
        )
        minAngleSliderInput: adsk.core.FloatSliderCommandInput = (
            angleDetectionGroupInputs.children.addFloatSliderCommandInput(
                MIN_SLIDER, "Min Limit", "", 10.0, 89.0
            )
        )
        minAngleSliderInput.isVisible = self.param.acuteAngle
        minAngleSliderInput.valueOne = self.param.minAngleLimit
        enableObtuseAngleInput: adsk.core.BoolValueCommandInput = (
            angleDetectionGroupInputs.children.addBoolValueInput(
                OBTUSE_ANGLE, "Obtuse Angle", True, "", self.param.obtuseAngle
            )
        )  #
        enableObtuseAngleInput.tooltip = (
            "Enables detection of corner angles greater than 90"
        )
        maxAngleSliderInput: adsk.core.FloatSliderCommandInput = (
            angleDetectionGroupInputs.children.addFloatSliderCommandInput(
                MAX_SLIDER, "Max Limit", "", 91.0, 170.0
            )
        )
        maxAngleSliderInput.isVisible = self.param.obtuseAngle
        maxAngleSliderInput.valueOne = self.param.maxAngleLimit

    def mode(self):
        modeGroup: adsk.core.GroupCommandInput = self.inputs.addGroupCommandInput(
            MODE_GROUP, "Mode"
        )
        modeGroup.isExpanded = self.param.expandModeGroup
        modeGroupChildInputs = modeGroup.children
        typeRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput(DOGBONE_TYPE, "Type", False)
        )
        typeRowInput.listItems.add(
            NORMAL_DOGBONE, self.param.dbType == NORMAL_DOGBONE, "resources/ui/type/normal"
        )
        typeRowInput.listItems.add(
            MINIMAL_DOGBONE,
            self.param.dbType == MINIMAL_DOGBONE,
            "resources/ui/type/minimal",
        )
        typeRowInput.listItems.add(
            MORTISE_DOGBONE,
            self.param.dbType == MORTISE_DOGBONE,
            "resources/ui/type/hidden",
        )
        typeRowInput.tooltipDescription = (
            "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit "
            "that, for example, will require a larger force to insert a tenon into a mortise.\n"
            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n"
            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        )
        mortiseRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput(
                MORTISE_TYPE, "Mortise Type", False
            )
        )
        mortiseRowInput.listItems.add(
            ON_LONG_SIDE, self.param.longSide, "resources/ui/type/hidden/longside"
        )
        mortiseRowInput.listItems.add(
            ON_SHORT_SIDE, not self.param.longSide, "resources/ui/type/hidden/shortside"
        )
        mortiseRowInput.tooltipDescription = (
            "Along Longest will have the dogbones cut into the longer sides."
            "\nAlong Shortest will have the dogbones cut into the shorter sides."
        )
        mortiseRowInput.isVisible = self.param.dbType == MORTISE_DOGBONE
        minPercentInp = modeGroupChildInputs.addValueInput(
            MINIMAL_PERCENT,
            "Percentage Reduction",
            "",
            adsk.core.ValueInput.createByReal(self.param.minimalPercent),
        )
        minPercentInp.tooltip = "Percentage of tool radius added to push out dogBone - leaves actual corner exposed"
        minPercentInp.tooltipDescription = "This should typically be left at 10%, but if the fit is too tight, it should be reduced"
        minPercentInp.isVisible = self.param.dbType == MINIMAL_DOGBONE
        depthRowInput: adsk.core.ButtonRowCommandInput = (
            modeGroupChildInputs.addButtonRowCommandInput(
                DEPTH_EXTENT, "Depth Extent", False
            )
        )
        depthRowInput.listItems.add(
            FROM_SELECTED_FACE, not self.param.fromTop, "resources/ui/mode/fromFace"
        )
        depthRowInput.listItems.add(
            FROM_TOP_FACE, self.param.fromTop, "resources/ui/mode/fromTop"
        )
        depthRowInput.tooltipDescription = (
            'When "From Top Face" is selected, all dogbones will be extended to the top most face\n'
            "\nThis is typically chosen when you don't want to, or can't do, double sided machinin"
        )

    def settings(self):
        group: adsk.core.GroupCommandInput = self.inputs.addGroupCommandInput(
            SETTINGS_GROUP, "Settings"
        )
        group.isExpanded = self.param.expandSettingsGroup

        previewEnabled = group.children.addBoolValueInput(
            PREVIEW_ENABLE, "Enable Preview Mode", True, "", self.param.previewEnabled            
        )

        previewEnabled.tooltip = "Activates live preview"
        previewEnabled.tooltipDescription =(
                                            "<br>Use ctrl-click when preview is active"
                                            "<br><br>Warning:"
                                            "<br>the number of edges selected,"
                                            "<br>along with the power of your computer and"
                                            "<br>graphics card may result in a delay in showing the preview"
        )

        benchMark = group.children.addBoolValueInput(
            BENCHMARK, "Benchmark time", True, "", self.param.benchmark
        )
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = (
            "When enabled, shows overall time taken to process all selected dogbones."
        )

        log: adsk.core.DropDownCommandInput = (
            group.children.addDropDownCommandInput(
                LOGGING,
                "Logging level",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
        )
        log.tooltip = "Enables logging"
        log.tooltipDescription = (
            "Creates a dogbone.log file. \n"
            f"Location: {os.path.join(_appPath, 'dogBone.log')}"
        )

        log.listItems.add("Notset", self.param.logging == 0)
        log.listItems.add("Debug", self.param.logging == 10)
        log.listItems.add("Info", self.param.logging == 20)

    def offset(self):

        ui = self.inputs.addValueInput(
            TOOL_DIAMETER_OFFSET,
            "Tool diameter offset",
            self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaOffsetStr),
        )
        ui.tooltip = "Increases the tool diameter"
        ui.tooltipDescription = (
            "Use this to create an oversized dogbone.\n"
            "Normally set to 0.  \n"
            "A value of .010 would increase the dogbone diameter by .010 \n"
            "Used when you want to keep the tool diameter and oversize value separate"
        )

    def tool_diameter(self):
        ui = self.inputs.addValueInput(
            TOOL_DIAMETER,
            "Tool Dia               ",
            self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaStr),
        )
        ui.tooltip = "Diameter of the tool with which you'll cut the dogbone."

    def edge_select(self):
        
        tooltipDesc = EDGE_TOOLTIP_DESCRIPTION
        if self.param.previewEnabled:
            msg = EDGE_TOOLTIP_PREVIEW
        else:
            msg = EDGE_TOOLTIP
            
        ui = self.inputs.addSelectionInput(
            EDGE_SELECT,
            "DogBone Edges",
            "",
        )
        ui.commandPrompt = ui.tooltip = msg
        ui.tooltipDescription = tooltipDesc
        ui.addSelectionFilter("LinearEdges")
        ui.setSelectionLimits(1, 0)
        ui.isVisible = False

    def face_select(self):

        tooltipDesc = FACE_TOOLTIP_DESCRIPTION

        if self.param.previewEnabled:
            msg = FACE_TOOLTIP_PREVIEW
        else:
            msg = FACE_TOOLTIP
            
        ui = self.inputs.addSelectionInput(
            FACE_SELECT,
            "Face",
            "",
        )
        ui.commandPrompt = ui.tooltip = msg
        ui.tooltipDescription = tooltipDesc
        ui.addSelectionFilter("PlanarFaces")
        ui.setSelectionLimits(1, 0)
