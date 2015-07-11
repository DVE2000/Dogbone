#Author-Casey Rogers
#Description-An Add-In for making dog-bone fillets.

#Select edges interior to 90 degree angles. Specify a tool diameter and a radial offset. The add-in will then create a dog-bone with diamater equal to the tool diameter plus
#twice the offset (as the offset is applied to the radius) at each selected edge.

#Thanks to Tapnair for looking of the code and making some nice additions!

# Version 1
# Current Functionality:
# Select edges interior to 90 degree angles. Specify a tool diameter and a radial offset.
# The add-in will then create a dogbone with diamater equal to the tool diameter plus
# twice the offset (as the offset is applied to the radius) at each selected edge.

#Known Bugs:
#The add-in's custom icon is not displaying in the user interface.

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
                product = app.activeProduct
                inputs = cmd.commandInputs

                selInput0 = inputs.addSelectionInput('edgeSelect', 'Interior Edges', 'Select the edge interior to each corner')
                selInput0.addSelectionFilter('LinearEdges')
                selInput0.setSelectionLimits(1,0)

                initialVal = adsk.core.ValueInput.createByReal(0)
                inputs.addValueInput('circDiameter', 'Tool Diameter', product.unitsManager.defaultLengthUnits, initialVal)

                initialVal = adsk.core.ValueInput.createByReal(0)
                inputs.addValueInput('offset', 'Radial Offset', product.unitsManager.defaultLengthUnits, initialVal)


                # Connect up to command related events.
                onExecute = CommandExecutedHandler()
                cmd.execute.add(onExecute)
                handlers.append(onExecute)

                onValidateInputs = ValidateInputsHandler()
                cmd.validateInputs.add(onValidateInputs)
                handlers.append(onValidateInputs)

        class CommandExecutedHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                app = adsk.core.Application.get()
                ui  = app.userInterface
                design = app.activeProduct
                timeline = design.timeline
                try:
                    command = args.firingEvent.sender

                    # Get the data and settings from the command inputs.
                    offStr = None
                    offVal = None
                    for input in command.commandInputs:
                        if input.id == 'circDiameter':
                            circStr = input.expression
                            circVal = input.value
                        elif input.id == 'offset':
                            offStr = input.expression
                        elif input.id == 'edgeSelect':
                            edges = []
                            for i in range(input.selectionCount):
                                edges.append(input.selection(i).entity)
                    startIndex, endIndex = None, None
                    # Create a dogbone for each edge specified
                    for edge in edges:
                        startStop = createDogbone(circStr, circVal, edge, offStr)
                        if not startStop:
                            ui.messageBox("Error in Dogbone creation")
                            return
                        if startIndex == None:
                            startIndex = startStop[0]
                        endIndex =startStop[1]
                    # Do something with the results.
                    if not startIndex == None and not endIndex == None:
                        timeline.timelineGroups.add(startIndex, endIndex)
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

        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')

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
        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
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

# Return MIDPOINT of LINE
def findMidPoint(line):
    x0 = line.startSketchPoint.geometry
    x1 = line.endSketchPoint.geometry
    y0 = x0.y
    y1 = x1.y
    x0 = x0.x
    x1 = x1.x
    midPoint = adsk.core.Point3D.create((x0 + x1)/2, (y0 + y1)/2, 0)
    return midPoint

# Finds and returns two EDGES that form a corner adjacent to EDGE, or FALSE if EEDGE is not interior to a corner
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

# Creates a dogbone with the given offset and tool diamaeter parameters at the
# specified EDGE.
def createDogbone(circStr, circVal, edge, offStr):
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

        # Find two edges that form the corner to be filleted
        edgeTuple = findCorner(edge)
        if not edgeTuple:
            adsk.core.Application.get().userInterface.messageBox('non-adjacent edges')
            return
        edge0, edge1 = edgeTuple[0], edgeTuple[1]

        #create a plane on one end of the interior edge
        inputPlane = planes.createInput() #add occurence handling
        tf = inputPlane.setByDistanceOnPath(edge, adsk.core.ValueInput.createByReal(0))
        plane = planes.add(inputPlane)
        if not plane or not tf:
            ui.messageBox('Failed to create sketchplane')
            return
        # Record the timeline index of the first feature createDogbone makes
        startIndex = plane.timelineObject.index
        inputPlane = None

        #create a sketch and project the dogbone's corner onto the sketch
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
        # This is a temporary point for our Dogbone sketch's centerline to end at
        tempPoint = adsk.core.Point3D.create((pointTuple[1].geometry.x + pointTuple[2].geometry.x)/2,
                                              (pointTuple[1].geometry.y + pointTuple[2].geometry.y)/2, 0)
        line0 = lines.addByTwoPoints(pointTuple[0], tempPoint)
        line0.isConstruction = True
        line1.isConstruction = True
        line2.isConstruction = True
        constraints.addSymmetry(line1, line2, line0)
        # Constrain the length of the centerline to the radius of the desired dogbone
        length = sketch.sketchDimensions.addDistanceDimension(line0.startSketchPoint, line0.endSketchPoint,
                                                     adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                     findMidPoint(line0));
        if offStr == "0.00 mm":
            length.parameter.expression = circStr +  "/ 2"
        else:
            length.parameter.expression = circStr +  "/ 2 + " + offStr
        # Create the dogbone's profile
        circle = circles.addByCenterRadius(line0.endSketchPoint, circVal / 2)
        constraints.addCoincident(pointTuple[0], circle)

        # Sweep the dogbone
        prof =  sketch.profiles.item(0)
        sweeps = rootComp.features.sweepFeatures
        swInput = sweeps.createInput(prof, rootComp.features.createPath(edge, False), adsk.fusion.FeatureOperations.CutFeatureOperation)
        swInput.distanceOne = adsk.core.ValueInput.createByReal(1.0)
        swInput.distanceTwo = adsk.core.ValueInput.createByReal(0)

        sw = sweeps.add(swInput)
        if not sw:
            return
        # Record the timeline index of the last feature createDogbone makes
        endIndex = sw.timelineObject.index
        return startIndex, endIndex


    except Exception as error:
        ui.messageBox('Failed : ' + str(error))


#Explicitly call the run function.
#stop({'IsApplicationStartup':True})
#run({'IsApplicationStartup':True})
#stop({'IsApplicationStartup':True})

