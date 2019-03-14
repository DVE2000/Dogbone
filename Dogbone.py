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
from math import sqrt as sqrt

#constants - to keep attribute group and names consistent
DOGBONEGROUP = 'dogBoneGroup'
FACE_ID = 'faceID'
REV_ID = 'revId'
ID = 'id'
DEBUGLEVEL = logging.NOTSET

dbModes = ['Normal Dogbone','Minimal Dogbone','Mortise Dogbone']

# Generate an edgeId or faceId from object
calcId = lambda x: str(x.tempId) + ':' + x.assemblyContext.name.split(':')[-1] if x.assemblyContext else str(x.tempId) + ':' + x.body.name
makeNative = lambda x: x.nativeObject if x.nativeObject else x
reValidateFace = lambda comp, x: comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)

class SelectedEdge:
    def __init__(self, edge, edgeId, activeEdgeName, tempId, selectedFace):
        self.edge = edge
        self.edgeId = edgeId
        self.activeEdgeName = activeEdgeName
        self.tempId = tempId
        self.selected = True
        self.selectedFace = selectedFace

    def select(self, selection = True):
        self.selected = selection


class SelectedFace:
    def __init__(self, dog, face, faceId, tempId, occurrenceName, refPoint, commandInputsEdgeSelect):
        self.dog = dog
        self.face = face # BrepFace
        self.faceId = faceId
        self.tempId = tempId
        self.occurrenceName = occurrenceName
        self.refPoint = refPoint
        self.commandInputsEdgeSelect = commandInputsEdgeSelect
        self.selected = True
        self.selectedEdges = {} # Keyed with edge
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

                    activeEdgeName = edge.assemblyContext.name.split(':')[-1] if edge.assemblyContext else edge.body.name
                    edgeId = str(edge.tempId)+':'+ activeEdgeName
                    self.selectedEdges[edgeId] = SelectedEdge(edge, edgeId, activeEdgeName, edge.tempId, self)
                    self.brepEdges.append(edge)
                    dog.addingEdges = True
                    self.commandInputsEdgeSelect.addSelection(edge)
                    dog.addingEdges = False
                    
                    dog.selectedEdges[edgeId] = self.selectedEdges[edgeId] # can be used for reverse lookup of edge to face
                except:
                    dbUtils.messageBox('Failed at edge:\n{}'.format(traceback.format_exc()))

    def selectAll(self, selection = True):
        self.selected = selection
        dog.addingEdges = True
        for edgeId, selectedEdge in self.selectedEdges.items():
            selectedEdge.select(selection)
            if selection:
                #commandInputsEdgeSelect.addSelection(edge.edge) # Not working for re-adding.
                dog.ui.activeSelections.add(selectedEdge.edge)
 
            else:
                dog.ui.activeSelections.removeByEntity(selectedEdge.edge)
        dog.addingEdges = False


class DogboneCommand(object):
    COMMAND_ID = "dogboneBtn"
    
    faceAssociations = {}
    defaultData = {}
    logger = logging.getLogger(__name__)


    def __init__(self):
        self.app = adsk.core.Application.get()
        self.ui = self.app.userInterface

        self.setDefaults()
        self.edges = []
        self.errorCount = 0
        self.faceSelections = adsk.core.ObjectCollection.create()

        self.addingEdges = 0
        self.loggingLevels = {'Notset':0,'Debug':10,'Info':20,'Warning':30,'Error':40}
        self.levels = {}

        self.handlers = dbUtils.HandlerHelper()

        self.appPath = os.path.dirname(os.path.abspath(__file__))
        
    def setDefaults(self):

        self.offStr = "0"
        self.offVal = None
        self.circStr = "0.25 in"
        self.circVal = None
        self.benchmark = False
        self.dbType = 'Normal Dogbone'
        self.longside = True
        self.minimalPercent = 10.0
        self.fromTop = False
        self.parametric = False
        self.logging = 0

        self.expandModeGroup = True
        self.expandSettingsGroup = False
        
        

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
    
    def readDefaults(self):
        self.logger.info('read config file')
        '''
        Reads default variable values back into dogbone
        '''        
     
        variables = {'offStr': adsk.core.ValueInput,\
        'offVal': float,\
        'circStr': adsk.core.ValueInput,\
        'circVal': float,\
        'benchmark': bool,\
        'dbType': str,\
        'minimalPercent': float,\
        'fromTop': bool,\
        'parametric': bool,\
        'logging': int,\
        'mortiseType': bool,\
        'expandModeGroup': bool,\
        'expandSettingsGroup': bool}
        
        if not os.path.isfile(os.path.join(self.appPath, 'defaults.dat')):
            return
        json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'r', encoding='UTF-8')
        try:
            self.defaultData = json.load(json_file)
            check = [var for var in self.defaultData.keys() if var not in variables.keys()] #weeds out keys that are not in the variables list
            if len(check) > 0:
                for key in check:
                    del self.defaultData[key] #delete the renegade keys
            if len(self.defaultData)!= len(variables):
                raise ValueError
            for var in self.defaultData.keys():
                if variables[var] == adsk.core.ValueInput:
                    self.design.unitsManager.evaluateExpression(self.defaultData[var])  # this will throw a RuntimeError 6 if the expression is not valid
                else:
                    if type(self.defaultData[var])!= variables[var]: #check that the variable type is correct
                        raise ValueError
                    if self.defaultData['dbType'] not in dbModes:
                        raise ValueError
                        
        except (ValueError, RuntimeError) as e:
            if type(e) == RuntimeError and e.args[0].split(":")[0].strip() != '6':
                raise
            self.logger.error('default.dat error')
            json_file.close()
            self.ui.messageBox('Oops!\nSomething went wrong with the saved configuration\nresetting defaults', 'Note', adsk.core.MessageBoxButtonTypes.OKButtonType, adsk.core.MessageBoxIconTypes.InformationIconType)
            self.setDefaults()
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
            self.logger.debug('edge {}; startVertex: {}; endVertex: {}'.format(edge.tempId, edge.startVertex.geometry.asArray(), edge.endVertex.geometry.asArray()))

        return

    def addButton(self):
        # clean up any crashed instances of the button if existing
        try:
            self.removeButton()
        except:
            pass

        # add add-in to UI
        buttonDogbone = self.ui.commandDefinitions.addButtonDefinition(
            self.COMMAND_ID, 'Dogbone', 'Creates dogbones at all inside corners of a face', 'Resources')

        buttonDogbone.commandCreated.add(self.handlers.make_handler(adsk.core.CommandCreatedEventHandler,
                                                                    self.onCreate))

        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        buttonControl = createPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

    def removeButton(self):
        cmdDef = self.ui.commandDefinitions.itemById(self.COMMAND_ID)
        if cmdDef:
            cmdDef.deleteMe()
        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        cntrl = createPanel.controls.itemById(self.COMMAND_ID)
        if cntrl:
            cntrl.deleteMe()

    def onCreate(self, args:adsk.core.CommandCreatedEventArgs):
        """
        important persistent variables:        
        self.selectedOccurrences  - Lookup dictionary 
        key: activeOccurrenceName 
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
        inputs = adsk.core.CommandCreatedEventArgs.cast(args)
        self.faces = []
        self.errorCount = 0
        self.faceSelections.clear()
        
        self.selectedOccurrences = {} 
        self.selectedFaces = {} 
        self.selectedEdges = {} 
        
        argsCmd = adsk.core.Command.cast(args)
        
        if self.design.designType != adsk.fusion.DesignTypes.ParametricDesignType :
            returnValue = self.ui.messageBox('DogBone only works in Parametric Mode \n Do you want to change modes?', 'Change to Parametric mode', adsk.core.MessageBoxButtonTypes.YesNoButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            self.design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        self.readDefaults()

        inputs = adsk.core.CommandInputs.cast(inputs.command.commandInputs)
        
        selInput0 = inputs.addSelectionInput(
            'select', 'Face',
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
            'circDiameter', 'Tool Diameter               ', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.circStr))
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."
        
        offsetInp = inputs.addValueInput(
            'offset', 'Tool diameter offset', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.offStr))
        offsetInp.tooltip = "Increases the tool diameter"
        offsetInp.tooltipDescription = "Use this to create an oversized dogbone.\n"\
                                        "Normally set to 0.  \n"\
                                        "A value of .010 would increase the dogbone diameter by .010 \n"\
                                        "Used when you want to keep the tool diameter and oversize value separate"
        
        modeGroup = adsk.core.GroupCommandInput.cast(inputs.addGroupCommandInput('modeGroup', 'Mode'))
        modeGroup.isExpanded = self.expandModeGroup
        modeGroupChildInputs = modeGroup.children
        
        modeRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('modeRow', 'Mode', False))
        modeRowInput.listItems.add('Static', not self.parametric, 'resources/staticMode' )
        modeRowInput.listItems.add('Parametric', self.parametric, 'resources/parametricMode' )
        modeRowInput.tooltipDescription = "Static dogbones do not move with the underlying component geometry. \n" \
                                "\nParametric dogbones will automatically adjust position with parametric changes to underlying geometry. " \
                                "Geometry changes must be made via the parametric dialog.\nFusion has more issues/bugs with these!"
        
        typeRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('dogboneType', 'Type', False))
        typeRowInput.listItems.add('Normal Dogbone', self.dbType == 'Normal Dogbone', 'resources/normal' )
        typeRowInput.listItems.add('Minimal Dogbone', self.dbType == 'Minimal Dogbone', 'resources/minimal' )
        typeRowInput.listItems.add('Mortise Dogbone', self.dbType == 'Mortise Dogbone', 'resources/hidden' )
        typeRowInput.tooltipDescription = "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit " \
                                            "that, for example, will require a larger force to insert a tenon into a mortise.\n" \
                                            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n" \
                                            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        
        mortiseRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('mortiseType', 'Mortise Type', False))
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

        depthRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('depthExtent', 'Depth Extent', False))
        depthRowInput.listItems.add('From Selected Face', not self.fromTop, 'resources/fromFace' )
        depthRowInput.listItems.add('From Top Face', self.fromTop, 'resources/fromTop' )
        depthRowInput.tooltipDescription = "When \"From Top Face\" is selected, all dogbones will be extended to the top most face\n"\
                                            "\nThis is typically chosen when you don't want to, or can't do, double sided machining."
 
        settingGroup = adsk.core.GroupCommandInput.cast(inputs.addGroupCommandInput('settingsGroup', 'Settings'))
        settingGroup.isExpanded = self.expandSettingsGroup
        settingGroupChildInputs = settingGroup.children

        benchMark = settingGroupChildInputs.addBoolValueInput("benchmark", "Benchmark time", True, "", self.benchmark)
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = "When enabled, shows overall time taken to process all selected dogbones."

        logDropDownInp = adsk.core.DropDownCommandInput.cast(settingGroupChildInputs.addDropDownCommandInput("logging", "Logging level", adsk.core.DropDownStyles.TextListDropDownStyle))
        logDropDownInp.tooltip = "Enables logging"
        logDropDownInp.tooltipDescription = "Creates a dogbone.log file. \n" \
                     "Location: " +  os.path.join(self.appPath, 'dogBone.log')

        logDropDownInp.listItems.add('Notset', self.logging == 0)
        logDropDownInp.listItems.add('Debug', self.logging == 10)
        logDropDownInp.listItems.add('Info', self.logging == 20)

        cmd = adsk.core.Command.cast(args.command)
        # Add handlers to this command.
        cmd.execute.add(self.handlers.make_handler(adsk.core.CommandEventHandler, self.onExecute))
        cmd.selectionEvent.add(self.handlers.make_handler(adsk.core.SelectionEventHandler, self.onFaceSelect))
        cmd.validateInputs.add(
            self.handlers.make_handler(adsk.core.ValidateInputsEventHandler, self.onValidate))
        cmd.inputChanged.add(
            self.handlers.make_handler(adsk.core.InputChangedEventHandler, self.onChange))

    #==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    #==============================================================================
    def onChange(self, args:adsk.core.InputChangedEventArgs):
        
        changedInput = adsk.core.CommandInput.cast(args.input)
#        self.logger.debug('input changed- {}'.format(changedInput.id))

        if changedInput.id == 'dogboneType':
            changedInput.commandInputs.itemById('minimalPercent').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Minimal Dogbone')
            changedInput.commandInputs.itemById('mortiseType').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Mortise Dogbone')
       

        if changedInput.id != 'select' and changedInput.id != 'edgeSelect':
            return

#        self.logger.debug('input changed- {}'.format(changedInput.id))
        if changedInput.id == 'select':

            #==============================================================================
            #            processing changes to face selections
            #==============================================================================
            numSelectedFaces = sum(1 for face in self.selectedFaces.values() if face.selected) 
            if numSelectedFaces > changedInput.selectionCount:               
                # a face has been removed
                
                # If all faces are removed, just iterate through all
                if changedInput.selectionCount == 0:                
                    for face in self.selectedFaces.values():
                        if face.selected:
                            face.selectAll(False)
                    changedInput.commandInputs.itemById('edgeSelect').clearSelection()
                    changedInput.commandInputs.itemById('select').hasFocus = True                    
                    changedInput.commandInputs.itemById('edgeSelect').isVisible = False   
                    return
                
                # Else find the missing face in selection
                selectionList = [changedInput.selection(i).entity.tempId for i in range(changedInput.selectionCount)]
                missingFace = {k for k, v in self.selectedFaces.items() if v.selected and v.tempId not in selectionList}.pop()
                changedInput.commandInputs.itemById('edgeSelect').hasFocus = True
                self.selectedFaces[missingFace].selectAll(False)
            
                changedInput.commandInputs.itemById('select').hasFocus = True
                return
             
            #==============================================================================
            #             Face has been added - assume that the last selection entity is the one added
            #==============================================================================
            face = adsk.fusion.BRepFace.cast(changedInput.selection(changedInput.selectionCount -1).entity)
            changedInput.commandInputs.itemById('edgeSelect').isVisible = True  
            
            changedEntity = face #changedInput.selection(changedInput.selectionCount-1).entity
            if changedEntity.assemblyContext:
                activeOccurrenceName = changedEntity.assemblyContext.name
            else:
                activeOccurrenceName = changedEntity.body.name
                
            if changedInput.selection(changedInput.selectionCount-1).entity.assemblyContext:
                changedEntityName = changedInput.selection(changedInput.selectionCount-1).entity.assemblyContext.name.split(':')[-1]
            else:
                changedEntityName = changedEntity.body.name
            
            faceId = str(changedEntity.tempId) + ":" + changedEntityName 
            if faceId in self.selectedFaces :
                changedInput.commandInputs.itemById('edgeSelect').hasFocus = True
                self.selectedFaces[faceId].selectAll(True) 
                changedInput.commandInputs.itemById('select').hasFocus = True
                return
            newSelectedFace = SelectedFace(
                                            self, 
                                            face,
                                            faceId,
                                            changedEntity.tempId,
                                            changedEntityName,
                                            face.nativeObject.pointOnFace if face.assemblyContext else face.pointOnFace,
                                            changedInput.commandInputs.itemById('edgeSelect')
                                          )  # creates a collecton (of edges) associated with a faceId
            faces = []
            faces = self.selectedOccurrences.get(activeOccurrenceName, faces)
            faces.append(newSelectedFace)
            self.selectedOccurrences[activeOccurrenceName] = faces # adds a face to a list of faces associated with this occurrence
            self.selectedFaces[faceId] = newSelectedFace


                 #end of processing faces
        #==============================================================================
        #         Processing changed edge selection            
        #==============================================================================
        if changedInput.id != 'edgeSelect':
            return

        if sum(1 for edge in self.selectedEdges.values() if edge.selected) > changedInput.selectionCount:
            #==============================================================================
            #             an edge has been removed
            #==============================================================================
            
            changedSelectionList = [changedInput.selection(i).entity for i in range(changedInput.selectionCount)]
            changedEdgeIdSet = set(map(calcId, changedSelectionList))  # converts list of edges to a list of their edgeIds
            missingEdges = (set(self.selectedEdges.keys()) - changedEdgeIdSet)
            for missingEdge in missingEdges:
                self.selectedEdges[missingEdge].select(False)
            # Note - let the user manually unselect the face if they want to choose a different face

            return
            # End of processing removed edge 
        else:
            #==============================================================================
            #         Start of adding a selected edge
            #         Edge has been added - assume that the last selection entity is the one added
            #==============================================================================
            edge = adsk.fusion.BRepEdge.cast(changedInput.selection(changedInput.selectionCount - 1).entity)
            self.selectedEdges[calcId(edge)].select() # Get selectedFace then get selectedEdge, then call function


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

        self.logger.debug('self.fromTop = {}'.format(self.fromTop))
        self.logger.debug('self.dbType = {}'.format(self.dbType))
        self.logger.debug('self.parametric = {}'.format(self.parametric))
        self.logger.debug('self.circStr = {}'.format(self.circStr))
        self.logger.debug('self.circDiameter = {}'.format(self.circVal))
        self.logger.debug('self.offStr = {}'.format(self.offStr))
        self.logger.debug('self.offVal = {}'.format(self.offVal))
        self.logger.debug('self.benchmark = {}'.format(self.benchmark))
        self.logger.debug('self.mortiseType = {}'.format(self.longside))
        self.logger.debug('self.expandModeGroup = {}'.format(self.expandModeGroup))
        self.logger.debug('self.expandSettingsGroup = {}'.format(self.expandSettingsGroup))
        
        self.edges = []
        self.faces = []
        
        for i in range(inputs['edgeSelect'].selectionCount):
            entity = inputs['edgeSelect'].selection(i).entity
            if entity.objectType == adsk.fusion.BRepEdge.classType():
                self.edges.append(entity)
        for i in range(inputs['select'].selectionCount):
            entity = inputs['select'].selection(i).entity
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

    def onExecute(self, args):
        start = time.time()

        self.initLogger()
        self.logger.log(0, 'logging Level = %(levelname)')
        self.parseInputs(args.firingEvent.sender.commandInputs)
        self.logHandler.setLevel(self.logging)
        self.logger.setLevel(self.logging)

        self.writeDefaults()

        if self.parametric:
            userParams = adsk.fusion.UserParameters.cast(self.design.userParameters)
            
            #set up parameters, so that changes can be easily made after dogbones have been inserted
            if not userParams.itemByName('dbToolDia'):
                dValIn = adsk.core.ValueInput.createByString(self.circStr)
                dParameter = userParams.add('dbToolDia', dValIn, self.design.unitsManager.defaultLengthUnits, '')
                dParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbToolDia')
                uParam.expression = self.circStr
                uParam.isFavorite = True
                
            if not userParams.itemByName('dbOffset'):
                rValIn = adsk.core.ValueInput.createByString(self.offStr)
                rParameter = userParams.add('dbOffset',rValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbOffset')
                uParam.expression = self.offStr
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbRadius'):
                rValIn = adsk.core.ValueInput.createByString('(dbToolDia + dbOffset)/2')
                rParameter = userParams.add('dbRadius',rValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
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
                oParameter = userParams.add('dbHoleOffset', oValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
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
            dbUtils.messageBox("Benchmark: {:.02f} sec processing {} edges".format(
                time.time() - start, len(self.edges)))


    ################################################################################        
    def onValidate(self, args):
        cmd = adsk.core.ValidateInputsEventArgs.cast(args)
        cmd = args.firingEvent.sender

        for input in cmd.commandInputs:
            if input.id == 'select':
                if input.selectionCount < 1:
                    args.areInputsValid = False
            elif input.id == 'circDiameter':
                if input.value <= 0:
                    args.areInputsValid = False
                    
    def onFaceSelect(self, args):
        '''==============================================================================
            Routine gets called with every mouse movement, if a commandInput select is active                   
           ==============================================================================
       '''
        eventArgs = adsk.core.SelectionEventArgs.cast(args)
        # Check which selection input the event is firing for.
        activeIn = eventArgs.firingEvent.activeInput
        if activeIn.id != 'select' and activeIn.id != 'edgeSelect':
            return # jump out if not dealing with either of the two selection boxes

        if activeIn.id == 'select':
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

                activeBodyName = eventArgs.selection.entity.body.name
                try:            
                    faces = self.selectedOccurrences[activeBodyName]
                    for face in faces:
                        if face.selected:
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
            activeOccurrenceName = activeOccurrence.name
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

            if activeOccurrenceName not in self.selectedOccurrences:  #check if mouse is over a face that is not already selected
                eventArgs.isSelectable = False
                return
                
            try:            
                faces = self.selectedOccurrences[activeOccurrenceName]
                for face in faces:
                    if face.selected:
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
            currentEdge = adsk.fusion.BRepEdge.cast(selected.entity)
            activeOccurrence = eventArgs.selection.entity.assemblyContext
            if eventArgs.selection.entity.assemblyContext:
                activeOccurrenceName = activeOccurrence.name
            else:
                activeOccurrenceName = eventArgs.selection.entity.body.name 

            occurrenceNumber = activeOccurrenceName.split(':')[-1]
            edgeId = str(currentEdge.tempId) + ':' + occurrenceNumber
            if (edgeId in self.selectedEdges and self.selectedEdges[edgeId].selectedFace.selected):
                eventArgs.isSelectable = True
            else:
                eventArgs.isSelectable = False
            return


    @property
    def design(self):
        return self.app.activeProduct

    @property
    def rootComp(self):
        return self.design.rootComponent

    @property
    def originPlane(self):
        return self.rootComp.xZConstructionPlane if self.yUp else self.rootComp.xYConstructionPlane

    # The main algorithm for parametric dogbones
    def createParametricDogbones(self):
        self.logger.info('Creating parametric dogbones')
        self.errorCount = 0
        if not self.design:
            raise RuntimeError('No active Fusion design')
        holeInput = adsk.fusion.HoleFeatureInput.cast(None)
        offsetByStr = adsk.core.ValueInput.createByString('dbHoleOffset')
        centreDistance = self.radius*(1+self.minimalPercent/100 if self.dbType=='Minimal Dogbone' else  1)
        
        for occurrenceFace in self.selectedOccurrences.values():
            startTlMarker = self.design.timeline.markerPosition

            if occurrenceFace[0].face.assemblyContext:
                comp = occurrenceFace[0].face.assemblyContext.component
                occ = occurrenceFace[0].face.assemblyContext
                self.logger.debug('processing component  = {}'.format(comp.name))
                self.logger.debug('processing occurrence  = {}'.format(occ.name))
                #entityName = occ.name.split(':')[-1]
            else:
               comp = self.rootComp
               occ = None
               self.logger.debug('processing Rootcomponent')

            if self.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(makeNative(occurrenceFace[0].face))
                self.logger.info('Processing holes from top face - {}'.format(topFace.body.name))

            for selectedFace in occurrenceFace:
                if len(selectedFace.selectedEdges.values()) <1:
                    self.logger.debug('Face has no edges')
                face = makeNative(selectedFace.face)
                
                comp = adsk.fusion.Component.cast(comp)
                
                if not face.isValid:
                    self.logger.debug('revalidating Face')
                    face = reValidateFace(comp, selectedFace.refPoint)
                self.logger.debug('Processing Face = {}'.format(face.tempId))
              
                #faceNormal = dbUtils.getFaceNormal(face.nativeObject)
                if self.fromTop:
                    self.logger.debug('topFace type {}'.format(type(topFace)))
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace = reValidateFace(comp, topFaceRefPoint)

                    topFace = makeNative(topFace)
                       
                    self.logger.debug('topFace isValid = {}'.format(topFace.isValid))
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(face, topFace)
                    self.logger.debug('creating transformVector to topFace = ({},{},{}) length = {}'.format(transformVector.x, transformVector.y, transformVector.z, transformVector.length))
                                
                for selectedEdge in selectedFace.selectedEdges.values():
                    
                    self.logger.debug('Processing edge - {}'.format(selectedEdge.edge.tempId))

                    if not selectedEdge.selected:
                        self.logger.debug('  Not selected. Skipping...')
                        continue

                    if not face.isValid:
                        self.logger.debug('Revalidating face')
                        face = reValidateFace(comp, selectedFace.refPoint)

                    if not selectedEdge.edge.isValid:
                        continue # edges that have been processed already will not be valid any more - at the moment this is easier than removing the 
    #                    affected edge from self.edges after having been processed
                    edge = makeNative(selectedEdge.edge)
                    try:
                        if not dbUtils.isEdgeAssociatedWithFace(face, edge):
                            continue  # skip if edge is not associated with the face currently being processed
                    except:
                        pass
                    
                    startVertex = adsk.fusion.BRepVertex.cast(dbUtils.getVertexAtFace(face, edge))
                    extentToEntity = dbUtils.findExtent(face, edge)

                    extentToEntity = makeNative(extentToEntity)
                    self.logger.debug('extentToEntity - {}'.format(extentToEntity.isValid))
                    if not extentToEntity.isValid:
                        self.logger.debug('To face invalid')

                    try:
                        (edge1, edge2) = dbUtils.getCornerEdgesAtFace(face, edge)
                    except:
                        self.logger.exception('Failed at findAdjecentFaceEdges')
                        dbUtils.messageBox('Failed at findAdjecentFaceEdges:\n{}'.format(traceback.format_exc()))
                    
                    centrePoint = makeNative(startVertex).geometry.copy()
                        
                    selectedEdgeFaces = makeNative(selectedEdge.edge).faces
                    
                    dirVect = adsk.core.Vector3D.cast(dbUtils.getFaceNormal(selectedEdgeFaces[0]).copy())
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
                        dirVect = adsk.core.Vector3D.cast(dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[0])).copy())
                        dirVect.add(dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[1])))
                        edge1OffsetByStr = offsetByStr
                        edge2OffsetByStr = offsetByStr

                    centrePoint.translateBy(dirVect)
                    self.logger.debug('centrePoint = ({},{},{})'.format(centrePoint.x, centrePoint.y, centrePoint.z))

                    if self.fromTop:
                        centrePoint.translateBy(transformVector)
                        self.logger.debug('centrePoint at topFace = {}'.format(centrePoint.asArray()))
                        holePlane = topFace if self.fromTop else face
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
                    
                    self.logger.debug('extentToEntity before setPositionByPlaneAndOffsets - {}'.format(extentToEntity.isValid))
                    holeInput.setPositionByPlaneAndOffsets(holePlane, centrePoint, edge1, edge1OffsetByStr, edge2, edge2OffsetByStr)
                    self.logger.debug('extentToEntity after setPositionByPlaneAndOffsets - {}'.format(extentToEntity.isValid))
                    holeInput.setOneSideToExtent(extentToEntity, False)
                    self.logger.info('hole added to list - {}'.format(centrePoint.asArray()))
 
                    holeFeature = holes.add(holeInput)
                    holeFeature.name = 'dogbone'
                    holeFeature.isSuppressed = True
                    
                for hole in holes:
                    if hole.name[:7] != 'dogbone':
                        break
                    hole.isSuppressed = False
                    
            endTlMarker = self.design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = self.design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'dogbone'
#            self.logger.debug('doEvents - allowing display to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox('Reported errors:{}\nYou may not need to do anything, \nbut check holes have been created'.format(self.errorCount))

    def createStaticDogbones(self):
        self.logger.info('Creating static dogbones')
        self.errorCount = 0
        if not self.design:
            raise RuntimeError('No active Fusion design')
        holeInput = adsk.fusion.HoleFeatureInput.cast(None)
        centreDistance = self.radius*(1+self.minimalPercent/100 if self.dbType == 'Minimal Dogbone' else  1)
        
        for occurrenceFace in self.selectedOccurrences.values():
            startTlMarker = self.design.timeline.markerPosition
            
            if occurrenceFace[0].face.assemblyContext:
                comp = occurrenceFace[0].face.assemblyContext.component
                occ = occurrenceFace[0].face.assemblyContext
                self.logger.info('processing component  = {}'.format(comp.name))
                self.logger.info('processing occurrence  = {}'.format(occ.name))
                #entityName = occ.name.split(':')[-1]
            else:
               comp = self.rootComp
               occ = None
               self.logger.info('processing Rootcomponent')
               
            
            if self.fromTop:
                (topFace, topFaceRefPoint) = dbUtils.getTopFace(makeNative(occurrenceFace[0].face))
                self.logger.debug('topFace ref point: {}'.format(topFaceRefPoint.asArray()))
                self.logger.info('Processing holes from top face - {}'.format(topFace.tempId))
                self.debugFace(topFace)
                
                    
                sketch = adsk.fusion.Sketch.cast(comp.sketches.add(topFace))  #used for fault finding
                sketch.name = 'dogbone'
                sketch.isComputeDeferred = True
                self.logger.debug('Added topFace sketch - {}'.format(sketch.name))

            for selectedFace in occurrenceFace:
                if len(selectedFace.selectedEdges.values()) <1:
                    self.logger.debug('Face has no edges')
                    continue 
                face = makeNative(selectedFace.face)

                if not face.isValid:
                    self.logger.debug('Revalidating face')
                    face = reValidateFace(comp, selectedFace.refPoint)
                    self.logger.info('Processing Face = {}'.format(face.tempId))
                    self.debugFace(face)

                self.logger.info('processing face - {}'.format(face.tempId))
                self.debugFace(face)
                holeList = []                

                comp = adsk.fusion.Component.cast(comp)
                

                if self.fromTop:
                    self.logger.debug('topFace type {}'.format(type(topFace)))
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace = reValidateFace(comp, topFaceRefPoint)
                       topFaceRefPoint = topFace.pointOnFace
                       self.debugFace(topFace)
                    self.logger.debug('topFace isValid = {}'.format(topFace.isValid))
                    transformVector = dbUtils.getTranslateVectorBetweenFaces(face, topFace)
                    self.logger.debug('creating transformVector to topFace = {} length = {}'.format(transformVector.asArray(), transformVector.length))
                else:    
                    sketch = adsk.fusion.Sketch.cast(comp.sketches.add(face))
                    sketch.name = 'dogbone'
                    sketch.isComputeDeferred = True
                    self.logger.debug('creating face plane sketch - {}'.format(sketch.name))
                
                for selectedEdge in selectedFace.selectedEdges.values():
                    
                    self.logger.debug('Processing edge - {}'.format(selectedEdge.edge.tempId))

                    if not selectedEdge.selected:
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

                    edge = makeNative(selectedEdge.edge)                    
                    startVertex = adsk.fusion.BRepVertex.cast(dbUtils.getVertexAtFace(face, edge))
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
                        dirVect = adsk.core.Vector3D.cast(dbUtils.getFaceNormal(makeNative(selectedEdgeFaces[0])).copy())
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
                    self.logger.info('hole added to list - length {}, {}'.format(length, sketchPoint.geometry.asArray()))
                    
                depthList = set(map(lambda x: x[0], holeList))  #create a unique set of depths - using this in the filter will automatically group depths

                for depth in depthList:
                    self.logger.debug('processing holes at depth {}'.format(depth))
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
                    self.logger.info('{} Holes added'.format(holeCount))
            sketch.isComputeDeferred = False
                    
            endTlMarker = self.design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = self.design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'dogbone'
#            self.logger.debug('doEvents - allowing fusion to refresh')
#            adsk.doEvents()
            
        if self.errorCount >0:
            dbUtils.messageBox('Reported errors:{}\nYou may not need to do anything, \nbut check holes have been created'.format(self.errorCount))


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

