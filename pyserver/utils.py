import socket
import logging

logger = logging.getLogger("simple_lsp")
logger.setLevel(logging.INFO)


class UDPHandler(logging.Handler):
    udp_address = ("127.0.0.1", 12012)

    def __init__(self):
        super().__init__()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def emit(self, record):
        msg = self.format(record)
        bb = msg.encode()
        size = 2**10
        while bb:
            bb1 = bb[:size]
            bb = bb[size:]
            self._socket.sendto(bb1, self.udp_address)


for handler in logging.root.handlers:
    logging.root.removeHandler(handler)
logging.root.addHandler(UDPHandler())


def print(*args, sep=" ", end="\n"):
    """A variant of print that end up in the logger. Pretty-prints dicts."""
    parts = []
    for arg in args:
        if isinstance(arg, dict):
            arg = json.dumps(arg, indent=4)
        elif not isinstance(arg, str):
            arg = str(arg)
        parts.append(arg)
    msg = (sep.join(parts) + end).rstrip()
    logger.info(msg)
