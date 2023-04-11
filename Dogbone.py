#Author-Peter Ludikar, Gary Singer
#Description-An Add-In for making dog-bone fillets.

# Peter completely revamped the dogbone add-in by Casey Rogers and Patrick Rainsberry and David Liu
# Some of the original utilities have remained, but a lot of the other functionality has changed.

# The original add-in was based on creating sketch points and extruding - Peter found using sketches and extrusion to be very heavy 
# on processing resources, so this version has been designed to create dogbones directly by using a hole tool. So far the
# the performance of this approach is day and night compared to the original version. 

# Select the face you want the dogbones to drop from. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diamater equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.
import logging
import adsk.core, adsk.fusion
import os, sys

# Globals
_app = adsk.core.Application.get()
_design = _app.activeProduct
_ui = _app.userInterface
_rootComp = _design.rootComponent
_appPath = os.path.dirname(os.path.abspath(__file__))
_subpath = os.path.join(f'{_appPath}','py_packages')
if _subpath not in sys.path:
    sys.path.insert(0, _subpath)
    # sys.path.insert(0, os.path.join(f'{_appPath}','py_packages','dataclasses_json'))
    sys.path.insert(0, '')

from collections import defaultdict

import math
import traceback
import json

import time
from . import dbutils as dbUtils
from .decorators import eventHandler
from math import sqrt as sqrt
from .DbClasses import DbFace, DbEdge
from .DbData import DbParams


#constants - to keep attribute group and names consistent
DOGBONEGROUP = 'dogBoneGroup'
# FACE_ID = 'faceID'
REV_ID = 'revId'
ID = 'id'
DEBUGLEVEL = logging.NOTSET



calcId = lambda x: hash(x.entityToken) # if x.assemblyContext else str(x.tempId) + ':' + x.body.name
makeNative = lambda x: x.nativeObject if x.nativeObject else x
reValidateFace = lambda comp, x: comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)


class DogboneCommand(object):
    COMMAND_ID = "dogboneBtn"
    # REFRESH_COMMAND_ID = "refreshDogboneBtn"
    
    param = DbParams()
    registeredEdgesDict = {}
    
    faces = []
    edges = []
    
    selectedOccurrences = {} #key hash(occurrence.entityToken) value:[DbFace,...]
    selectedFaces = {} #key: hash(face.entityToken) value:[DbFace,...]
    selectedEdges = {} #kay: hash(edge.entityToken) value:[DbEdge, ...]

    def __init__(self):

        self.faceSelections = adsk.core.ObjectCollection.create()
        self.param = DbParams()
        self.loggingLevels = {'Notset':0,'Debug':10,'Info':20,'Warning':30,'Error':40}

        self.levels = {}
        self.initLogger()
        _appPath = os.path.dirname(os.path.abspath(__file__))
        

    def writeDefaults(self):
        self.logger.info('config file write')

        json_file = open(os.path.join(_appPath, 'defaults.dat'), 'w', encoding='UTF-8')
        json_file.write(self.param.to_json())
        json_file.close()
    
    def readDefaults(self): 
        self.logger.info('config file read')
        if not os.path.isfile(os.path.join(_appPath, 'defaults.dat')):
            return
        json_file = open(os.path.join(_appPath, 'defaults.dat'), 'r', encoding='UTF-8')
        jsonString = json_file.read()
        try:
            self.param = self.param.from_json(jsonString)
        except ValueError:
            self.logger.error('default.dat error')
            json_file.close()
            json_file = open(os.path.join(_appPath, 'defaults.dat'), 'w', encoding='UTF-8')
            paramString = DbParams().to_json()
            json_file.write(paramString)
            json_file.close()
            self.param = DbParams()
            
    def debugFace(self, face):
        if  self.logger.level < logging.DEBUG:
            return
        for edge in face.edges:
             self.logger.debug(f'edge {edge.tempId}; startVertex: {edge.startVertex.geometry.asArray()}; endVertex: {edge.endVertex.geometry.asArray()}')

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

        # Create button definition and command event handler
        buttonDogbone = _ui.commandDefinitions.addButtonDefinition(
            self.COMMAND_ID, 
            'Dogbone', 
            'Creates dogbones at all inside corners of a face', 
            'Resources')

        self.onCreate(event=buttonDogbone.commandCreated)
        # Create controls for Manufacturing Workspace
        mfgEnv = _ui.workspaces.itemById('MfgWorkingModelEnv')
        mfgTab = mfgEnv.toolbarTabs.itemById('MfgSolidTab')
        mfgSolidPanel = mfgTab.toolbarPanels.itemById('SolidCreatePanel')
        buttonControlMfg = mfgSolidPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')

        # Make the button available in the Mfg panel.
        buttonControlMfg.isPromotedByDefault = True
        buttonControlMfg.isPromoted = True

        # Create controls for the Design Workspace
        createPanel = _ui.allToolbarPanels.itemById('SolidCreatePanel')
        buttonControl = createPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

    def removeButton(self):
        createPanel = _ui.allToolbarPanels.itemById('SolidCreatePanel')
        if cntrl := createPanel.controls.itemById(self.COMMAND_ID):
            cntrl.deleteMe()

        mfgEnv = _ui.workspaces.itemById('MfgWorkingModelEnv')
        mfgTab = mfgEnv.toolbarTabs.itemById('MfgSolidTab')
        mfgSolidPanel = mfgTab.toolbarPanels.itemById('SolidCreatePanel')
        if cntrl := mfgSolidPanel.controls.itemById(self.COMMAND_ID):
            cntrl.deleteMe()

        if cmdDef := _ui.commandDefinitions.itemById(self.COMMAND_ID):
            cmdDef.deleteMe()

    # @eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
    # def onRefreshCreate(self, args:adsk.core.CommandCreatedEventArgs):
    #         inputs = args.command.commandInputs
    #         edgeSelectCommand = inputs.itemById('edgeSelect')
    #         if not edgeSelectCommand.isVisible:
    #             return
    #         focusState = inputs.itemById('faceSelect').hasFocus
    #         edgeSelectCommand.hasFocus = True
    #         [_ui.activeSelections.removeByEntity(edgeObj.edge) for edgeObj in self.selectedEdges.values()]
    #         [faceObj.reSelectEdges() for faceObj in self.selectedFaces.values()]
    #         inputs.itemById('faceSelect').hasFocus = focusState
    #         return

    @eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
    def onCreate(self, args:adsk.core.CommandCreatedEventArgs):
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
        self.errorCount = 0
        self.faceSelections.clear()
        
        if _design.designType != adsk.fusion.DesignTypes.ParametricDesignType :
            returnValue = _ui.messageBox('DogBone only works in Parametric Mode \n Do you want to change modes?', 'Change to Parametric mode', adsk.core.MessageBoxButtonTypes.YesNoButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            _design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        self.readDefaults()

        self.selectedEdges = {}
        self.selectedFaces = {}
        self.selectedOccurrences = {}

        inputs:adsk.core.CommandInputs = args.command.commandInputs
        
        selInput0 = inputs.addSelectionInput(
            'faceSelect', 'Face',
            'Select a face to apply dogbones to all internal corner edges')
        selInput0.tooltip ='Select a face to apply dogbones to all internal corner edges\n*** Select faces by clicking on them. DO NOT DRAG SELECT! ***' 
        selInput0.addSelectionFilter('PlanarFaces')
        selInput0.setSelectionLimits(1,0)
        
        selInput1 = inputs.addSelectionInput(
            'edgeSelect', 'DogBone Edges',
            'Select or de-select any internal edges dropping down from a selected face (to apply dogbones to')
        selInput1.tooltip ='Select or de-select any internal edges dropping down from a selected face (to apply dogbones to)' 
        selInput1.addSelectionFilter('LinearEdges')
        selInput1.setSelectionLimits(1,0)
        selInput1.isVisible = False
                
        inp = inputs.addValueInput(
            'toolDia', 
            'Tool Dia               ', 
            _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaStr))
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."
        
        offsetInp = inputs.addValueInput(
            'toolDiaOffset', 
            'Tool diameter offset', 
            _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.param.toolDiaOffsetStr))
        offsetInp.tooltip = "Increases the tool diameter"
        offsetInp.tooltipDescription = "Use this to create an oversized dogbone.\n"\
                                        "Normally set to 0.  \n"\
                                        "A value of .010 would increase the dogbone diameter by .010 \n"\
                                        "Used when you want to keep the tool diameter and oversize value separate"
        
        modeGroup:adsk.core.GroupCommandInput = inputs.addGroupCommandInput('modeGroup', 'Mode')
        modeGroup.isExpanded = self.param.expandModeGroup
        modeGroupChildInputs = modeGroup.children
        
        modeRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('modeRow', 'Mode', False)
        modeRowInput.listItems.add('Static',
                                    not self.param.parametric, 
                                    'resources/staticMode' )
        modeRowInput.listItems.add('Parametric', 
                                   self.param.parametric, 
                                   'resources/parametricMode' )
        modeRowInput.tooltipDescription = "Static dogbones do not move with the underlying component geometry. \n" \
                                "\nParametric dogbones will automatically adjust position with parametric changes to underlying geometry. " \
                                "Geometry changes must be made via the parametric dialog.\nFusion has more issues/bugs with these!"
        
        typeRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('dogboneType', 'Type', False)
        typeRowInput.listItems.add('Normal Dogbone', 
                                   self.param.dbType == 'Normal Dogbone', 
                                   'resources/normal' )
        typeRowInput.listItems.add('Minimal Dogbone', 
                                   self.param.dbType == 'Minimal Dogbone', 
                                   'resources/minimal' )
        typeRowInput.listItems.add('Mortise Dogbone', 
                                   self.param.dbType == 'Mortise Dogbone', 
                                   'resources/hidden' )
        typeRowInput.tooltipDescription = "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit " \
                                            "that, for example, will require a larger force to insert a tenon into a mortise.\n" \
                                            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n" \
                                            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        
        mortiseRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('mortiseType', 'Mortise Type', False)
        mortiseRowInput.listItems.add('On Long Side', 
                                      self.param.longSide, 
                                      'resources/hidden/longSide' )
        mortiseRowInput.listItems.add('On Short Side', 
                                      not self.param.longSide, 
                                      'resources/hidden/shortside' )
        mortiseRowInput.tooltipDescription = "Along Longest will have the dogbones cut into the longer sides." \
                                             "\nAlong Shortest will have the dogbones cut into the shorter sides."
        mortiseRowInput.isVisible = self.param.dbType == 'Mortise Dogbone'

        minPercentInp = modeGroupChildInputs.addValueInput(
                                'minimalPercent', 
                                'Percentage Reduction', 
                                '',
                                adsk.core.ValueInput.createByReal(self.param.minimalPercent))
        minPercentInp.tooltip = "Percentage of tool radius added to push out dogBone - leaves actual corner exposed"
        minPercentInp.tooltipDescription = "This should typically be left at 10%, but if the fit is too tight, it should be reduced"
        minPercentInp.isVisible = self.param.dbType == 'Minimal Dogbone'

        depthRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('depthExtent', 'Depth Extent', False)
        depthRowInput.listItems.add('From Selected Face', 
                                    not self.param.fromTop, 
                                    'resources/fromFace' )
        depthRowInput.listItems.add('From Top Face', 
                                    self.param.fromTop, 
                                    'resources/fromTop' )
        depthRowInput.tooltipDescription = "When \"From Top Face\" is selected, all dogbones will be extended to the top most face\n"\
                                            "\nThis is typically chosen when you don't want to, or can't do, double sided machining."
 
        angleDetectionGroupInputs:adsk.core.GroupCommandInput = inputs.addGroupCommandInput('angleDetectionGroup', 'Detection Mode')
        angleDetectionGroupInputs.isExpanded = self.param.angleDetectionGroup

        enableAcuteAngleInput:adsk.core.BoolValueCommandInput = angleDetectionGroupInputs.children.addBoolValueInput('acuteAngle','Acute Angle', True, '', self.param.acuteAngle)
        enableAcuteAngleInput.tooltip = "Enables detection of corner angles less than 90"
        minAngleSliderInput:adsk.core.FloatSliderCommandInput = angleDetectionGroupInputs.children.addFloatSliderCommandInput('minSlider', 'Min Limit', '', 10.0, 89.0)
        minAngleSliderInput.isVisible = self.param.acuteAngle
        minAngleSliderInput.valueOne = self.param.minAngleLimit

        enableObtuseAngleInput:adsk.core.BoolValueCommandInput = angleDetectionGroupInputs.children.addBoolValueInput('obtuseAngle','Obtuse Angle', True, '', self.param.obtuseAngle) # 
        enableObtuseAngleInput.tooltip = "Enables detection of corner angles greater than 90"
        
        maxAngleSliderInput:adsk.core.FloatSliderCommandInput = angleDetectionGroupInputs.children.addFloatSliderCommandInput('maxSlider', 'Max Limit', '', 91.0, 170.0)
        maxAngleSliderInput.isVisible = self.param.obtuseAngle
        maxAngleSliderInput.valueOne = self.param.maxAngleLimit  

        settingGroup:adsk.core.GroupCommandInput = inputs.addGroupCommandInput('settingsGroup', 'Settings')
        settingGroup.isExpanded = self.param.expandSettingsGroup
        settingGroupChildInputs = settingGroup.children

        benchMark = settingGroupChildInputs.addBoolValueInput("benchmark", 
                                                              "Benchmark time", 
                                                              True, 
                                                              "", 
                                                              self.param.benchmark)
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = "When enabled, shows overall time taken to process all selected dogbones."

        logDropDownInp:adsk.core.DropDownCommandInput = settingGroupChildInputs.addDropDownCommandInput("logging", "Logging level", adsk.core.DropDownStyles.TextListDropDownStyle)
        logDropDownInp.tooltip = "Enables logging"
        logDropDownInp.tooltipDescription = "Creates a dogbone.log file. \n" \
                     f"Location: {os.path.join(_appPath, 'dogBone.log')}"

        logDropDownInp.listItems.add('Notset', self.param.logging == 0)
        logDropDownInp.listItems.add('Debug', self.param.logging == 10)
        logDropDownInp.listItems.add('Info', self.param.logging == 20)

        cmd:adsk.core.Command = args.command
        # Add handlers to this command.
        self.onExecute(event=cmd.execute)
        # self.onExecutePreview(event=cmd.executePreview)
        self.onFaceSelect(event=cmd.selectionEvent)
        self.onValidate(event=cmd.validateInputs)
        self.onChange(event=cmd.inputChanged)

    @eventHandler(handler_cls=adsk.core.CommandEventHandler)
    def onExecutePreview(self, args:adsk.core.CommandEventArgs):
        # return
        [edgeObj.addCustomGraphic() for edgeObj in self.selectedEdges.values()]
        self.selections = _ui.activeSelections.all
        self.createStaticDogbones()
        # _ui.activeSelections.all = self.selections 

    #==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    #==============================================================================
    @eventHandler(handler_cls = adsk.core.InputChangedEventHandler)
    def onChange(self, args:adsk.core.InputChangedEventArgs):
        
        changedInput:adsk.core.CommandInput = args.input
        self.logger.debug(f'input changed- {changedInput.id}')

        if changedInput.id == 'dogboneType':
            changedInput.commandInputs.itemById('minimalPercent').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Minimal Dogbone')
            changedInput.commandInputs.itemById('mortiseType').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Mortise Dogbone')
            return
        
        if changedInput.id == 'toolDia':
            changedInput: adsk.core.ValueCommandInput
            self.param.toolDiaStr = changedInput.expression
            return
        

        if changedInput.id == 'acuteAngle':
            changedInput.commandInputs.itemById('minSlider').isVisible = changedInput.value
            self.param.acuteAngle = changedInput.value

        if changedInput.id == 'minSlider':
            self.param.minAngleLimit = changedInput.commandInputs.itemById('minSlider').valueOne

        if changedInput.id == 'obtuseAngle':
            changedInput.commandInputs.itemById('maxSlider').isVisible = changedInput.value
            self.param.obtuseAngle = changedInput.value

        if changedInput.id == 'maxSlider':
            self.param.maxAngleLimit = changedInput.commandInputs.itemById('maxSlider').valueOne

        if changedInput.id == 'acuteAngle' \
             or changedInput.id == 'obtuseAngle' \
             or changedInput.id == 'minSlider' \
             or changedInput.id == 'maxSlider' :
            edgeSelectCommand = changedInput.parentCommand.commandInputs.itemById('edgeSelect')
            if not edgeSelectCommand.isVisible:
                return
            focusState = changedInput.parentCommand.commandInputs.itemById('faceSelect').hasFocus
            edgeSelectCommand.hasFocus = True
            [_ui.activeSelections.removeByEntity(edgeObj.edge) for edgeObj in self.selectedEdges.values()]
            [faceObj.reSelectEdges() for faceObj in self.selectedFaces.values()]
            changedInput.parentCommand.commandInputs.itemById('faceSelect').hasFocus = focusState
            return
            
        if changedInput.id != 'faceSelect' and changedInput.id != 'edgeSelect':
            return

        self.logger.debug(f'input changed- {changedInput.id}')
        if changedInput.id == 'faceSelect':

            #==============================================================================
            #            processing changes to face selections
            #==============================================================================
            if len(self.selectedFaces) > changedInput.selectionCount:               
                # a face has been removed
                
                # If all faces are removed, just reset registers
                if changedInput.selectionCount == 0:                
                    self.selectedEdges = {}
                    self.selectedFaces = {}
                    self.selectedOccurrences = {}
                    changedInput.commandInputs.itemById('edgeSelect').clearSelection()
                    changedInput.commandInputs.itemById('faceSelect').hasFocus = True                    
                    changedInput.commandInputs.itemById('edgeSelect').isVisible = False   
                    return
                
                # Else find the missing face in selection
                selectionSet = {hash(changedInput.selection(i).entity.entityToken) for i in range(changedInput.selectionCount)}
                missingFaces = set(self.selectedFaces.keys()) ^ selectionSet
                changedInput.commandInputs.itemById('edgeSelect').isVisible = True   
                changedInput.commandInputs.itemById('edgeSelect').hasFocus = True
                [(self.selectedFaces[missingFace].removeFaceFromSelectedOccurrences(),
                  self.selectedFaces[missingFace].deleteEdges(),
                   self.selectedFaces.pop(missingFace)) for missingFace in missingFaces]
                changedInput.commandInputs.itemById('faceSelect').hasFocus = True
                return
             
            #==============================================================================
            #             Face has been added - assume that the last selection entity is the one added
            #==============================================================================
            changedInput.commandInputs.itemById('edgeSelect').isVisible = True  
            changedInput.commandInputs.itemById('edgeSelect').hasFocus = True

            selectionDict = {hash(changedInput.selection(i).entity.entityToken): changedInput.selection(i).entity \
                             for i in range(changedInput.selectionCount)}
            
            addedFaces = set(self.selectedFaces.keys()) ^ set(selectionDict.keys()) #get difference -> results in 

            for faceId in addedFaces:
                changedEntity = selectionDict[faceId] #changedInput.selection(changedInput.selectionCount-1).entity
                activeOccurrenceId = hash(changedEntity.assemblyContext.entityToken) \
                                    if changedEntity.assemblyContext \
                                        else hash(changedEntity.body.entityToken)

                faces = self.selectedOccurrences.get(activeOccurrenceId, [])
                    
                faces += (t := [DbFace(
                        parent = self, 
                        face = changedEntity,
                        params = self.param,
                        commandInputsEdgeSelect = changedInput.commandInputs.itemById('edgeSelect')
                        )])
                self.selectedOccurrences[activeOccurrenceId] = faces # adds a face to a list of faces associated with this occurrence
                self.selectedFaces.update( {faceObj.faceId: faceObj for faceObj in t})
                [self.selectedFaces[faceId].selectAll() for faceId in addedFaces] 
                changedInput.commandInputs.itemById('faceSelect').hasFocus = True
            return
            #end of processing faces
        #==============================================================================
        #         Processing changed edge selection            
        #==============================================================================

        if len(self.selectedEdges) > changedInput.selectionCount:
            #==============================================================================
            #             an edge has been removed
            #==============================================================================
            
            changedSelectionList = [changedInput.selection(i).entity for i in range(changedInput.selectionCount)]
            changedEdgeIdSet = set(map(calcId, changedSelectionList))  # converts list of edges to a list of their edgeIds
            missingEdges = (set(self.selectedEdges.keys()) - changedEdgeIdSet)
            [self.selectedEdges[missingEdge].deselect for missingEdge in missingEdges]
            # Note - let the user manually unselect the face if they want to choose a different face

            return
            # End of processing removed edge 
        else:
            #==============================================================================
            #         Start of adding a selected edge
            #         Edge has been added - assume that the last selection entity is the one added
            #==============================================================================
            edge:adsk.fusion.BRepEdge = changedInput.selection(changedInput.selectionCount - 1).entity
            self.selectedEdges[calcId(edge)].select # Get selectedFace then get selectedEdge, then call function

    def parseInputs(self, cmdInputs):
        '''==============================================================================
           put the selections into variables that can be accessed by the main routine            
           ==============================================================================
       '''
        inputs = {inp.id: inp for inp in cmdInputs}

        self.param.logging = self.loggingLevels[inputs['logging'].selectedItem.name]
        self.logHandler.setLevel(self.param.logging)

        self.logger.debug('Parsing inputs')

        self.param.toolDiaStr = inputs['toolDia'].expression
        self.param.toolDiaOffsetStr = inputs['toolDiaOffset'].expression
        self.param.benchmark = inputs['benchmark'].value
        self.param.dbType = inputs['dogboneType'].selectedItem.name
        self.param.minimalPercent = inputs['minimalPercent'].value
        self.param.fromTop = (inputs['depthExtent'].selectedItem.name == 'From Top Face')
        self.param.parametric = (inputs['modeRow'].selectedItem.name == 'Parametric')
        self.param.longSide = (inputs['mortiseType'].selectedItem.name == 'On Long Side')
        self.param.angleDetectionGroup = inputs['angleDetectionGroup'].isExpanded
        self.param.acuteAngle = inputs['acuteAngle'].value
        self.param.obtuseAngle = inputs['obtuseAngle'].value
        self.param.minAngleLimit = inputs['minSlider'].valueOne
        self.param.maxAngleLimit = inputs['maxSlider'].valueOne
        self.param.expandModeGroup = (inputs['modeGroup']).isExpanded
        self.param.expandSettingsGroup = (inputs['settingsGroup']).isExpanded

        self.logger.debug(f'self.param.fromTop = {self.param.fromTop}')
        self.logger.debug(f'self.param.dbType = {self.param.dbType}')
        self.logger.debug(f'self.param.parametric = {self.param.parametric}')
        self.logger.debug(f'self.param.toolDiaStr = {self.param.toolDiaStr}')
        self.logger.debug(f'self.param.toolDia = {self.param.toolDia}')
        self.logger.debug(f'self.param.toolDiaOffsetStr = {self.param.toolDiaOffsetStr}')
        self.logger.debug(f'self.param.toolDiaOffset = {self.param.toolDiaOffset}')
        self.logger.debug(f'self.param.benchmark = {self.param.benchmark}')
        self.logger.debug(f'self.param.mortiseType = {self.param.longSide}')
        self.logger.debug(f'self.param.expandModeGroup = {self.param.expandModeGroup}')
        self.logger.debug(f'self.param.expandSettingsGroup = {self.param.expandSettingsGroup}')
        
        self.edges = []
        self.faces = []
        
        for i in range(inputs['edgeSelect'].selectionCount):
            entity = inputs['edgeSelect'].selection(i).entity
            if entity.objectType == adsk.fusion.BRepEdge.classType():
                self.edges.append(entity)
        for i in range(inputs['faceSelect'].selectionCount):
            entity = inputs['faceSelect'].selection(i).entity
            if entity.objectType == adsk.fusion.BRepFace.classType():
                self.faces.append(entity)
                
    def initLogger(self):
        self.logger = logging.getLogger('dogbone')
        self.formatter = logging.Formatter('%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s')
        self.logHandler = logging.FileHandler(os.path.join(_appPath, 'dogbone.log'), mode='w')
        self.logHandler.setFormatter(self.formatter)
        self.logHandler.flush()
        self.logger.addHandler(self.logHandler)
        
    def closeLogger(self):
        for handler in self.logger.handlers:
            handler.flush()
            handler.close()

    @eventHandler(handler_cls = adsk.core.CommandEventHandler)
    def onExecute(self, args):
        start = time.time()

        self.logger.log(0, 'logging Level = %(levelname)')
        self.parseInputs(args.firingEvent.sender.commandInputs)
        self.logHandler.setLevel(self.param.logging)
        self.logger.setLevel(self.param.logging)

        self.writeDefaults()

        if self.param.parametric:
            userParams:adsk.fusion.UserParameters = _design.userParameters
            
            #set up parameters, so that changes can be easily made after dogbones have been inserted
            if not userParams.itemByName('dbToolDia'):
                dValIn = adsk.core.ValueInput.createByString(self.param.toolDiaStr)
                dParameter = userParams.add('dbToolDia', dValIn, _design.unitsManager.defaultLengthUnits, '')
                dParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbToolDia')
                uParam.expression = self.param.toolDiaStr
                uParam.isFavorite = True
                
            if not userParams.itemByName('dbOffset'):
                rValIn = adsk.core.ValueInput.createByString(self.param.toolDiaOffsetStr)
                rParameter = userParams.add('dbOffset',rValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbOffset')
                uParam.expression = self.param.toolDiaOffsetStr
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbRadius'):
                rValIn = adsk.core.ValueInput.createByString('(dbToolDia + dbOffset)/2')
                rParameter = userParams.add('dbRadius',rValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbRadius')
                uParam.expression = '(dbToolDia + dbOffset)/2'
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbMinPercent'):
                rValIn = adsk.core.ValueInput.createByReal(self.param.minimalPercent)
                rParameter = userParams.add('dbMinPercent',rValIn, '', '')
                rParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbMinPercent')
                uParam.value = self.param.minimalPercent
                uParam.comment = ''
                uParam.isFavorite = True

            if not userParams.itemByName('dbHoleOffset'):
                oValIn = adsk.core.ValueInput.createByString('dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.param.dbType == 'Minimal Dogbone' else 'dbRadius' if self.param.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)')
                oParameter = userParams.add('dbHoleOffset', oValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbHoleOffset')
                uParam.expression = 'dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.param.dbType == 'Minimal Dogbone' else 'dbRadius' if self.param.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)'
                uParam.comment = 'Do NOT change formula'

            self.radius = userParams.itemByName('dbRadius').value
            self.offset = adsk.core.ValueInput.createByString('dbOffset')
            self.offset = adsk.core.ValueInput.createByReal(userParams.itemByName('dbHoleOffset').value)

            self.createParametricDogbones()

        else: #Static dogbones

            self.radius = (self.param.toolDia + self.param.toolDiaOffset) / 2
            self.offset = self.radius / sqrt(2)  * (1 + self.param.minimalPercent/100) if self.param.dbType == 'Minimal Dogbone' else self.radius if self.param.dbType == 'Mortise Dogbone' else self.radius / sqrt(2)
            
            self.createStaticDogbones()
        
        self.logger.info('all dogbones complete\n-------------------------------------------\n')

        self.closeLogger()
        
        if self.param.benchmark:
            dbUtils.messageBox(f"Benchmark: {time.time() - start:.02f} sec processing {len(self.edges)} edges")


    ################################################################################        
    @eventHandler(handler_cls = adsk.core.ValidateInputsEventHandler)
    def onValidate(self, args):
        cmd:adsk.core.ValidateInputsEventArgs = args
        cmd = args.firingEvent.sender

        for input in cmd.commandInputs:
            if input.id == 'faceSelect':
                if input.selectionCount < 1:
                    args.areInputsValid = False
            elif input.id == 'toolDia':
                if input.value <= 0:
                    args.areInputsValid = False
                    
    @eventHandler(handler_cls = adsk.core.SelectionEventHandler)                
    def onFaceSelect(self, args):
        '''==============================================================================
            Routine gets called with every mouse movement, if a commandInput select is active                   
           ==============================================================================
       '''
        eventArgs:adsk.core.SelectionEventArgs = args
        # Check which selection input the event is firing for.
        activeIn = eventArgs.firingEvent.activeInput
        if activeIn.id != 'faceSelect' and activeIn.id != 'edgeSelect':
            return # jump out if not dealing with either of the two selection boxes
        
        if activeIn.id == 'faceSelect':
            #==============================================================================
            # processing activities when faces are being selected
            #        selection filter is limited to planar faces
            #        makes sure only valid occurrences and components are selectable
            #==============================================================================

            if not len( self.selectedOccurrences ): #get out if the face selection list is empty
                eventArgs.isSelectable = True
                return
            if not eventArgs.selection.entity.assemblyContext:
                # dealing with a root component body

                activeBodyName = hash(eventArgs.selection.entity.body.entityToken)
                try:            
                    faces = self.selectedOccurrences[activeBodyName]
                    for face in faces:
                        if face.isSelected:
                            primaryFace = face
                            break
                    else:
                        eventArgs.isSelectable = True
                        return
                except (KeyError, IndexError) as e:
                    return

                primaryFaceNormal = dbUtils.getFaceNormal(primaryFace.face)
                if primaryFaceNormal.isParallelTo(dbUtils.getFaceNormal(eventArgs.selection.entity)):
                    eventArgs.isSelectable = True
                    return
                eventArgs.isSelectable = False
                return
            # End of root component face processing
            
            #==============================================================================
            # Start of occurrence face processing              
            #==============================================================================
            activeOccurrence = eventArgs.selection.entity.assemblyContext
            activeOccurrenceId = hash(activeOccurrence.entityToken)
            activeComponent = activeOccurrence.component
            
            # we got here because the face is either not in root or is on the existing selected list    
            # at this point only need to check for duplicate component selection - Only one component allowed, to save on conflict checking
            try:
                selectedComponentList = [x[0].face.assemblyContext.component for x in self.selectedOccurrences.values() if x[0].face.assemblyContext]
            except KeyError:
               eventArgs.isSelectable = True
               return

            if activeComponent not in selectedComponentList:
                    eventArgs.isSelectable = True
                    return

            if activeOccurrenceId not in self.selectedOccurrences:  #check if mouse is over a face that is not already selected
                eventArgs.isSelectable = False
                return
                
            try:            
                faces = self.selectedOccurrences[activeOccurrenceId]
                for face in faces:
                    if face.isSelected:
                        primaryFace = face
                        break
                    else:
                        eventArgs.isSelectable = True
                        return
            except KeyError:
                return
            primaryFaceNormal = dbUtils.getFaceNormal(primaryFace.face)
            if primaryFaceNormal.isParallelTo(dbUtils.getFaceNormal(eventArgs.selection.entity)):
                eventArgs.isSelectable = True
                return
            eventArgs.isSelectable = False
            return
            # end selecting faces
            
        else:
            #==============================================================================
            #             processing edges associated with face - edges selection has focus
            #==============================================================================
            if self.addingEdges:
                return
            selected = eventArgs.selection
            currentEdge:adsk.fusion.BRepEdge = selected.entity
            activeOccurrence = eventArgs.selection.entity.assemblyContext
            if eventArgs.selection.entity.assemblyContext:
                activeOccurrenceId = hash(activeOccurrence.entityToken)
            else:
                activeOccurrenceId = hash(eventArgs.selection.entity.body.entityToken) 

            edgeId = hash(currentEdge.entityToken) 
            if (edgeId in self.selectedEdges.keys()):
                eventArgs.isSelectable = True
            else:
                eventArgs.isSelectable = False
            return

    @property
    def originPlane(self):
        return _rootComp.xZConstructionPlane if self.yUp else _rootComp.xYConstructionPlane

    # The main algorithm for parametric dogbones
    def createParametricDogbones(self):
        self.logger.info('Creating parametric dogbones')
        self.errorCount = 0
        if not _design:
            raise RuntimeError('No active Fusion design')
        holeInput:adsk.fusion.HoleFeatureInput = None
        offsetByStr = adsk.core.ValueInput.createByString('dbHoleOffset')
        centreDistance = self.radius*(1+self.param.minimalPercent/100 if self.param.dbType=='Minimal Dogbone' else  1)
        
        for occurrenceFaces in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition

            comp:adsk.fusion.Component = occurrenceFaces[0].component
            occ:adsk.fusion.Occurrence = occurrenceFaces[0].occurrence

            if self.param.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(occurrenceFaces[0].native)
                self.logger.info(f'Processing holes from top face - {topFace.body.name}')

            for selectedFace in occurrenceFaces:
                if len(selectedFace.selectedEdges.values()) <1:
                    self.logger.debug('Face has no edges')
                    
                face = selectedFace.native
                
                if not face.isValid:
                    self.logger.debug('revalidating Face')
                    face = selectedFace.revalidate()
                self.logger.debug(f'Processing Face = {face.tempId}')
              
                #faceNormal = dbUtils.getFaceNormal(face.nativeObject)
                if self.param.fromTop:
                    self.logger.debug(f'topFace type {type(topFace)}')
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace = reValidateFace(comp, topFaceRefPoint)

                    topFace = makeNative(topFace)
                       
                    self.logger.debug(f'topFace isValid = {topFace.isValid}')
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(face, topFace)
                    self.logger.debug(f'creating transformVector to topFace = ({transformVector.x},{transformVector.y},{transformVector.z}) length = {transformVector.length}')
                                
                for selectedEdge in selectedFace.selectedEdges.values():
                    
                    self.logger.debug(f'Processing edge - {selectedEdge.edge.tempId}')

                    if not selectedEdge.isSelected:
                        self.logger.debug('  Not selected. Skipping...')
                        continue

                    if not face.isValid:
                        self.logger.debug('Revalidating face')
                        face = selectedFace.revalidate() # = reValidateFace(comp, selectedFace.refPoint)

                    if not selectedEdge.edge.isValid:
                        continue # edges that have been processed already will not be valid any more - at the moment this is easier than removing the 
    #                    affected edge from self.edges after having been processed
                    edge = selectedEdge.native
                    try:
                        if not dbUtils.isEdgeAssociatedWithFace(face, edge):
                            continue  # skip if edge is not associated with the face currently being processed
                    except:
                        pass
                    
                    startVertex:adsk.fusion.BRepVertex = dbUtils.getVertexAtFace(face, edge)
                    extentToEntity = dbUtils.findExtent(face, edge)

                    extentToEntity = makeNative(extentToEntity)
                    self.logger.debug(f'extentToEntity - {extentToEntity.isValid}')
                    if not extentToEntity.isValid:
                        self.logger.debug('To face invalid')

                    try:
                        (edge1, edge2) = dbUtils.getCornerEdgesAtFace(face, edge)
                    except:
                        self.logger.exception('Failed at findAdjecentFaceEdges')
                        dbUtils.messageBox(f'Failed at findAdjecentFaceEdges:\n{traceback.format_exc()}')
                    
                    centrePoint = makeNative(startVertex).geometry.copy()
                        
                    selectedEdgeFaces = makeNative(selectedEdge.edge).faces
                    
                    dirVect:adsk.core.Vector3D = dbUtils.getFaceNormal(selectedEdgeFaces[0]).copy()
                    dirVect.add(dbUtils.getFaceNormal(selectedEdgeFaces[1]))
                    dirVect.normalize()
                    dirVect.scaleBy(centreDistance)  #ideally radius should be linked to parameters, 
 
                    if self.param.dbType == 'Mortise Dogbone':
                        direction0 = dbUtils.correctedEdgeVector(edge1,startVertex) 
                        direction1 = dbUtils.correctedEdgeVector(edge2,startVertex)
                        
                        if self.longSide:
                            if (edge1.length > edge2.length):
                                dirVect = direction0
                                edge1OffsetByStr = adsk.core.ValueInput.createByReal(0)
                                edge2OffsetByStr = offsetByStr
                            else:
                                dirVect = direction1
                                edge2OffsetByStr = adsk.core.ValueInput.createByReal(0)
                                edge1OffsetByStr = offsetByStr
                        else:
                            if (edge1.length > edge2.length):
                                dirVect = direction1
                                edge2OffsetByStr = adsk.core.ValueInput.createByReal(0)
                                edge1OffsetByStr = offsetByStr
                            else:
                                dirVect = direction0
                                edge1OffsetByStr = adsk.core.ValueInput.createByReal(0)
                                edge2OffsetByStr = offsetByStr
                    else:
                        dirVect:adsk.core.Vector3D = dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[0])).copy()
                        dirVect.add(dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[1])))
                        edge1OffsetByStr = offsetByStr
                        edge2OffsetByStr = offsetByStr

                    centrePoint.translateBy(dirVect)
                    self.logger.debug(f'centrePoint = ({centrePoint.x},{centrePoint.y},{centrePoint.z})')

                    if self.param.fromTop:
                        centrePoint.translateBy(transformVector)
                        self.logger.debug(f'centrePoint at topFace = {centrePoint.asArray()}')
                        holePlane = topFace if self.param.fromTop else face
                        if not holePlane.isValid:
                            holePlane = reValidateFace(comp, topFaceRefPoint)
                    else:
                        holePlane = makeNative(face)
                         
                    holes =  comp.features.holeFeatures
                    holeInput = holes.createSimpleInput(adsk.core.ValueInput.createByString('dbRadius*2'))
#                    holeInput.creationOccurrence = occ #This needs to be uncommented once AD fixes component copy issue!!
                    holeInput.isDefaultDirection = True
                    holeInput.tipAngle = adsk.core.ValueInput.createByString('180 deg')
#                    holeInput.participantBodies = [face.nativeObject.body if occ else face.body]  #Restore this once AD fixes occurrence bugs
                    holeInput.participantBodies = [makeNative(face.body)]
                    
                    self.logger.debug(f'extentToEntity before setPositionByPlaneAndOffsets - {extentToEntity.isValid}')
                    holeInput.setPositionByPlaneAndOffsets(holePlane, centrePoint, edge1, edge1OffsetByStr, edge2, edge2OffsetByStr)
                    self.logger.debug(f'extentToEntity after setPositionByPlaneAndOffsets - {extentToEntity.isValid}')
                    holeInput.setOneSideToExtent(extentToEntity, False)
                    self.logger.info(f'hole added to list - {centrePoint.asArray()}')
 
                    holeFeature = holes.add(holeInput)
                    holeFeature.name = 'dogbone'
                    holeFeature.isSuppressed = True
                    
                for hole in holes:
                    if hole.name[:7] != 'dogbone':
                        break
                    hole.isSuppressed = False
                    
            endTlMarker = _design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = _design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'dogbone'
# self.logger.debug('doEvents - allowing display to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox(f'Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created')

    def createStaticDogbones(self):
        self.logger.info('Creating static dogbones')
        self.errorCount = 0
        if not _design:
            raise RuntimeError('No active Fusion design')
        
        tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

        for occurrenceFaces in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition
            comp:adsk.fusion.Component = occurrenceFaces[0].component
            occ:adsk.fusion.Occurrence = occurrenceFaces[0].occurrence 
            topFace = None  
            
            if self.param.fromTop:
                topFace, topFaceRefPoint = dbUtils.getTopFace(occurrenceFaces[0].native)
                self.logger.debug(f'topFace ref point: {topFaceRefPoint.asArray()}')
                self.logger.info(f'Processing holes from top face - {topFace.tempId}')
                self.debugFace(topFace)
                
            for selectedFace in occurrenceFaces:

                toolCollection = adsk.core.ObjectCollection.create()
                toolBodies = None
 
                for edge in selectedFace.selectedEdges:
                    if not toolBodies:
                        toolBodies = edge.getToolBody(params = self.param, topFace = topFace)
                    else:
                        tempBrepMgr.booleanOperation(toolBodies, edge.getToolBody(params = self.param, topFace = topFace), adsk.fusion.BooleanTypes.UnionBooleanType)

                baseFeatures = _rootComp.features.baseFeatures
                baseFeature = baseFeatures.add()
                baseFeature.name = 'dogbone'

                baseFeature.startEdit()
                dbB = _rootComp.bRepBodies.add(toolBodies, baseFeature)
                dbB.name = 'dogboneTool'
                baseFeature.finishEdit()

                toolCollection.add(baseFeature.bodies.item(0))

                activeBody = selectedFace.native.body

                combineInput = _rootComp.features.combineFeatures.createInput(targetBody = activeBody, 
                                                                            toolBodies = toolCollection)
                combineInput.isKeepToolBodies = False
                combineInput.isNewComponent = False
                combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                combine = _rootComp.features.combineFeatures.add(combineInput)

                    
            endTlMarker = _design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = _design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'dogbone'
# self.logger.debug('doEvents - allowing fusion to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox(f'Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created')
            
dog = DogboneCommand()


def run(context):
    try:
        dog.addButton()
        # dog.addRefreshButton()
    except:
        dbUtils.messageBox(traceback.format_exc())


def stop(context):
    try:
        _ui.terminateActiveCommand()
        adsk.terminate()
        dog.removeButton()
    except:
        dbUtils.messageBox(traceback.format_exc())

