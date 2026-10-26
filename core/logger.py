import logging

logLevel = logging.WARNING
logger = logging.getLogger(__name__)
logger.setLevel(logLevel)

# File handler (mode='w' to clear old logs on restart)
file_handler = logging.FileHandler('econsim.log', mode='w')
file_handler.setLevel(logLevel)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add handlers to the logger
logger.addHandler(file_handler)

# Example
def logInit():
    pass


def logdebug(*args):
    msg = ' '.join(map(str, args))
    logger.debug(msg)

def logwarning(*args):
    msg = ' '.join(map(str, args))
    logger.warning(msg)

def loginfo(*args):
    msg = ' '.join(map(str, args))
    logger.info(msg)

def logerror(*args):
    msg = ' '.join(map(str, args))
    logger.error(msg)
