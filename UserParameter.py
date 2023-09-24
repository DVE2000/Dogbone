from typing import cast

from adsk.core import ValueInput

from .DbData import DbParams
import adsk.fusion

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)

DB_TOOL_DIA = "dbToolDia"
DB_OFFSET = "dbOffset"
DB_MIN_PERCENT = "dbMinPercent"
DB_HOLE_OFFSET = "dbHoleOffset"
DB_RADIUS = "dbRadius"
COMMENT = "Do NOT change formula"

userParams: adsk.fusion.UserParameters = _design.userParameters
default_length_units = _design.unitsManager.defaultLengthUnits


def create_user_parameter(param: DbParams):
    # set up parameters, so that changes can be easily made after dogbones have been inserted

    # TODO: why are some isFavorite = True
    _create_parameter(DB_TOOL_DIA, param.toolDiaStr, favorite=True)
    _create_parameter(DB_OFFSET, param.toolDiaOffsetStr)
    _create_parameter(DB_RADIUS, f"({DB_TOOL_DIA} + {DB_OFFSET})/2")
    _min_percentage(param)
    _create_parameter(DB_HOLE_OFFSET, _hole_offset_expression(param))

    return userParams


def _create_parameter(name: str, expression: str, comment=COMMENT, favorite: bool = False) -> adsk.fusion.UserParameter:
    parameter = userParams.itemByName(name)
    if not parameter:
        parameter = userParams.add(name, ValueInput.createByString(expression), default_length_units, comment)

    parameter.expression = expression
    parameter.comment = comment
    parameter.isFavorite = favorite

    return parameter


def _hole_offset_expression(param: DbParams) -> str:
    # TODO: use constants instead of strings
    if param.dbType == "Minimal Dogbone":
        return f"{DB_RADIUS} / sqrt(2) * (1 + {DB_MIN_PERCENT}/100)"

    if param.dbType == "Mortise Dogbone":
        return DB_RADIUS

    return f"{DB_RADIUS} / sqrt(2)"


def _min_percentage(param):
    parameter = userParams.itemByName(DB_MIN_PERCENT)
    value = param.minimalPercent

    if not parameter:
        parameter = userParams.add(DB_MIN_PERCENT, ValueInput.createByReal(value), "", "")

    parameter.value = value
    parameter.comment = ""
    parameter.isFavorite = True
