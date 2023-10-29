import adsk.fusion


def calcId(x):
    return hash(x.entityToken)


def makeNative(x):
    return x.nativeObject if x.nativeObject else x


def reValidateFace(comp, x):
    return comp.findBRepUsingPoint(x, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False).item(0)
