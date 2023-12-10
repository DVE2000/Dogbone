import adsk.fusion


def calcId(x):
    return hash(x.entityToken)

def calcOccurrenceId(x):
    if x.objectType == adsk.fusion.BRepBody.classType():
        return ( calcId(x.assemblyContext) if x.assemblyContext else calcId(x)) 
    return ( calcId(x.assemblyContext) if x.assemblyContext else calcId(x.body))

def setSupressionState(entity, state):
    entity.isSuppressed = state

def makeNative(x):
    return x.nativeObject if x.nativeObject else x


def reValidateFace(comp, x):
    return comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False).item(0)
