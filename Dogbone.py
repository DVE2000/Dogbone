#Author-Casey Rogers
#Description-Create a dogbone for milling
'''
Version 0.1
Current Functionality:
Select two edges that form a <180 degree corner, select a terminating face and specify a diameter.
The add-in will create a dogbone joint between the specified edges a terminating face with the given diameter.

Known Bugs:
Depending on the positioning of the corners and the terminating face, you will get a "zero extent" error.
The dogbone control, when promoted to the create panel, doesn't do anything when pressed.
Symmetry constraint is not maintained when the edges are moved.

Planned Features:
Allow non-planar terminating faces
Improved functionality for non-rightangle corners
Better unit management
Make dogbones respond to changing user parameters
'''

import adsk.core, adsk.fusion, traceback

handlers = []




def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface

        #event handlers
        class dogboneCommandCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                cmd = args.command
        
                inputs = cmd.commandInputs
        
                selInput0 = inputs.addSelectionInput('edgeSelect', 'Interior Edges', 'Select the edge interior to each corner')
                selInput0.addSelectionFilter('LinearEdges')
                selInput0.setSelectionLimits(1,0)
        
                initialVal = adsk.core.ValueInput.createByReal(0)
                inputs.addValueInput('circDiameter', 'Tool Diameter', 'cm', initialVal)
        
                # Connect up to command related events.
                onExecute = CommandExecutedHandler()
                cmd.execute.add(onExecute)
                handlers.append(onExecute)

                #onInputChanged = InputChangedHandler()
        
                #cmd.inputChanged.add(onInputChanged)
                #handlers.append(onInputChanged) 

                onValidateInputs = ValidateInputsHandler()
                cmd.validateInputs.add(onValidateInputs)
                handlers.append(onValidateInputs)
        
        class CommandExecutedHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                app = adsk.core.Application.get()
                ui  = app.userInterface
                try:
                    command = args.firingEvent.sender
            
                # Get the data and settings from the command inputs.
                    for input in command.commandInputs:
                        if input.id == 'circDiameter':
                            circStr = input.expression
                            circVal = input.value
                        elif input.id == 'edgeSelect':
                            edges = []
                            for i in range(input.selectionCount):
                                edges.append(input.selection(i).entity)
                    for edge in edges:
                        createDogbone(circStr, circVal, edge)
                    # Do something with the results.
                except:
                    if ui:
                        ui.messageBox('command executed failed:\n{}'.format(traceback.format_exc()))
        class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                app = adsk.core.Application.get()
                ui  = app.userInterface
                try:
                    # Get the command.
                    cmd = args.firingEvent.sender
        
                    # Check that two selections are satisfied.
                    for input in cmd.commandInputs:
                        if input.id == 'edgeSelect':
                            if input.selectionCount < 1:
                                # Set that the inputs are not valid and return.
                                args.areInputsValid = False
                                return
                        elif input.id == 'circDiameter':
                            if input.value <= 0:
                                # Set that the inputs are not valid and return.
                                args.areInputsValid = False
                                return
                except:
                    if ui:
                        ui.messageBox('Input changed event failed:\n{}'.format(traceback.format_exc()))     

        #add add-in to UI
        cmdDefs = ui.commandDefinitions
        buttonDogbone = cmdDefs.addButtonDefinition('dogboneBtn', 'Dogbone', 'Creates a dogbone at the corner of two lines/edges')
        
        dogboneCommandCreated = dogboneCommandCreatedEventHandler()
        buttonDogbone.commandCreated.add(dogboneCommandCreated)
        handlers.append(dogboneCommandCreated)

        createPanel = ui.toolbarPanels.itemById('SolidCreatePanel')
        
        buttonControl = createPanel.controls.addCommand(buttonDogbone, 'dogboneBtn')
        
        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True
    
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            

def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        
        cmdDef = ui.commandDefinitions.itemById('dogboneBtn')
        if cmdDef:
            cmdDef.deleteMe()
        createPanel = ui.toolbarPanels.itemById('SolidCreatePanel')
        cntrl = createPanel.controls.itemById('dogboneBtn')
        if cntrl:
            cntrl.deleteMe()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Returns points A, B, C where A is shared between the two input edges
def findPoints(edge0, edge1):
    if edge0.classType() == 'adsk::fusion::SketchLine':
        point0_0 = edge0.startSketchPoint
        point0_1 = edge0.endSketchPoint
        point1_0 = edge1.startSketchPoint
        point1_1 = edge1.endSketchPoint
    else:
        point0_0 = edge0.startVertex
        point0_1 = edge0.endVertex
        point1_0 = edge1.startVertex
        point1_1 = edge1.endVertex  
    if (point0_0 == point1_0):
        pointA = point0_0
        pointB = point0_1
        pointC = point1_1
    elif (point0_0 == point1_1):
        pointA = point0_0
        pointB = point0_1
        pointC = point1_0
    elif (point0_1 == point1_0):
        pointA = point0_1
        pointB = point0_0
        pointC = point1_1
    elif (point0_1 == point1_1):
        pointA = point0_1
        pointB = point0_0
        pointC = point1_0
    else:
        return False
            
    return pointA, pointB, pointC

def findMidPoint(line):
    x0 = line.startSketchPoint.geometry
    x1 = line.endSketchPoint.geometry
    y0 = x0.y
    y1 = x1.y
    x0 = x0.x
    x1 = x1.x
    midPoint = adsk.core.Point3D.create((x0 + x1)/2, (y0 + y1)/2, 0)
    return midPoint

# Identifies one corner given an edge and returns the edges defining that corner
def findCorner(edge):
    faces = edge.faces
    edges0 = faces.item(0).edges
    edges1 = faces.item(1).edges
    for e0 in edges0:
        if e0 == edge:
            continue
        for e1 in edges1:
            if e1 == edge:
                continue
            a0, a1 = e0.startVertex, e0.endVertex
            b0, b1 = e1.startVertex, e1.endVertex
            if a0 == b0 or a0 == b1 or a1 == b0 or a1 == b1:
                return e0, e1
    return False

def createDogbone(circStr, circVal, edge):
    try:
        #initialization
        app = adsk.core.Application.get()
        ui = app.userInterface

        design = app.activeProduct
        if not design:
            ui.messageBox('No active Fusion design', 'No Design')
            return
        #grab various important objects/collections
        rootComp = design.rootComponent
        sketches = rootComp.sketches
        planes = rootComp.constructionPlanes
        
        #Find three points
        edgeTuple = findCorner(edge)
        if not edgeTuple:
            adsk.core.Application.get().userInterface.messageBox('non-adjacent edges')
            return
        edge0, edge1 = edgeTuple[0], edgeTuple[1]
            
        #create a plane on the interior edge
        inputPlane = planes.createInput() #add occurence handling
        tf = inputPlane.setByDistanceOnPath(edge, adsk.core.ValueInput.createByReal(0))
        if not tf:
            ui.messageBox('Failed to create sketchplane')
            return
        plane = planes.add(inputPlane)
        inputPlane = None
        
        #create a sketch
        sketch = sketches.add(plane)
        line1 = sketch.project(edge0)
        line2 = sketch.project(edge1)
        line1 = line1.item(0)
        line2 = line2.item(0)
        
        lines = sketch.sketchCurves.sketchLines
        constraints = sketch.geometricConstraints
        circles = sketch.sketchCurves.sketchCircles
        
        #create dogbone sketch
        pointTuple = findPoints(line1, line2)
        if not pointTuple:   
            adsk.core.Application.get().userInterface.messageBox('non-adjacent edges')
            return
        line0 = lines.addByTwoPoints(pointTuple[0], pointTuple[1].geometry)
        line0.isConstruction = True
        line1.isConstruction = True
        line2.isConstruction = True
        constraints.addSymmetry(line1, line2, line0)
        length = sketch.sketchDimensions.addDistanceDimension(line0.startSketchPoint, line0.endSketchPoint,
                                                     adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                     findMidPoint(line0));
        length.parameter.expression = circStr +  "/ 2"
        circle = circles.addByCenterRadius(line0.endSketchPoint, circVal / 2)
        constraints.addCoincident(pointTuple[0], circle)
        
        #sweep the dogbone
        prof =  sketch.profiles.item(0)
        sweeps = rootComp.features.sweepFeatures
        swInput = sweeps.createInput(prof, rootComp.features.createPath(edge, False), adsk.fusion.FeatureOperations.CutFeatureOperation)
        swInput.distanceOne = adsk.core.ValueInput.createByReal(1.0)
        swInput.distanceTwo = adsk.core.ValueInput.createByReal(0)

        sweeps.add(swInput)
        
    
    except Exception as error:
        ui.messageBox('Failed : ' + str(error))

           
#Explicitly call the run function.
#stop({'IsApplicationStartup':True})
#run({'IsApplicationStartup':True})
#stop({'IsApplicationStartup':True})

