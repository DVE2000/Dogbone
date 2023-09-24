class Selection:
    selectedOccurrences = {}  # key hash(occurrence.entityToken) value:[DbFace,...]
    selectedFaces = {}  # key: hash(face.entityToken) value:[DbFace,...]
    selectedEdges = {}  # kay: hash(edge.entityToken) value:[DbEdge, ...]

    edges = []
    faces = []
