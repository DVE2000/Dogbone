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
 
from collections import defaultdict

import adsk.core, adsk.fusion
import math
import traceback
import os
import json

import time
from . import dbutils as dbUtils
from .decorators import eventHandler
from math import sqrt as sqrt

#constants - to keep attribute group and names consistent
DOGBONEGROUP = 'dogBoneGroup'
# FACE_ID = 'faceID'
REV_ID = 'revId'
ID = 'id'
DEBUGLEVEL = logging.NOTSET



# Generate an edgeId or faceId from object
# calcId = lambda x: str(x.tempId) + ':' + x.assemblyContext.name.split(':')[-1] if x.assemblyContext else str(x.tempId) + ':' + x.body.name
calcId = lambda x: hash(x.entityToken) # if x.assemblyContext else str(x.tempId) + ':' + x.body.name
makeNative = lambda x: x.nativeObject if x.nativeObject else x
reValidateFace = lambda comp, x: comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)

# Globals
_app = adsk.core.Application.get()
_design = _app.activeProduct
_ui = _app.userInterface
_rootComp = _design.rootComponent

class DbFace:
    def __init__(self, parent, face, commandInputsEdgeSelect):
        self.parent:DogboneCommand = parent
        self.face = face # BrepFace
        self._faceId = hash(face.entityToken)
        self.faceNormal = dbUtils.getFaceNormal(face)
        self._refPoint = face.nativeObject.pointOnFace if face.assemblyContext else face.pointOnFace
        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self._selected = True
        self._associatedEdgesDict = {} # Keyed with edge
        self.brepEdges = [] # used for quick checking if an edge is already included (below)

        #==============================================================================
        #             this is where inside corner edges, dropping down from the face are processed
        #==============================================================================

        faceNormal = dbUtils.getFaceNormal(face)

        for edge in self.face.body.edges:
                if edge.isDegenerate:
                    continue
                if edge in self.brepEdges:
                    continue
                try:
                    if edge.geometry.curveType != adsk.core.Curve3DTypes.Line3DCurveType:
                        continue
                    vector = edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
                    if vector.isPerpendicularTo(faceNormal):
                        continue
                    if edge.faces.item(0).geometry.objectType != adsk.core.Plane.classType():
                        continue
                    if edge.faces.item(1).geometry.objectType != adsk.core.Plane.classType():
                        continue              
                    if edge.startVertex not in face.vertices:
                        if edge.endVertex not in face.vertices:
                            continue
                        else:
                            vector = edge.endVertex.geometry.vectorTo(edge.startVertex.geometry)
                    if vector.dotProduct(faceNormal) >= 0:
                        continue
                    if dbUtils.getAngleBetweenFaces(edge) > math.pi:
                        continue

                    # activeEdgeName = edge.assemblyContext.name.split(':')[-1] if edge.assemblyContext else edge.body.name
                    edgeId = hash(edge.entityToken) #str(edge.tempId)+':'+ activeEdgeName
                # edgeId = hash(edge.entityToken) #str(edge.tempId)+':'+ activeEdgeName
                    parent.selectedEdges[edgeId] = self._associatedEdgesDict[edgeId] = DbEdge(edge = edge, parentFace = self)
                    self.brepEdges.append(edge)
                    parent.addingEdges = True
                    self.commandInputsEdgeSelect.addSelection(edge)
                    parent.addingEdges = False
                    parent.selectedEdgesSet  |= {edgeId}
                except:
                    dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))

    def __hash__(self):
        return self.faceId

    def __del__(self):
        pass

    @property
    def selectAll(self):
        self._selected = True
        self.parent.addingEdges = True
        [(selectedEdge.select, 
          _ui.activeSelections.add(selectedEdge.edge))
        for selectedEdge in self._associatedEdgesDict.values()]
        self.parent.addingEdges = False

    @property
    def deselectAll(self):
        self._selected = False
        self.parent.addingEdges = True
        [(selectedEdge.deselect, 
          _ui.activeSelections.removeByEntity(selectedEdge.edge))
          for selectedEdge in self._associatedEdgesDict.values()]
        self.parent.addingEdges = False

    @property
    def refPoint(self):
        return self._refPoint

    @property
    def select(self):
        self._selected = True

    @property
    def deselect(self):
        self._selected = False

    @property
    def isSelected(self):
        return self._selected
    
    @property
    def edgeIdSet(self):
        return set(self._associatedEdgesDict.keys())
    
    @property
    def selectedEdges(self):
        return [edgeObj for edgeObj in self._associatedEdgesDict.values() if edgeObj.isSelected]
    
    @property
    def deleteEdges(self):
        [(_ui.activeSelections.removeByEntity(edgeObj.edge),
           self.parent.selectedEdges.pop(edgeId) )
           for edgeId, edgeObj in self._associatedEdgesDict.items()]
        del self._associatedEdgesDict

    @property
    def faceId(self):
        return self._faceId

    @property
    def component(self)->adsk.fusion.Component:
        return self.face.assemblyContext.component if self.face.assemblyContext else _rootComp
  
    @property
    def occurrence(self)->adsk.fusion.Occurrence:
        return self.face.assemblyContext if self.face.assemblyContext else None

    @property
    def native(self):
        return self.face.nativeObject if self.face.nativeObject else self.face

    @property
    def revalidate(self):
        return self.component.findBRepUsingPoint(self.face, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)

class DbEdge:
    def __init__(self, edge:adsk.fusion.BRepEdge, parentFace:DbFace):
        self.edge = edge
        self._edgeId = hash(edge.entityToken)
        self._selected = True
        self._parentFace = parentFace

    def __hash__(self):
        return self._edgeId

    @property
    def select(self):
        self._selected = True

    @property
    def deselect(self):
        self._selected = False

    @property
    def isSelected(self):
        return self._selected
    
    def faceObj(self):
        return self._parentFace
    
    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, DbEdge):
            return __o.hash == self._hash
        if isinstance(__o, str):
            return hash(__o) == self._hash
        if isinstance(__o, adsk.fusion.BRepEdge):
            return __o == self._edge
        return NotImplemented
    
    def __hash__(self) -> int:
        return self._hash

    @property
    def native(self):
        return self.edge.nativeObject if self.edge.nativeObject else self.edge
class DogboneCommand(object):
    COMMAND_ID = "dogboneBtn"
    
    # faceAssociations = {}
    defaultData = {}
    registeredEdgesDict = {}
    
    faces = []
    edges = []
    
    selectedOccurrences = {} 
    selectedFaces = {} #key: face.entityToken value:[DbFace,...]
    selectedEdges = {} #kay: edge.entityToken value:[DbEdge, ...]
    selectedEdgesSet = set()

    def __init__(self):

        self.offStr = "0"
        self.offVal = None
        self.circStr = "0.25 in"
        self.circVal = None
        self.benchmark = False
        self.errorCount = 0
#        self.boneDirection = "top"
        self.dbType = 'Normal Dogbone'
        self.longside = True
        self.minimalPercent = 10.0
        self.faceSelections = adsk.core.ObjectCollection.create()
        self.fromTop = False

        self.addingEdges = 0
        self.parametric = True
        self.logging = 0
        self.loggingLevels = {'Notset':0,'Debug':10,'Info':20,'Warning':30,'Error':40}

        self.expandModeGroup = True
        self.expandSettingsGroup = False
#        self.loggingLevelsLookUp = {self.loggingLevels[k]:k for k in self.loggingLevels}
        self.levels = {}

        self.handlers = dbUtils.HandlerHelper()

        self.appPath = os.path.dirname(os.path.abspath(__file__))
        

    def writeDefaults(self):
        self.logger.info('config file write')

        self.defaultData['offStr'] = self.offStr
        self.defaultData['offVal'] = self.offVal
        self.defaultData['circStr'] = self.circStr
        self.defaultData['circVal'] = self.circVal
            #self.defaultData['!outputUnconstrainedGeometry:' = str(self.outputUnconstrainedGeometry))
        self.defaultData['benchmark'] = self.benchmark
#        self.defaultData['boneDirection'] = self.boneDirection
        self.defaultData['dbType'] = self.dbType
        self.defaultData['minimalPercent'] = self.minimalPercent
        self.defaultData['fromTop'] = self.fromTop
        self.defaultData['parametric'] = self.parametric
        self.defaultData['logging'] = self.logging
        self.defaultData['mortiseType'] = self.longside
        self.defaultData['expandModeGroup'] = self.expandModeGroup
        self.defaultData['expandSettingsGroup'] = self.expandSettingsGroup
        
        json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'w', encoding='UTF-8')
        json.dump(self.defaultData, json_file, ensure_ascii=False)
        json_file.close()
            #file.write('!limitParticipation:' = str(self.limitParticipation))
            #file.write('!minimumAngle:' = str(self.minimumAngle))
            #file.write('!maximumAngle:' = str(self.maximumAngle))
    
    def readDefaults(self): 
#        self.logger.info('config file read')
        if not os.path.isfile(os.path.join(self.appPath, 'defaults.dat')):
            return
        json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'r', encoding='UTF-8')
        try:
            self.defaultData = json.load(json_file)
        except ValueError:
            self.logger.error('default.dat error')
            json_file.close()
            json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'w', encoding='UTF-8')
            json.dump(self.defaultData, json_file, ensure_ascii=False)
            return

        json_file.close()
        try:
            self.offStr = self.defaultData['offStr']
            self.offVal = self.defaultData['offVal']
            self.circStr = self.defaultData['circStr']
            self.circVal = self.defaultData['circVal']
                #elif var == 'outputUnconstrainedGeometry': self.outputUnconstrainedGeometry = val == 'True'
            self.benchmark = self.defaultData['benchmark']
#            self.boneDirection = self.defaultData['boneDirection']
            self.dbType = self.defaultData['dbType']
            self.minimalPercent = self.defaultData['minimalPercent']
            self.fromTop = self.defaultData['fromTop']
            self.parametric = self.defaultData['parametric']
            self.logging = self.defaultData['logging']
            self.longside = self.defaultData['mortiseType']
            self.expandModeGroup = self.defaultData['expandModeGroup']
            self.expandSettingsGroup = self.defaultData['expandSettingsGroup']

        except KeyError: 
        
#            self.logger.error('Key error on read config file')
        #if there's a keyError - means file is corrupted - so, rewrite it with known existing defaultData - it will result in a valid dict, 
        # but contents may have extra, superfluous  data
            json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'w', encoding='UTF-8')
            json.dump(self.defaultData, json_file, ensure_ascii=False)
            json_file.close()
            return
            
    def debugFace(self, face):
        if self.logger.level < logging.DEBUG:
            return
        for edge in face.edges:
            self.logger.debug(f'edge {edge.tempId}; startVertex: {edge.startVertex.geometry.asArray()}; endVertex: {edge.endVertex.geometry.asArray()}')

        return

    def addButton(self):
        # clean up any crashed instances of the button if existing
        try:
            self.removeButton()
        except:
            pass

        # Create button definition and command event handler
        buttonDogbone = _ui.commandDefinitions.addButtonDefinition(
            self.COMMAND_ID, 'Dogbone', 'Creates dogbones at all inside corners of a face', 'Resources')

        # buttonDogbone.commandCreated.add(self.handlers.make_handler(adsk.core.CommandCreatedEventHandler,
        #                                                             self.onCreate))
        
        self.onCreate(event=buttonDogbone.commandCreated)
        # Create controls for Manufacturing Workspace
        mfgEnv = _ui.workspaces.itemById('MfgWorkingModelEnv')
        mfgTab = mfgEnv.toolbarTabs.itemById('MfgSolidTab')
        mfgSolidPanel = mfgTab.toolbarPanels.itemById('SolidCreatePanel')
        buttonControlMfg = mfgSolidPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')

        # Make the button available in the Mfg panel.
        buttonControlMfg.isPromotedByDefault = True
        buttonControlMfg.isPromoted = True

        # CReate controls for the Design Workspace
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

    @eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
    def onCreate(self, args:adsk.core.CommandCreatedEventArgs):
        """
        important persistent variables:        
        self.selectedOccurrences  - Lookup dictionary 
        key: activeOccurrenceId 
        value: list of selectedFaces
            provides a quick lookup relationship between each occurrence and in particular which faces have been selected.  
            The 1st selected face in the list is always the primary face
        
        self.selectedFaces - Lookup dictionary 
        key: faceId = str(face tempId:occurrenceNumber) 
        value: [BrepFace, objectCollection of edges, reference point on nativeObject Face]
            provides fast method of getting Brep entities associated with a faceId

        self.selectedEdges - reverse lookup 
        key: edgeId = str(edgeId:occurrenceNumber) 
        value: str(face tempId:occurrenceNumber)
            provides fast method of finding face that owns an edge
        """
        inputs:adsk.core.CommandCreatedEventArgs = args
        self.errorCount = 0
        self.faceSelections.clear()
        
        argsCmd:adsk.core.Command = args
        
        if _design.designType != adsk.fusion.DesignTypes.ParametricDesignType :
            returnValue = _ui.messageBox('DogBone only works in Parametric Mode \n Do you want to change modes?', 'Change to Parametric mode', adsk.core.MessageBoxButtonTypes.YesNoButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            _design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        self.readDefaults()

        self.selectedEdges = {}
        self.selectedFaces = {}
        self.selectedOccurrences = {}

        inputs:adsk.core.CommandInputs = inputs.command.commandInputs
        
        selInput0 = inputs.addSelectionInput(
            'faceSelect', 'Face',
            'Select a face to apply dogbones to all internal corner edges')
        selInput0.tooltip ='Select a face to apply dogbones to all internal corner edges\n*** Select faces by clicking on them. DO NOT DRAG SELECT! ***' 
#        selInput0.addSelectionFilter('LinearEdges')
        selInput0.addSelectionFilter('PlanarFaces')
        selInput0.setSelectionLimits(1,0)
        
        selInput1 = inputs.addSelectionInput(
            'edgeSelect', 'DogBone Edges',
            'Select or de-select any internal edges dropping down from a selected face (to apply dogbones to')
#        selInput0.addSelectionFilter('LinearEdges')
        selInput1.tooltip ='Select or de-select any internal edges dropping down from a selected face (to apply dogbones to)' 
        selInput1.addSelectionFilter('LinearEdges')
        selInput1.setSelectionLimits(1,0)
        selInput1.isVisible = False
                
        inp = inputs.addValueInput(
            'circDiameter', 'Tool Diameter               ', _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.circStr))
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."
        
        offsetInp = inputs.addValueInput(
            'offset', 'Tool diameter offset', _design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.offStr))
        offsetInp.tooltip = "Increases the tool diameter"
        offsetInp.tooltipDescription = "Use this to create an oversized dogbone.\n"\
                                        "Normally set to 0.  \n"\
                                        "A value of .010 would increase the dogbone diameter by .010 \n"\
                                        "Used when you want to keep the tool diameter and oversize value separate"
        
        modeGroup:adsk.core.GroupCommandInput = inputs.addGroupCommandInput('modeGroup', 'Mode')
        modeGroup.isExpanded = self.expandModeGroup
        modeGroupChildInputs = modeGroup.children
        
        modeRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('modeRow', 'Mode', False)
        modeRowInput.listItems.add('Static', not self.parametric, 'resources/staticMode' )
        modeRowInput.listItems.add('Parametric', self.parametric, 'resources/parametricMode' )
        modeRowInput.tooltipDescription = "Static dogbones do not move with the underlying component geometry. \n" \
                                "\nParametric dogbones will automatically adjust position with parametric changes to underlying geometry. " \
                                "Geometry changes must be made via the parametric dialog.\nFusion has more issues/bugs with these!"
        
        typeRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('dogboneType', 'Type', False)
        typeRowInput.listItems.add('Normal Dogbone', self.dbType == 'Normal Dogbone', 'resources/normal' )
        typeRowInput.listItems.add('Minimal Dogbone', self.dbType == 'Minimal Dogbone', 'resources/minimal' )
        typeRowInput.listItems.add('Mortise Dogbone', self.dbType == 'Mortise Dogbone', 'resources/hidden' )
        typeRowInput.tooltipDescription = "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit " \
                                            "that, for example, will require a larger force to insert a tenon into a mortise.\n" \
                                            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n" \
                                            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        
        mortiseRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('mortiseType', 'Mortise Type', False)
        mortiseRowInput.listItems.add('On Long Side', self.longside, 'resources/hidden/longside' )
        mortiseRowInput.listItems.add('On Short Side', not self.longside, 'resources/hidden/shortside' )
        mortiseRowInput.tooltipDescription = "Along Longest will have the dogbones cut into the longer sides." \
                                             "\nAlong Shortest will have the dogbones cut into the shorter sides."
        mortiseRowInput.isVisible = self.dbType == 'Mortise Dogbone'

        minPercentInp = modeGroupChildInputs.addValueInput(
            'minimalPercent', 'Percentage Reduction', '',
            adsk.core.ValueInput.createByReal(self.minimalPercent))
        minPercentInp.tooltip = "Percentage of tool radius added to dogBone offset."
        minPercentInp.tooltipDescription = "This should typically be left at 10%, but if the fit is too tight, it should be reduced"
        minPercentInp.isVisible = self.dbType == 'Minimal Dogbone'

        depthRowInput:adsk.core.ButtonRowCommandInput = modeGroupChildInputs.addButtonRowCommandInput('depthExtent', 'Depth Extent', False)
        depthRowInput.listItems.add('From Selected Face', not self.fromTop, 'resources/fromFace' )
        depthRowInput.listItems.add('From Top Face', self.fromTop, 'resources/fromTop' )
        depthRowInput.tooltipDescription = "When \"From Top Face\" is selected, all dogbones will be extended to the top most face\n"\
                                            "\nThis is typically chosen when you don't want to, or can't do, double sided machining."
 
        settingGroup:adsk.core.GroupCommandInput = inputs.addGroupCommandInput('settingsGroup', 'Settings')
        settingGroup.isExpanded = self.expandSettingsGroup
        settingGroupChildInputs = settingGroup.children

        benchMark = settingGroupChildInputs.addBoolValueInput("benchmark", "Benchmark time", True, "", self.benchmark)
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = "When enabled, shows overall time taken to process all selected dogbones."

        logDropDownInp:adsk.core.DropDownCommandInput = settingGroupChildInputs.addDropDownCommandInput("logging", "Logging level", adsk.core.DropDownStyles.TextListDropDownStyle)
        logDropDownInp.tooltip = "Enables logging"
        logDropDownInp.tooltipDescription = "Creates a dogbone.log file. \n" \
                     "Location: " +  os.path.join(self.appPath, 'dogBone.log')

        logDropDownInp.listItems.add('Notset', self.logging == 0)
        logDropDownInp.listItems.add('Debug', self.logging == 10)
        logDropDownInp.listItems.add('Info', self.logging == 20)

        cmd:adsk.core.Command = args.command
        # Add handlers to this command.
        self.onExecute(event=cmd.execute)
        self.onFaceSelect(event=cmd.selectionEvent)
        self.onValidate(event=cmd.validateInputs)
        self.onChange(event=cmd.inputChanged)

    #==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    #==============================================================================
    @eventHandler(handler_cls = adsk.core.InputChangedEventHandler)
    def onChange(self, args:adsk.core.InputChangedEventArgs):
        
        changedInput:adsk.core.CommandInput = args.input
#        self.logger.debug(f'input changed- {changedInput.id}')

        if changedInput.id == 'dogboneType':
            changedInput.commandInputs.itemById('minimalPercent').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Minimal Dogbone')
            changedInput.commandInputs.itemById('mortiseType').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Mortise Dogbone')
       

        if changedInput.id != 'faceSelect' and changedInput.id != 'edgeSelect':
            return

#        self.logger.debug(f'input changed- {changedInput.id}')
        if changedInput.id == 'faceSelect':

            #==============================================================================
            #            processing changes to face selections
            #==============================================================================
            if len(self.selectedFaces) > changedInput.selectionCount:               
                # a face has been removed
                
                # If all faces are removed, just iterate through all
                if changedInput.selectionCount == 0:                
                    [ faceObj.deselectAll for faceObj in self.selectedFaces.values()]
                    self.selectedFaces = {}
                    changedInput.commandInputs.itemById('edgeSelect').clearSelection()
                    changedInput.commandInputs.itemById('faceSelect').hasFocus = True                    
                    changedInput.commandInputs.itemById('edgeSelect').isVisible = False   
                    return
                
                # Else find the missing face in selection
                selectionSet = {hash(changedInput.selection(i).entity.entityToken) for i in range(changedInput.selectionCount)}
                missingFaces = set(self.selectedFaces.keys()) ^ selectionSet
                changedInput.commandInputs.itemById('edgeSelect').isVisible = True   
                changedInput.commandInputs.itemById('edgeSelect').hasFocus = True
                [(self.selectedFaces[missingFace].deleteEdges,
                   self.selectedFaces.pop(missingFace)) for missingFace in missingFaces]
                changedInput.commandInputs.itemById('faceSelect').hasFocus = True
                return
             
            #==============================================================================
            #             Face has been added - assume that the last selection entity is the one added
            #==============================================================================
            changedInput.commandInputs.itemById('edgeSelect').isVisible = True  
            changedInput.commandInputs.itemById('edgeSelect').hasFocus = True

            selectionDict = {hash(changedInput.selection(i).entity.entityToken): changedInput.selection(i).entity for i in range(changedInput.selectionCount)}
            addedFaces = set(self.selectedFaces.keys()) ^ set(selectionDict.keys())

            for faceId in addedFaces:
                changedEntity = selectionDict[faceId] #changedInput.selection(changedInput.selectionCount-1).entity
                if changedEntity.assemblyContext:
                    activeOccurrenceId = hash(changedEntity.assemblyContext.entityToken)
                else:
                    activeOccurrenceId = hash(changedEntity.body.entityToken)

                faces = self.selectedOccurrences.get(activeOccurrenceId, [])
                    
                faces += (t := [DbFace(
                        parent = self, 
                        face = selectionDict[id],
                        commandInputsEdgeSelect = changedInput.commandInputs.itemById('edgeSelect')
                        )
                        for id in addedFaces])
                self.selectedOccurrences[activeOccurrenceId] = faces # adds a face to a list of faces associated with this occurrence
                self.selectedFaces.update( {faceObj.faceId: faceObj for faceObj in t})
                [self.selectedFaces[faceId].selectAll for faceId in addedFaces] 
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

    def parseInputs(self, inputs):
        '''==============================================================================
           put the selections into variables that can be accessed by the main routine            
           ==============================================================================
       '''
        inputs = {inp.id: inp for inp in inputs}

        self.logging = self.loggingLevels[inputs['logging'].selectedItem.name]
        self.logHandler.setLevel(self.logging)

        self.logger.debug('Parsing inputs')

        self.circStr = inputs['circDiameter'].expression
        self.circVal = inputs['circDiameter'].value
        self.offStr = inputs['offset'].expression
        self.offVal = inputs['offset'].value
        self.benchmark = inputs['benchmark'].value
        self.dbType = inputs['dogboneType'].selectedItem.name
        self.minimalPercent = inputs['minimalPercent'].value
        self.fromTop = (inputs['depthExtent'].selectedItem.name == 'From Top Face')
        self.parametric = (inputs['modeRow'].selectedItem.name == 'Parametric')
        self.longside = (inputs['mortiseType'].selectedItem.name == 'On Long Side')
        self.expandModeGroup = (inputs['modeGroup']).isExpanded
        self.expandSettingsGroup = (inputs['settingsGroup']).isExpanded

        self.logger.debug(f'self.fromTop = {self.fromTop}')
        self.logger.debug(f'self.dbType = {self.dbType}')
        self.logger.debug(f'self.parametric = {self.parametric}')
        self.logger.debug(f'self.circStr = {self.circStr}')
        self.logger.debug(f'self.circDiameter = {self.circVal}')
        self.logger.debug(f'self.offStr = {self.offStr}')
        self.logger.debug(f'self.offVal = {self.offVal}')
        self.logger.debug(f'self.benchmark = {self.benchmark}')
        self.logger.debug(f'self.mortiseType = {self.longside}')
        self.logger.debug(f'self.expandModeGroup = {self.expandModeGroup}')
        self.logger.debug(f'self.expandSettingsGroup = {self.expandSettingsGroup}')
        
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
        self.logger = logging.getLogger(__name__)
        self.formatter = logging.Formatter('%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s')
#        if not os.path.isfile(os.path.join(self.appPath, 'dogBone.log')):
#            return
        self.logHandler = logging.FileHandler(os.path.join(self.appPath, 'dogbone.log'), mode='w')
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

        self.initLogger()
        self.logger.log(0, 'logging Level = %(levelname)')
        self.parseInputs(args.firingEvent.sender.commandInputs)
        self.logHandler.setLevel(self.logging)
        self.logger.setLevel(self.logging)

        self.writeDefaults()

        if self.parametric:
            userParams:adsk.fusion.UserParameters = _design.userParameters
            
            #set up parameters, so that changes can be easily made after dogbones have been inserted
            if not userParams.itemByName('dbToolDia'):
                dValIn = adsk.core.ValueInput.createByString(self.circStr)
                dParameter = userParams.add('dbToolDia', dValIn, _design.unitsManager.defaultLengthUnits, '')
                dParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbToolDia')
                uParam.expression = self.circStr
                uParam.isFavorite = True
                
            if not userParams.itemByName('dbOffset'):
                rValIn = adsk.core.ValueInput.createByString(self.offStr)
                rParameter = userParams.add('dbOffset',rValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbOffset')
                uParam.expression = self.offStr
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbRadius'):
                rValIn = adsk.core.ValueInput.createByString('(dbToolDia + dbOffset)/2')
                rParameter = userParams.add('dbRadius',rValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbRadius')
                uParam.expression = '(dbToolDia + dbOffset)/2'
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbMinPercent'):
                rValIn = adsk.core.ValueInput.createByReal(self.minimalPercent)
                rParameter = userParams.add('dbMinPercent',rValIn, '', '')
                rParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbMinPercent')
                uParam.value = self.minimalPercent
                uParam.comment = ''
                uParam.isFavorite = True

            if not userParams.itemByName('dbHoleOffset'):
                oValIn = adsk.core.ValueInput.createByString('dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.dbType == 'Minimal Dogbone' else 'dbRadius' if self.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)')
                oParameter = userParams.add('dbHoleOffset', oValIn, _design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbHoleOffset')
                uParam.expression = 'dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.dbType == 'Minimal Dogbone' else 'dbRadius' if self.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)'
                uParam.comment = 'Do NOT change formula'

            self.radius = userParams.itemByName('dbRadius').value
            self.offset = adsk.core.ValueInput.createByString('dbOffset')
            self.offset = adsk.core.ValueInput.createByReal(userParams.itemByName('dbHoleOffset').value)

            self.createParametricDogbones()

        else: #Static dogbones

            self.radius = (self.circVal + self.offVal) / 2
            self.offset = self.radius / sqrt(2)  * (1 + self.minimalPercent/100) if self.dbType == 'Minimal Dogbone' else self.radius if self.dbType == 'Mortise Dogbone' else self.radius / sqrt(2)
            
            self.createStaticDogbones()
        
        self.logger.info('all dogbones complete\n-------------------------------------------\n')

        self.closeLogger()
        
        if self.benchmark:
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
            elif input.id == 'circDiameter':
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

            # occurrenceNumber = activeOccurrenceId.split(':')[-1]
            edgeId = hash(currentEdge.entityToken) #str(currentEdge.tempId) + ':' + occurrenceNumber
            if (edgeId in self.selectedEdgesSet):
                eventArgs.isSelectable = True
            else:
                eventArgs.isSelectable = False
            return


    @property
    def design(self):
        return _app.activeProduct

    @property
    def rootComp(self):
        return _design.rootComponent

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
        centreDistance = self.radius*(1+self.minimalPercent/100 if self.dbType=='Minimal Dogbone' else  1)
        
        for occurrenceFace in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition

            # if occurrenceFace[0].face.assemblyContext:
            #     comp = occurrenceFace[0].face.assemblyContext.component
            #     occ = occurrenceFace[0].face.assemblyContext
            #     self.logger.debug(f'processing component  = {comp.name}')
            #     self.logger.debug(f'processing occurrence  = {occ.name}')
            #     #entityName = occ.name.split(':')[-1]
            # else:
            #    comp = _rootComp
            #    occ = None
            #    self.logger.debug('processing Rootcomponent')
            comp:adsk.fusion.Component = occurrenceFace[0].component
            occ:adsk.fusion.Occurrence = occurrenceFace[0].occurrence

            if self.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(occurrenceFace[0].native)
                self.logger.info(f'Processing holes from top face - {topFace.body.name}')

            for selectedFace in occurrenceFace:
                if len(selectedFace.selectedEdges.values()) <1:
                    self.logger.debug('Face has no edges')
                    
                face = selectedFace.native
                
                if not face.isValid:
                    self.logger.debug('revalidating Face')
                    face.revalidate
                self.logger.debug(f'Processing Face = {face.tempId}')
              
                #faceNormal = dbUtils.getFaceNormal(face.nativeObject)
                if self.fromTop:
                    self.logger.debug(f'topFace type {type(topFace)}')
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace.revalidate # = reValidateFace(comp, topFaceRefPoint)

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
                        face.revalidate # = reValidateFace(comp, selectedFace.refPoint)

                    if not selectedEdge.edge.isValid:
                        continue # edges that have been processed already will not be valid any more - at the moment this is easier than removing the 
    #                    affected edge from self.edges after having been processed
                    edge = makeNative(selectedEdge.edge)
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
 
                    if self.dbType == 'Mortise Dogbone':
                        direction0 = dbUtils.correctedEdgeVector(edge1,startVertex) 
                        direction1 = dbUtils.correctedEdgeVector(edge2,startVertex)
                        
                        if self.longside:
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

                    if self.fromTop:
                        centrePoint.translateBy(transformVector)
                        self.logger.debug(f'centrePoint at topFace = {centrePoint.asArray()}')
                        holePlane = topFace if self.fromTop else face
                        if not holePlane.isValid:
                            holePlane.revalidate # = reValidateFace(comp, topFaceRefPoint)
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
#            self.logger.debug('doEvents - allowing display to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox(f'Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created')

    def createStaticDogbones(self):
        self.logger.info('Creating static dogbones')
        self.errorCount = 0
        if not _design:
            raise RuntimeError('No active Fusion design')
        holeInput:adsk.fusion.HoleFeatureInput = None
        centreDistance = self.radius*(1+self.minimalPercent/100 if self.dbType == 'Minimal Dogbone' else  1)
        
        for occurrenceFace in self.selectedOccurrences.values():
            startTlMarker = _design.timeline.markerPosition
            
            # if occurrenceFace[0].face.assemblyContext:
            #     comp = occurrenceFace[0].face.assemblyContext.component
            #     occ = occurrenceFace[0].face.assemblyContext
            #     self.logger.info(f'processing component  = {comp.name}')
            #     self.logger.info(f'processing occurrence  = {occ.name}')
            #     #entityName = occ.name.split(':')[-1]
            # else:
            #    comp = _rootComp
            #    occ = None
            #    self.logger.info('processing Rootcomponent')
            comp:adsk.fusion.Component = occurrenceFace[0].component
            occ:adsk.fusion.Occurrence = occurrenceFace[0].occurrence   
            
            if self.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(occurrenceFace[0].native)
                self.logger.debug(f'topFace ref point: {topFaceRefPoint.asArray()}')
                self.logger.info(f'Processing holes from top face - {topFace.tempId}')
                self.debugFace(topFace)
                
                sketch:adsk.fusion.Sketch = comp.sketches.add(topFace)  #used for fault finding
                sketch.name = 'dogbone'
                sketch.isComputeDeferred = True
                self.logger.debug(f'Added topFace sketch - {sketch.name}')

            for selectedFace in occurrenceFace:
                if len(selectedFace.selectedEdges) <1:
                    self.logger.debug('Face has no edges')
                    continue 
                face = selectedFace.native

                if not face.isValid:
                    self.logger.debug('Revalidating face')
                    face = reValidateFace(comp, selectedFace.refPoint)
                    self.logger.info(f'Processing Face = {face.tempId}')
                    self.debugFace(face)

                self.logger.info(f'processing face - {face.tempId}')
                self.debugFace(face)
                holeList = []                

                comp:adsk.fusion.Component = comp
                

                if self.fromTop:
                    self.logger.debug(f'topFace type {type(topFace)}')
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace = reValidateFace(comp, topFaceRefPoint)
                       topFaceRefPoint = topFace.pointOnFace
                       self.debugFace(topFace)
                    self.logger.debug(f'topFace isValid = {topFace.isValid}')
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(face, topFace)
                    self.logger.debug(f'creating transformVector to topFace = {transformVector.asArray()} length = {transformVector.length}')
                else:    
                    sketch:adsk.fusion.Sketch = comp.sketches.add(face)
                    sketch.name = 'dogbone'
                    sketch.isComputeDeferred = True
                    self.logger.debug(f'creating face plane sketch - {sketch.name}')
                
                for selectedEdge in selectedFace.selectedEdges:
                    
                    self.logger.debug(f'Processing edge - {selectedEdge.edge.tempId}')

                    if not selectedEdge.isSelected:
                        self.logger.debug('  Not selected. Skipping...')
                        continue

                    if not face.isValid:
                        self.logger.debug('Revalidating face')
                        face = reValidateFace(comp, selectedFace.refPoint)
                        
                    if not selectedEdge.edge.isValid:
                        continue # edges that have been processed already will not be valid any more - at the moment this is easier than removing the 
    #                    affected edge from self.edges after having been processed
                    try:
                        if not dbUtils.isEdgeAssociatedWithFace(face, makeNative(selectedEdge.edge)):
                            continue  # skip if edge is not associated with the face currently being processed
                    except:
                        pass

                    edge = selectedEdge.native                    
                    startVertex:adsk.fusion.BRepVertex = dbUtils.getVertexAtFace(face, edge)
                    centrePoint = startVertex.geometry.copy()
                        
                    selectedEdgeFaces = edge.faces
                    
                    if self.dbType == 'Mortise Dogbone':
                        (edge0, edge1) = dbUtils.getCornerEdgesAtFace(face, edge)
                        direction0 = dbUtils.correctedEdgeVector(edge0,startVertex) 
                        direction1 = dbUtils.correctedEdgeVector(edge1,startVertex) 
                        if self.longside:
                            if (edge0.length > edge1.length):
                                dirVect = direction0
                            else:
                                dirVect = direction1
                        else:
                            if (edge0.length > edge1.length):
                                dirVect = direction1
                            else:
                                dirVect = direction0
                    else:
                        dirVect:adsk.core.Vector3D = dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[0])).copy()
                        dirVect.add(dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[1])))
                    dirVect.normalize()
                    dirVect.scaleBy(centreDistance)  #ideally radius should be linked to parameters, 
                                                          # but hole start point still is the right quadrant
                    centrePoint.translateBy(dirVect)
                    if self.fromTop:
                        centrePoint.translateBy(transformVector)

                    centrePoint = sketch.modelToSketchSpace(centrePoint)
                    
                    sketchPoint = sketch.sketchPoints.add(centrePoint)  #as the centre is placed on midline endPoint, it automatically gets constrained
                    length = (selectedEdge.edge.length + transformVector.length) if self.fromTop else makeNative(selectedEdge.edge).length
                    holeList.append([length, sketchPoint])
                    self.logger.info(f'hole added to list - length {length}, {sketchPoint.geometry.asArray()}')
                    
                depthList = set(map(lambda x: x[0], holeList))  #create a unique set of depths - using this in the filter will automatically group depths

                for depth in depthList:
                    self.logger.debug(f'processing holes at depth {depth}')
                    pointCollection = adsk.core.ObjectCollection.create()  #needed for the setPositionBySketchpoints
                    holeCount = 0
                    for hole in filter(lambda h: h[0] == depth, holeList):
                        pointCollection.add(hole[1])
                        holeCount+=1
                    
                    if not face.isValid:
                        self.logger.debug('Revalidating face')
                        face = reValidateFace(comp, selectedFace.refPoint)

                    holes =  comp.features.holeFeatures
                    holeInput = holes.createSimpleInput(adsk.core.ValueInput.createByReal(self.radius*2))
                    holeInput.isDefaultDirection = True
                    holeInput.tipAngle = adsk.core.ValueInput.createByString('180 deg')
                    holeInput.participantBodies = [face.body]
                    holeInput.setPositionBySketchPoints(pointCollection)
                    holeInput.setDistanceExtent(adsk.core.ValueInput.createByReal(depth))

                    holes.add(holeInput)
                    self.logger.info(f'{holeCount} Holes added')
            sketch.isComputeDeferred = False
                    
            endTlMarker = _design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = _design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'dogbone'
#            self.logger.debug('doEvents - allowing fusion to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox(f'Reported errors:{self.errorCount}\nYou may not need to do anything, \nbut check holes have been created')


dog = DogboneCommand()


def run(context):
    try:
        dog.addButton()
    except:
        dbUtils.messageBox(traceback.format_exc())


def stop(context):
    try:
        dog.removeButton()
    except:
        dbUtils.messageBox(traceback.format_exc())

