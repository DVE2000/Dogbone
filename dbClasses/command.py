import logging
import os, sys
import adsk.core, adsk.fusion

from collections import defaultdict

import traceback
import json

import time
from ..common import dbutils as util
from ..common.dbutils import calcHash
from ..common import decorators as d
from math import sqrt, pi
from ..dbClasses import dataclasses as dc, faceEdgeMgr, dbFaces, dbEdges
from ..dbClasses import register as r

debugging = True
r.FaceObject('123')
r.EdgeObject('456')
if debugging:
    import importlib
    importlib.reload(util)
    importlib.reload(dc)
    importlib.reload(faceEdgeMgr)
    importlib.reload(dbFaces)
    importlib.reload(dbEdges)
    importlib.reload(d)

# Generate an edgeId or faceId from object
#calcId = lambda x: str(x.tempId) + ':' + x.assemblyContext.name.split(':')[-1] if x.assemblyContext else str(x.tempId) + ':' + x.body.name
makeNative = lambda x: x.nativeObject if x.nativeObject else x
reValidateFace = lambda comp, x: comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,-1.0 ,False ).item(0)
faceSelections = lambda selectionObjects: list(filter(lambda face: face.objectType == adsk.fusion.BRepFace.classType(), selectionObjects))
edgeSelections = lambda selectionObjects: list(filter(lambda edge: edge.objectType == adsk.fusion.BRepEdge.classType(), selectionObjects))


class DogboneCommand(object):
    RADIOBUTTONLIST_ID = 'dbButtonList' 
    COMMAND_ID = "dogboneBtn"
    RESTORE_ID = "dogboneRestoreBtn"
    
    faceAssociations = {}
    defaultData = {}


    def __init__(self):
        
        self.logger = logging.getLogger('dogbone.command')

        self.app = adsk.core.Application.get()
        self.ui = self.app.userInterface

        self.dbParams = dc.DbParams()
        # self.dbParams2 = P2.DbParams()
        self.faceSelections = adsk.core.ObjectCollection.create()
        self.offsetStr = "0"
        self.toolDiaStr = str(self.dbParams.toolDia) + " in"
        self.edges = []
        self.benchmark = False
        self.errorCount = 0

        self.addingEdges = 0
        self.parametric = False
        self.loggingLevels = dc.LoginLevels() #Utility 
        self.logging = self.loggingLevels.Debug
        # {'Notset':0,'Debug':10,'Info':20,'Warning':30,'Error':40}

        self.expandModeGroup = True
        self.expandSettingsGroup = False
#        self.loggingLevelsLookUp = {self.loggingLevels[k]:k for k in self.loggingLevels}
        self.levels = {}

        # self.handlers = util.HandlerHelper()

        self.appPath = os.path.dirname(os.path.abspath(__file__))
        self.registeredEntities = adsk.core.ObjectCollection.create()
        
    def __del__(self):
        d.HandlerCollection.handlers = []  #clear event handers
        for handler in self.logger.handlers:
            handler.flush()
            handler.close()

    def writeDefaults(self):
        self.logger.info('config file write')

        # self.defaultData['toolDiaOffsetStr'] = self.toolDiaOffsetStr
        # self.defaultData['toolDiaOffset'] = self.dbParams.toolDiaOffset
        # self.defaultData['toolDiaStr'] = self.toolDiaStr
        # self.defaultData['toolDiaVal'] = self.dbParams.toolDia
        # self.defaultData['benchmark'] = self.benchmark
        # self.defaultData['dbType'] = self.dbParams.dbType
        # self.defaultData['minimalPercent'] = self.dbParams.minimalPercent
        # self.defaultData['fromTop'] = self.dbParams.fromTop
        # self.defaultData['parametric'] = self.parametric
        # self.defaultData['logging'] = self.logging
        # self.defaultData['mortiseType'] = self.dbParams.longSide
        # self.defaultData['expandModeGroup'] = self.expandModeGroup
        # self.defaultData['expandSettingsGroup'] = self.expandSettingsGroup
        
        json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'w', encoding='UTF-8')
        json.dump(self.dbParams.json(), json_file, ensure_ascii=False)
        json_file.close()
    
    def readDefaults(self): 
        self.logger.info('config file read')
        if not os.path.isfile(os.path.join(self.appPath, 'defaults.dat')):
            return
        json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'r', encoding='UTF-8')
        try:
            resultStr = json.load(json_file)
            self.dbParams= dc.DbParams(**resultStr)
        except ValueError:
            self.logger.error('default.dat error')
            json_file.close()
            json_file = open(os.path.join(self.appPath, 'defaults.dat'), 'w', encoding='UTF-8')
            json.dump(self.dbParams.dict(), json_file, ensure_ascii=False)
            return

        json_file.close()
        try:
            self.offsetStr = self.defaultData['offsetStr']
            self.toolDiaStr = self.defaultData['toolDiaStr']
            self.benchmark = self.defaultData['benchmark']

            self.dbParams.offset = self.defaultData['offset']
            self.dbParams.toolDia = self.defaultData['toolDia']
            self.dbParams.dbType = self.defaultData['dbType']
            self.dbParams.minimalPercent = self.defaultData['minimalPercent']
            self.dbParams.fromTop = self.defaultData['fromTop']
            self.dbParams.minAngleLimit = self.defaultData['minAngleLimit']
            self.dbParams.maxAngleLimit = self.defaultData['maxAngleLimit']

            self.parametric = self.defaultData['parametric']
            self.logging = self.defaultData['logging']
            self.dbParams.longside = self.defaultData['mortiseType']
            self.expandModeGroup = self.defaultData['expandModeGroup']
            self.expandSettingsGroup = self.defaultData['expandSettingsGroup']

        except KeyError: 
        
            self.logger.error('Key error on read config file')
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

    def addButtons(self):
        # clean up any crashed instances of the button if existing
        try:
            self.removeButtons()
        except:
            return -1
        
        buttonRestore = self.ui.commandDefinitions.addButtonDefinition(self.RESTORE_ID,
                                                                       'Refresh',
                                                                       'quick way to refresh dogbones',
                                                                       'Resources')

        # add add-in to UI
        buttonDogbone = self.ui.commandDefinitions.addButtonDefinition( self.COMMAND_ID,
                                                                       'Dogbone',
                                                                       'Creates dogbones at all inside corners of a face',
                                                                       'Resources')
        self.onCreate(event=buttonDogbone.commandCreated)
        self.onRestore(event=buttonRestore.commandCreated)

        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        separatorControl = createPanel.controls.addSeparator()
        dropDownControl = createPanel.controls.addDropDown('Dogbone',
                                                           'Resources',
                                                           'dbDropDown',
                                                           separatorControl.id )
        buttonControl = dropDownControl.controls.addCommand(buttonDogbone,
                                                            'dogboneBtn')
        restoreBtnControl = dropDownControl.controls.addCommand(buttonRestore,
                                                             'dogboneRestoreBtn')

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True
        

    def removeButtons(self):
#        cleans up buttons and command definitions left over from previous instantiations
        cmdDef = self.ui.commandDefinitions.itemById(self.COMMAND_ID)
        restoreDef = self.ui.commandDefinitions.itemById(self.RESTORE_ID)
        createPanel = self.ui.allToolbarPanels.itemById('SolidCreatePanel')
        dbDropDowncntrl = createPanel.controls.itemById('dbDropDown')
        if dbDropDowncntrl:
            dbButtoncntrl = dbDropDowncntrl.controls.itemById('dogboneBtn')
            if dbButtoncntrl:
                dbButtoncntrl.isPromoted = False
                dbButtoncntrl.deleteMe()
            dbRestoreBtncntrl = dbDropDowncntrl.controls.itemById('dogboneRestoreBtn')
            if dbRestoreBtncntrl:
                dbRestoreBtncntrl.deleteMe()
            dbDropDowncntrl.deleteMe()
        if restoreDef:
            restoreDef.deleteMe()
        if cmdDef:
            cmdDef.deleteMe()

    @d.eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
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
        inputs: adsk.core.CommandCreatedEventArgs = args
        
        self.logger.info("============================================================================================")
        self.logger.info("-----------------------------------dogbone started------------------------------------------")
        self.logger.info("============================================================================================")
            
        self.faces = []
        self.errorCount = 0
        self.faceSelections.clear()
        
        self.selectedOccurrences = {} 
        self.selectedFaces = {} 
        self.selectedEdges = {} 
        self.registry = dbFaces.DbFaces()
        
        self.workspace = self.ui.activeWorkspace

        self.NORMAL_ID = 'dogboneNormalId'
        self.MINIMAL_ID = 'dogboneMinimalId'
                
        argsCmd: adsk.core.Command = args
        
        self.registry.preLoad()
        
        if self.design.designType != adsk.fusion.DesignTypes.ParametricDesignType :
            returnValue = self.ui.messageBox('DogBone only works in Parametric Mode \n Do you want to change modes?',
                                             'Change to Parametric mode',
                                             adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                                             adsk.core.MessageBoxIconTypes.WarningIconType)
            if returnValue != adsk.core.DialogResults.DialogYes:
                return
            self.design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        self.readDefaults()

        inputs = adsk.core.CommandInputs.cast(inputs.command.commandInputs)
        
        selInput0 = inputs.addSelectionInput('select',
                                             'Face',
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
            'toolDia', 'Tool Diameter               ', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.toolDiaStr))
        inp.tooltip = "Size of the tool with which you'll cut the dogbone."
        
        offsetInp = inputs.addValueInput(
            'toolDiaOffset', 'Tool diameter offset', self.design.unitsManager.defaultLengthUnits,
            adsk.core.ValueInput.createByString(self.offsetStr))
        offsetInp.tooltip = "Increases the tool diameter"
        offsetInp.tooltipDescription = "Use this to create an oversized dogbone.\n"\
                                        "Normally set to 0.  \n"\
                                        "A value of .010 would increase the dogbone diameter by .010 \n"\
                                        "Used when you want to keep the tool diameter and oversize value separate"
        
        modeGroup = adsk.core.GroupCommandInput.cast(inputs.addGroupCommandInput('modeGroup', 'Mode'))
        modeGroup.isExpanded = self.expandModeGroup
        modeGroupChildInputs = modeGroup.children
        
        modeRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('modeRow', 'Mode', False))
        modeRowInput.listItems.add('Static',
                                   not self.parametric,
                                   'resources/staticMode' )
        modeRowInput.listItems.add('Parametric',
                                   self.parametric,
                                   'resources/parametricMode' )
        modeRowInput.tooltipDescription = "Static dogbones do not move with the underlying component geometry. \n" \
                                "\nParametric dogbones will automatically adjust position with parametric changes to underlying geometry. " \
                                "Geometry changes must be made via the parametric dialog.\nFusion has more issues/bugs with these!"
        
        typeRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('dogboneType',
                                                                                                          'Type',
                                                                                                          False))
        typeRowInput.listItems.add('Normal Dogbone',
                                   self.dbParams.dbType == 'Normal Dogbone',
                                   'resources/normal' )
        typeRowInput.listItems.add('Minimal Dogbone',
                                   self.dbParams.dbType == 'Minimal Dogbone',
                                   'resources/minimal' )
        typeRowInput.listItems.add('Mortise Dogbone',
                                   self.dbParams.dbType == 'Mortise Dogbone',
                                   'resources/hidden' )
        typeRowInput.tooltipDescription = "Minimal dogbones creates visually less prominent dogbones, but results in an interference fit " \
                                            "that, for example, will require a larger force to insert a tenon into a mortise.\n" \
                                            "\nMortise dogbones create dogbones on the shortest sides, or the longest sides.\n" \
                                            "A piece with a tenon can be used to hide them if they're not cut all the way through the workpiece."
        
        mortiseRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('mortiseType', 'Mortise Type', False))
        mortiseRowInput.listItems.add('On Long Side',
                                      self.dbParams.longSide,
                                      'resources/hidden/longside' )
        mortiseRowInput.listItems.add('On Short Side',
                                      not self.dbParams.longSide,
                                      'resources/hidden/shortside' )
        mortiseRowInput.tooltipDescription = "Along Longest will have the dogbones cut into the longer sides." \
                                             "\nAlong Shortest will have the dogbones cut into the shorter sides."
        mortiseRowInput.isVisible = self.dbParams.dbType == 'Mortise Dogbone'

        minPercentInp = modeGroupChildInputs.addValueInput('minimalPercent',
                                                           'Percentage Reduction',
                                                           '',
                                                           adsk.core.ValueInput.createByReal(self.dbParams.minimalPercent))
        minPercentInp.tooltip = "Percentage of tool radius added to dogBone offset."
        minPercentInp.tooltipDescription = "This should typically be left at 10%, but if the fit is too tight, it should be reduced"
        minPercentInp.isVisible = self.dbParams.dbType == 'Minimal Dogbone'

        depthRowInput = adsk.core.ButtonRowCommandInput.cast(modeGroupChildInputs.addButtonRowCommandInput('depthExtent',
                                                                                                           'Depth Extent',
                                                                                                           False))
        depthRowInput.listItems.add('From Selected Face',
                                    not self.dbParams.fromTop,
                                    'resources/fromFace' )
        depthRowInput.listItems.add('From Top Face',
                                    self.dbParams.fromTop,
                                    'resources/fromTop' )
        depthRowInput.tooltipDescription = "When \"From Top Face\" is selected, all dogbones will be extended to the top most face\n"\
                                            "\nThis is typically chosen when you don't want to, or can't do, double sided machining."
 
        settingGroup = adsk.core.GroupCommandInput.cast(inputs.addGroupCommandInput('settingsGroup',
                                                                                    'Settings'))
        settingGroup.isExpanded = self.expandSettingsGroup
        settingGroupChildInputs = settingGroup.children

        occurrenceTable = adsk.core.TableCommandInput.cast(inputs.addTableCommandInput('occTable', 'OccurrenceTable', 2, "1:1"))
        occurrenceTable.isFullWidth = True

        rowCount = 0
        if not self.registry.registeredFaceObjectsAsList:
            for faceObject in self.registry.registeredFaceObjectsAsList:
                occurrenceTable.addCommandInput(inputs.addImageCommandInput(f"row{rowCount}", 
                                                                            faceObject.occurrenceHash, 
                                                                            'resources/tableBody/16x16-normal.png'),
                                                                            rowCount,
                                                                            0)
                occurrenceTable.addCommandInput(inputs.addTextBoxCommandInput(f"row{rowCount}Name",
                                                                            "          ",
                                                                            faceObject.face.body.name,
                                                                            1,
                                                                            True),
                                                                            rowCount,
                                                                            1)
                rowCount+=1


        benchMark = settingGroupChildInputs.addBoolValueInput("benchmark",
                                                              "Benchmark time",
                                                              True,
                                                              "",
                                                              self.benchmark)
        benchMark.tooltip = "Enables benchmarking"
        benchMark.tooltipDescription = "When enabled, shows overall time taken to process all selected dogbones."

        logDropDownInp = adsk.core.DropDownCommandInput.cast(settingGroupChildInputs.addDropDownCommandInput("logging",
                                                                                                             "Logging level",
                                                                                                             adsk.core.DropDownStyles.TextListDropDownStyle))
        logDropDownInp.tooltip = "Enables logging"
        logDropDownInp.tooltipDescription = "Creates a dogbone.log file. \n" \
                     "Location: " +  os.path.join(self.appPath, 'dogBone.log')

        logDropDownInp.listItems.add('Notset',
                                     self.logging == 0)
        logDropDownInp.listItems.add('Debug',
                                     self.logging == 10)
        logDropDownInp.listItems.add('Info',
                                     self.logging == 20)

        cmd = adsk.core.Command.cast(args.command)

        # Add handlers to this command.
        self.onExecute(event=cmd.execute)
        self.onFaceSelect(event=cmd.selectionEvent)
        self.onValidate(event=cmd.validateInputs)
        self.onChange(event=cmd.inputChanged)
        self.setSelections(self.registry,
                           inputs,
                           selInput0 )
        
    @d.eventHandler(handler_cls=adsk.core.CommandCreatedEventHandler)
    def onRestore(self, args:adsk.core.CommandCreatedEventArgs):
        pass
            
    def setSelections(self, feMgr, commandInputs, activeCommandInput): #updates the selected entities on the UI
        collection = adsk.core.ObjectCollection.create()
        self.ui.activeSelections.clear()
        
        
        faces = map(lambda x: x.face, feMgr.selectedFaceObjectsAsList)
        edges = map(lambda x: x.edge, feMgr.selectedEdgeObjectsAsList)

        commandInputs.itemById('select').hasFocus = True        
        for face in faces:
            collection.add(face)
            
        self.ui.activeSelections.all = collection
        
        commandInputs.itemById('edgeSelect').isVisible = True
    
        commandInputs.itemById('edgeSelect').hasFocus = True        
        
        for edge in edges:
            collection.add(edge)
            
        self.ui.activeSelections.all = collection
        
        activeCommandInput.hasFocus = True

    #==============================================================================
    #  routine to process any changed selections
    #  this is where selection and deselection management takes place
    #  also where eligible edges are determined
    #==============================================================================
    @d.eventHandler(handler_cls=adsk.core.InputChangedEventHandler)
    def onChange(self, args:adsk.core.InputChangedEventArgs):
        changedInput = adsk.core.CommandInput.cast(args.input)

        if changedInput.id == 'dogboneType':
            changedInput.commandInputs.itemById('minimalPercent').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Minimal Dogbone')
            changedInput.commandInputs.itemById('mortiseType').isVisible = (changedInput.commandInputs.itemById('dogboneType').selectedItem.name == 'Mortise Dogbone')
       

        if changedInput.id != 'select' and changedInput.id != 'edgeSelect':
            return
            
        activeSelections = self.ui.activeSelections.all #save active selections - selections are sensitive and fragile, any processing beyond just reading on live selections will destroy selection 

        self.logger.debug('input changed- {}'.format(changedInput.id))
        faces = faceSelections(activeSelections)
        edges = edgeSelections(activeSelections)
        
        if changedInput.id == 'select':

            #==============================================================================
            #            processing changes to face selections
            #==============================================================================            
            
            removedFaces = [face for face in map(lambda x: x.face, self.registry.selectedFaceObjectsAsList) if face not in faces]
            addedFaces = [face for face in faces if face not in map(lambda x: x.face, self.registry.selectedFaceObjectsAsList)]
            
            for face in removedFaces:
                #==============================================================================
                #         Faces have been removed
                #==============================================================================
                self.logger.debug('face being removed {}'.format(face.entityToken))
                self.registry.deleteFace(face)
                            
            for face in addedFaces:
            #==============================================================================
            #             Faces has been added 
            #==============================================================================
                 
                self.logger.debug('face being added {}'.format(face.entityToken))
                self.registry.addFace(face, self.dbParams)
                            
                if not changedInput.commandInputs.itemById('edgeSelect').isVisible:
                    changedInput.commandInputs.itemById('edgeSelect').isVisible = True
            self.setSelections(self.registry, changedInput.commandInputs, changedInput.commandInputs.itemById('select')) #update selections
            return

#==============================================================================
#                  end of processing faces
#==============================================================================


        #==============================================================================
        #         Processing changed edge selection            
        #==============================================================================
        if changedInput.id != 'edgeSelect':
            return
            
        removedEdges = [edge for edge in map(lambda x: x.edge, self.registry.selectedEdgeObjectsAsList) if edge not in edges]
        addedEdges = [edge for edge in edges if edge not in map(lambda x: x.edge, self.registry.selectedEdgeObjectsAsList)]


        for edge in removedEdges:
            #==============================================================================
            #             Edges have been removed
            #==============================================================================
            self.registry.deleteEdge(edge)

        for edge in addedEdges:
            #==============================================================================
            #         Edges have been added
            #==============================================================================
            self.registry.addEdge(edge)
            edge.dbParams = self.dbParams
            
        self.setSelections(self.registry, changedInput.commandInputs, changedInput.commandInputs.itemById('edgeSelect'))


    def parseInputs(self, inputs):
        '''==============================================================================
           put the selections into variables that can be accessed by the main routine            
           ==============================================================================
       '''
        inputs = {inp.id: inp for inp in inputs}
        
        self.logger = logging.getLogger('dogbone')

        self.logging = self.loggingLevels[inputs['logging'].selectedItem.name]
        self.logger.level = self.logging

        self.logger.debug('Parsing inputs')

        self.toolDiaStr = inputs['toolDia'].expression
        self.dbParams.toolDia = inputs['toolDia'].value
        self.toolDiaOffsetStr = inputs['toolDiaOffset'].expression
        self.dbParams.toolDiaOffset = inputs['toolDiaOffset'].value
        self.benchmark = inputs['benchmark'].value
        self.dbParams.dbType = inputs['dogboneType'].selectedItem.name
        self.dbParams.minimalPercent = inputs['minimalPercent'].value
        self.dbParams.fromTop = (inputs['depthExtent'].selectedItem.name == 'From Top Face')
        self.parametric = (inputs['modeRow'].selectedItem.name == 'Parametric')
        self.dbParams.longSide = (inputs['mortiseType'].selectedItem.name == 'On Long Side')
        self.expandModeGroup = (inputs['modeGroup']).isExpanded
        self.expandSettingsGroup = (inputs['settingsGroup']).isExpanded

        self.logger.debug('self.fromTop = {}'.format(self.dbParams.fromTop))
        self.logger.debug('self.dbType = {}'.format(self.dbParams.dbType))
        self.logger.debug('self.parametric = {}'.format(self.parametric))
        self.logger.debug('self.toolDiaStr = {}'.format(self.toolDiaStr))
        self.logger.debug('self.toolDia = {}'.format(self.dbParams.toolDia))
        self.logger.debug('self.toolDiaOffsetStr = {}'.format(self.toolDiaOffsetStr))
        self.logger.debug('self.toolDiaOffset = {}'.format(self.dbParams.toolDiaOffset))
        self.logger.debug('self.benchmark = {}'.format(self.benchmark))
        self.logger.debug('self.mortiseType = {}'.format(self.dbParams.longSide))
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
        
    def closeLogger(self):
#        logging.shutdown()
        for handler in self.logger.handlers:
            handler.flush()
            handler.close()
            self.logger.removeHandler(handler)

    @d.eventHandler(handler_cls=adsk.core.CommandEventHandler)
    def onExecute(self, args:adsk.core.CommandEventArgs):
        start = time.time()
        
        
        self.originWorkspace.activate()

        self.logger.log(0, 'logging Level = %(levelname)')
        self.parseInputs(args.firingEvent.sender.commandInputs)
        self.logger.level =self.logging

        self.writeDefaults()

        if self.parametric:
            userParams = adsk.fusion.UserParameters.cast(self.design.userParameters)
            
            #set up parameters, so that changes can be easily made after dogbones have been inserted
            if not userParams.itemByName('dbToolDia'):
                dValIn = adsk.core.ValueInput.createByString(self.toolDiaStr)
                dParameter = userParams.add('dbToolDia', dValIn, self.design.unitsManager.defaultLengthUnits, '')
                dParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbToolDia')
                uParam.expression = self.toolDiaStr
                uParam.isFavorite = True
                
            if not userParams.itemByName('dbOffset'):
                rValIn = adsk.core.ValueInput.createByString(self.toolDiaOffsetStr)
                rParameter = userParams.add('dbOffset',rValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbOffset')
                uParam.expression = self.toolDiaOffsetStr
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbRadius'):
                rValIn = adsk.core.ValueInput.createByString('(dbToolDia + dbOffset)/2')
                rParameter = userParams.add('dbRadius',rValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbRadius')
                uParam.expression = '(dbToolDia + dbOffset)/2'
                uParam.comment = 'Do NOT change formula'

            if not userParams.itemByName('dbMinPercent'):
                rValIn = adsk.core.ValueInput.createByReal(self.dbParams.minimalPercent)
                rParameter = userParams.add('dbMinPercent',rValIn, '', '')
                rParameter.isFavorite = True
            else:
                uParam = userParams.itemByName('dbMinPercent')
                uParam.value = self.dbParams.minimalPercent
                uParam.comment = ''
                uParam.isFavorite = True

            if not userParams.itemByName('dbHoleOffset'):
                oValIn = adsk.core.ValueInput.createByString('dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.dbParams.dbType == 'Minimal Dogbone' else 'dbRadius' if self.dbParams.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)')
                oParameter = userParams.add('dbHoleOffset', oValIn, self.design.unitsManager.defaultLengthUnits, 'Do NOT change formula')
            else:
                uParam = userParams.itemByName('dbHoleOffset')
                uParam.expression = 'dbRadius / sqrt(2)' + (' * (1 + dbMinPercent/100)') if self.dbParams.dbType == 'Minimal Dogbone' else 'dbRadius' if self.dbParams.dbType == 'Mortise Dogbone' else 'dbRadius / sqrt(2)'
                uParam.comment = 'Do NOT change formula'

            self.radius = userParams.itemByName('dbRadius').value
            self.offset = adsk.core.ValueInput.createByString('dbOffset')
            self.offset = adsk.core.ValueInput.createByReal(userParams.itemByName('dbHoleOffset').value)

            self.createParametricDogbones()

        else: #Static dogbones

            self.radius = (self.dbParams.toolDia + self.dbParams.toolDiaOffset) / 2
            self.offset = self.radius / sqrt(2)  * (1 + self.dbParams.minimalPercent/100) if self.dbParams.dbType == 'Minimal Dogbone' else self.radius if self.dbParams.dbType == 'Mortise Dogbone' else self.radius / sqrt(2)
            
            self.createStaticDogbones()
        
        self.logger.info('all dogbones complete\n-------------------------------------------\n')

        self.closeLogger()
        
        if self.benchmark:
            util.messageBox("Benchmark: {:.02f} sec processing {} edges".format(
                time.time() - start, len(self.edges)))


    ################################################################################        
    @d.eventHandler(handler_cls=adsk.core.ValidateInputsEventHandler)
    def onValidate(self, args:adsk.core.ValidateInputsEventArgs):
        cmd: adsk.core.ValidateInputsEventArgs = args
        cmd = args.firingEvent.sender

        for input in cmd.commandInputs:
            if input.id == 'select':
                if input.selectionCount < 1:
                    args.areInputsValid = False
            elif input.id == 'circDiameter':
                if input.value <= 0:
                    args.areInputsValid = False
                    
    @d.eventHandler(handler_cls=adsk.core.SelectionEventHandler)
    def onFaceSelect(self, args:adsk.core.SelectionEventArgs):
        '''==============================================================================
            Routine gets called with every mouse movement, if a commandInput select is active                   
           ==============================================================================
       '''
        eventArgs: adsk.core.SelectionEventArgs = args
        # Check which selection input the event is firing for.
        activeIn = eventArgs.firingEvent.activeInput
        if activeIn.id != 'select' and activeIn.id != 'edgeSelect':
            return # jump out if not dealing with either of the two selection boxes
        eventArgs.isSelectable = self.registry.isSelectable(eventArgs.selection.entity)
        return

    def removeHandlers(self):
        adsk.terminate()

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
        holeInput: adsk.fusion.HoleFeatureInput = None
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
                (topFace, topFaceRefPoint) = util.getTopFace(makeNative(occurrenceFace[0].face))
                self.logger.info('Processing holes from top face - {}'.format(topFace.body.name))

            for selectedFace in occurrenceFace:
                if len(selectedFace.selectedEdges.values()) <1:
                    self.logger.debug('Face has no edges')
                face = makeNative(selectedFace.face)
                
                comp: adsk.fusion.Component = comp
                
                if not face.isValid:
                    self.logger.debug('revalidating Face')
                    face = reValidateFace(comp, selectedFace.refPoint)
                self.logger.debug('Processing Face = {}'.format(face.tempId))
              
                #faceNormal = util.getFaceNormal(face.nativeObject)
                if self.fromTop:
                    self.logger.debug('topFace type {}'.format(type(topFace)))
                    if not topFace.isValid:
                       self.logger.debug('revalidating topFace') 
                       topFace = reValidateFace(comp, topFaceRefPoint)

                    topFace = makeNative(topFace)
                       
                    self.logger.debug('topFace isValid = {}'.format(topFace.isValid))
                    transformVector = util.getTranslateVectorBetweenFaces(face, topFace)
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
                        if not util.isEdgeAssociatedWithFace(face, edge):
                            continue  # skip if edge is not associated with the face currently being processed
                    except:
                        pass
                    
                    startVertex = adsk.fusion.BRepVertex.cast(util.getVertexAtFace(face, edge))
                    extentToEntity = util.findExtent(face, edge)

                    extentToEntity = makeNative(extentToEntity)
                    self.logger.debug('extentToEntity - {}'.format(extentToEntity.isValid))
                    if not extentToEntity.isValid:
                        self.logger.debug('To face invalid')

                    try:
                        (edge1, edge2) = util.getCornerEdgesAtFace(face, edge)
                    except:
                        self.logger.exception('Failed at findAdjecentFaceEdges')
                        util.messageBox('Failed at findAdjecentFaceEdges:\n{}'.format(traceback.format_exc()))
                    
                    centrePoint = makeNative(startVertex).geometry.copy()
                        
                    selectedEdgeFaces = makeNative(selectedEdge.edge).faces
                    
                    dirVect = adsk.core.Vector3D.cast(util.getFaceNormal(selectedEdgeFaces[0]).copy())
                    dirVect.add(util.getFaceNormal(selectedEdgeFaces[1]))
                    dirVect.normalize()
                    dirVect.scaleBy(centreDistance)  #ideally radius should be linked to parameters, 
 
                    if self.dbType == 'Mortise Dogbone':
                        direction0 = util.correctedEdgeVector(edge1,startVertex) 
                        direction1 = util.correctedEdgeVector(edge2,startVertex)
                        
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
                        dirVect = adsk.core.Vector3D.cast(util.getFaceNormal(makeNative(selectedEdgeFaces[0])).copy())
                        dirVect.add(util.getFaceNormal(makeNative(selectedEdgeFaces[1])))
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
            util.messageBox('Reported errors:{}\nYou may not need to do anything, \nbut check holes have been created'.format(self.errorCount))

    def createStaticDogbones(self):
        self.logger.info('Creating static dogbones')
        self.errorCount = 0
        if not self.design:
            raise RuntimeError('No active Fusion design')
        minPercent = 1+self.dbParams.minimalPercent/100 if self.dbParams.dbType == 'Minimal Dogbone' else  1
        occurrenceEdgeList = self.registry.selectedEdgesAsGroupList


        for occGroupName, edgeGroup in occurrenceEdgeList.items():
            topPlane = None
                
            if not edgeGroup:
                continue
            if self.dbParams.fromTop:
                topPlane = edgeGroup[0].topFacePlane
                self.logger.info('Processing holes from top face - {}'.format(edgeGroup[0].parent.faceHash))

            bodies = None
                           
            bodyCollection = adsk.core.ObjectCollection.create()
            tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
            startTlMarker = self.design.timeline.markerPosition
              
            for edgeObject in edgeGroup:
                
                self.logger.debug('Processing edge - {}'.format(edgeObject.tempId))

                edge = edgeObject.edge
                dbToolBody = edgeObject.getdbTool()
                if not bodies:
                    bodies = dbToolBody
                else:
                    tempBrepMgr.booleanOperation(bodies, dbBody, adsk.fusion.BooleanTypes.UnionBooleanType)
                    
            if not bodies:
                continue

            timelineGroup = self.registry.timeLineGroups.get(occGroupName, False)
            if timelineGroup:
                timelineGroup.isCollapsed = False
                oldBaseFeats = timelineGroup.item(0)
                oldBaseFeats.isSuppressed = False
                oldBaseFeats.rollTo(False)
#                oldBaseFeats.entity.deleteMe()
                
            baseFeats = self.rootComp.features.baseFeatures
            baseFeat = baseFeats.add()
            baseFeat.startEdit()
    
            dbB = self.rootComp.bRepBodies.add(bodies, baseFeat)
            dbB.name = 'dbHole'
            baseFeat.finishEdit()
            baseFeat.name = 'dbBaseFeat'
            
            targetBody = edge.body
            
                
            bodyCollection.add(baseFeat.bodies.item(0))
            
            if timelineGroup:
                combine = timelineGroup.item(2).entity
                combine.toolBodies = bodyCollection
                oldBaseFeats.entity.deleteMe()
            else:
                
                combineInput = self.rootComp.features.combineFeatures.createInput(targetBody, bodyCollection)
                combineInput.isKeepToolBodies = False
                combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                combine = self.rootComp.features.combineFeatures.add(combineInput)
                combine.name = 'dbCombine'
                                            
            endTlMarker = self.design.timeline.markerPosition-1
            if endTlMarker - startTlMarker >0:
                timelineGroup = self.design.timeline.timelineGroups.add(startTlMarker,endTlMarker)
                timelineGroup.name = 'db:' + occGroupName
#            self.logger.debug('doEvents - allowing fusion to refresh')
            adsk.doEvents()
            
        if self.errorCount >0:
            util.messageBox('Reported errors:{}\nYou may not need to do anything, \nbut check holes have been created'.format(self.errorCount))

