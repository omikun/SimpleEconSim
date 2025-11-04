import logging

logLevel = logging.ERROR
logging.basicConfig(level=logLevel)
logger = logging.getLogger(__name__)

# File handler
file_handler = logging.FileHandler('econsim.log')
file_handler.setLevel(logLevel)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logLevel)
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Example
def logInit():
    pass


def logdebug(*args):
    msg = ' '.join(map(str, args))
    logger.warning(msg)

def logwarning(*args):
    msg = ' '.join(map(str, args))
    logger.warning(msg)

def loginfo(*args):
    msg = ' '.join(map(str, args))
    logger.info(msg)

def logerror(*args):
    msg = ' '.join(map(str, args))
    logger.error(msg)
