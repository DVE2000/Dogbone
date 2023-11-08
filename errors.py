
#Placeholder for the future - Unused currently
class FaceInvalidError(Exception):
    def __init__(self) -> None:
        super().__init__("Face is no longer available")

class EdgeInvalidError(Exception):
    def __init__(self) -> None:
        super().__init__("Edge is no longer available")

class UpdateError(Exception):
    def __init__(self) -> None:
        super().__init__("Failed to find a body to update")