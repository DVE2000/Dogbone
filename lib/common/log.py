import logging
import os
from ..classes import basePath

LEVELS = {
    "Notset": 0,
    "Debug": 10,
    "Info": 20,
    "Warning": 30,
    "Error": 40,
}

def startLogger():
    logger = logging.getLogger("dogbone")
    formatter = logging.Formatter(
        "%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s"
    )
    logHandler = logging.FileHandler(
        os.path.join(basePath, "dogbone.log"), mode="w"
    )
    logHandler.setFormatter(formatter)
    logHandler.flush()
    logger.addHandler(logHandler)
    return logger

def stopLogger():
    logger = logging.getLogger("dogbone")
    for handler in logger.handlers:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)