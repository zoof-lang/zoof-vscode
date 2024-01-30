import sys
import json
import asyncio
import threading

from .utils import logger, print


__version__ = "0.0.1"


# == The io thread and server


class IOThread(threading.Thread):
    """To read from stdin and feed the result into the main threads event loop."""

    def __init__(self, loop, dispatch_func):
        super().__init__()
        self._loop = loop  # in main thread
        self._dispatch_func = dispatch_func
        self.daemon = True

    def run(self):
        logger.info("io thread started")
        content_length = 0
        rfile = sys.stdin.buffer  # binary file io
        try:
            while True:
                line = rfile.readline().decode()
                if not line:
                    break  # stdin is closed
                elif not line.strip():
                    # Header is done, we can read the content
                    if content_length > 0:
                        self.send_content(rfile.read(content_length).decode())
                        content_length = 0
                    else:
                        logger.error(f"Got a message with Content-Length zero")
                elif line.startswith("Content-Length:"):
                    try:
                        content_length = int(line.split(":")[-1].strip())
                    except Exception:
                        logger.error(f"Could not parse Content-Length: {line.strip()}")
                elif line.startswith("Content-Type:"):
                    if line.strip() != "application/vscode-jsonrpc; charset=utf-8":
                        logger.warning(f"Unexpected Content-Type: {line.strip()}")
                else:
                    logger.warning(f"Ignoring incoming line: {line.strip()}")
        except Exception as err:
            logger.error(f"io thread errored: {str(err)}")
        else:
            logger.info("io thread stopped")

    def send_content(self, content):
        """Method, called from this thread, to convert the content to a dict and send it to the main thread."""
        try:
            d = json.loads(content)
        except Exception:
            logger.error("Could not convert content to JSON")
        else:
            self._loop.call_soon_threadsafe(self._dispatch_func, d)


class LanguageServer:
    """The language server object."""

    def __init__(self):
        self._thread = None
        self.shut_down = False

    def start(self):
        self._loop = asyncio.get_event_loop()
        self._thread = IOThread(self._loop, self._dispatch)
        self._thread.start()
        logger.info("Entering main loop")
        self._loop.run_forever()
        logger.info("Main loop ended")

    def _dispatch(self, request):
        task = self._loop.create_task(self.handle_request(request))

    async def handle_request(self, d):
        await asyncio.sleep(0.1)

        id = d.get("id", None)
        method_name = d.get("method", "no_method_name").replace("/", "_")
        params = d.get("params", None)

        logger.info(("Request" if id else "Notification") + " for " + method_name)
        method = method_functions.get(method_name, None)
        try:
            result = await method(self, params)
            # todo:  **params / *params (depending on whether params is a list or dict)
        except Exception as err:
            # client cancelled: -32800
            # server cancelled: -32802
            # content modified: -32801
            error_msg = str(err)
            error_code = -32603  # internal error
            if method is None:
                error_code = -32601
                error_msg = f"Method not implemented: {method_name}"

            response = {
                "jsonrpc": "2.0",
                "id": id,
                "error": {
                    "code": error_code,
                    "message": error_msg,
                    "data": None,
                },
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": id,
                "result": result,
            }

        # If this is a notification, we should not send a response
        if id is None:
            if response.get("error"):
                logger.info(f"Error in notification: {response['error']['message']}")
            else:
                logger.info("Notification done.")
            return

        # Prepare the response bytes
        try:
            text = json.dumps(response)
        except Exception:
            response = {
                "jsonrpc": "2.0",
                "id": id,
                "error": {
                    "code": -32603,
                    "message": "failed to json-encode the response",
                },
            }
            text = json.dumps(response)
        bb = text.encode()

        # Send the response
        wfile = sys.stdout.buffer  # binary io
        wfile.write(f"Content-Length: {len(bb)}\r\n".encode())
        wfile.write(b"\r\n")
        wfile.write(bb)
        wfile.flush()

        # Log
        if response.get("error"):
            logger.info(f"Wrote result error: {response['error']['message']}")
        else:
            logger.info("Wrote result")


# == For registering methods


method_functions = {}


def register_method(func):
    """Decorator"""
    assert asyncio.iscoroutinefunction(func)
    method_functions[func.__name__] = func


# == Builtin methods


@register_method
async def initialize(server, params):
    logger.info(
        f"Initializing with {params['clientInfo']['name']} {params['clientInfo'].get('version', '')}"
    )

    # Store some stuff
    server.client_capabilities = params["capabilities"]
    server.initialization_options = params.get("initializationOptions", None)
    server.workspace_folders = params.get("workspaceFolders", [])

    # Create result
    server_capabilities = {
        "textDocumentSync": {
            "openClose": True,
            "change": 1,  # 1 means send full doc, 2 means incremental changes
        },
        "completionProvider": {
            "triggerCharacters": ["."],
            "resolveProvider": False,  # can be true if we can provide additional info on items
            "completionItem": {},
        },
        # "semanticTokensProvider": {},
        # "documentFormattingProvider": {},
        # "documentRangeFormattingProvider": {},
        # "documentOnTypeFormattingProvider": {},
        # "executeCommandProvider": {}  ?? whats thos
        # "inlineValueProvider": {}  !!
    }

    result = {
        "capabilities": server_capabilities,
        "serverInfo": {
            "name": "Zoof lsp",
            "version": __version__,
        },
    }
    return result


@register_method
async def initialized(server, params):
    logger.info("Ininialization comfirmed by client!")
    return None  # This is a notification


@register_method
async def shutdown(server, params):
    logger.info("Server shutdown requested")
    server.shut_down = True
    # Now wait for exit
    return {}  # This is a request


@register_method
async def exit(server, params):
    logger.info("Server exit requested")
    server._loop.stop()
    return None  # This is a notification
