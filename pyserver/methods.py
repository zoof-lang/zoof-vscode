from .server import register_method
from .utils import logger, print
from .conv import itemkind2int


@register_method
async def textDocument_didOpen(server, params):
    return None  # This is a notification


@register_method
async def textDocument_didChange(server, params):
    return None  # This is a notification


@register_method
async def textDocument_didClose(server, params):
    return None  # This is a notification


@register_method
async def textDocument_completion(server, params):
    items = []
    for name in [
        "print",
        "import",
        "from",
        "as",
        # "and",  these are not really keywords
        # "or",
        # "true",
        # "false",
        # "nil",
        "abstract",
        "trait",
        "struct",
        "impl",
        "func",
        "proc",
        "getter",
        "setter",
        "method",
        "return",
        "if",
        "elif",
        "elseif",
        "else",
        "then",
        "for",
        "in",
        "while",
        "do",
        "its",
        "break",
        "continue",
    ]:
        item = {
            "label": name,
            "kind": itemkind2int("Keyword"),
            "detail": "extra details",
        }
        items.append(item)
    result = {
        "isIncomplete": False,
        "items": items,
    }
    return result
