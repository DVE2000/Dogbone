import logging
import os

LEVELS = {
    "Notset": 0,
    "Debug": 10,
    "Info": 20,
    "Warning": 30,
    "Error": 40,
}

logger = logging.getLogger("dogbone")
formatter = logging.Formatter(
    "%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s"
)
logHandler = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "dogbone.log"), mode="w"
)
logHandler.setFormatter(formatter)
logHandler.flush()
logger.addHandler(logHandler)
