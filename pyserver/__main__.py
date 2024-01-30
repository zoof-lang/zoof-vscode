import sys
import time

sys.path.append(".")  # os.path.dirname(os.path.dirname(__file__)))

from pyserver import LanguageServer, logger


server = LanguageServer()

logger.warning("\n" + "=" * 80)
logger.warning("Starting server at " + time.strftime("%Y-%m-%d %H:%M:%S"))

server.start()

logger.warning("Stopping server")
