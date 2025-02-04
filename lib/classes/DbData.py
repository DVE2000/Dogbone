# -*- coding: utf-8 -*-
#Dataclass structure that gets attached to each entity - allows mode and style of dogbone to be retrieved and used in refresh
import os
import logging
import adsk.core
import json

from dataclasses import dataclass

from ...py_packages.dataclasses_json import dataclass_json

# appPath = os.path.dirname(os.path.abspath(__file__))
basePath = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(basePath, "defaults.dat")

logger = logging.getLogger("dogbone.DbParams")

@dataclass_json
@dataclass
class DbParams:
    """Dataclass - Holds add-in instance setup values"""

    toolDiaStr: str = "0.25 in"
    dbType: str = "Normal Dogbone"
    fromTop: bool = True
    toolDiaOffsetStr: str = "0 cm"

    mortiseType: bool = False
    longSide: bool = True

    minimalPercent: float = 10.0

    angleDetectionGroup: bool = False
    acuteAngle: bool = False
    obtuseAngle: bool = False
    minAngleLimit: float = 89.0
    maxAngleLimit: float = 91.0

    # parametric: bool = False
    expandModeGroup: bool = True
    expandSettingsGroup: bool = True
    logging: int = 0
    benchmark: bool = False

    isPromotedCreate: bool = True
    isPromotedRefresh: bool = True
    isPromotedCreateMfg: bool = True
    isPromotedRefreshMfg: bool = True

    previewEnabled: bool = True

    @classmethod
    def read_file(cls,  path: str) -> str:
        with open(path, "r", encoding="UTF-8") as file:
            return file.read()

    @classmethod
    def read_defaults(cls):
        logger.info("config file read")

        if not os.path.isfile(CONFIG_PATH):
            return False

        try:
            return cls.read_file(CONFIG_PATH)
        except ValueError:
            return False

    def write_defaults(self):
        logger.info("config file write")
        self.write_file(CONFIG_PATH, self.to_json())

    def write_file(cls, path: str, data: str):
        with open(path, "w", encoding="UTF-8") as file:
            file.write(data)

    def __post_init__(self):
        read_str = DbParams.read_defaults()
        if read_str:
            self.__dict__ = json.loads(read_str)

    @property
    def design(self):
        app = adsk.core.Application.get()
        return app.activeProduct

    @property
    def toolDia(self):
        return self.design.unitsManager.evaluateExpression(self.toolDiaStr)

    @property
    def toolDiaOffset(self):
        return self.design.unitsManager.evaluateExpression(self.toolDiaOffsetStr)

params = DbParams()
