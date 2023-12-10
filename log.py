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
[logger.removeHandler(h) for h in logger.handlers]  #make sure there are no residual handlers from last run

formatter = logging.Formatter(
    "%(asctime)s ; %(name)s ; %(levelname)s ; %(lineno)d; %(message)s"
)
logHandler = logging.handlers.RotatingFileHandler(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dogbone.log"), mode="a", backupCount=3, maxBytes = 526000
)
logHandler.setFormatter(formatter)
logHandler.flush()
logger.addHandler(logHandler)
logger.handlers[0].doRollover()