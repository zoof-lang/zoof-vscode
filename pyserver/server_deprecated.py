"""
Run a language server, to provide autocompletion and diagnostics in vs-code.

"""

import os
import sys
import glob
import time
import logging
import argparse
import asyncio

# import rich.text

from pygls.server import LanguageServer
from lsprotocol import types

# TODO: replace hard-coded import with requirement to install zoofc1
sys.path.append("/Users/almar/dev/zf/zoof-boot")
import zoofc1
from zoofc1 import ZoofCompiler


logger = logging.getLogger("zoof-lsp")


##


class DataBase:
    def __init__(self):
        self._files = {}

    async def validate(self, ls: LanguageServer, uri, delay):
        try:
            file = self._files[uri]
        except KeyError:
            file = File(uri.removeprefix("file://"))
            self._files[uri] = file
        await file.validate(ls, delay)

    async def close_file(self, uri):
        file = self._files.pop(uri, None)
        if file is not None:
            await file._close()


class File:
    def __init__(self, filename):
        self.filename = filename
        self.references = {}

        self._validation_task = None

    async def _close(self):
        await self.stop_validation()

    async def validate(self, ls: LanguageServer, delay=0):
        """Validate source code by parsing the source.

        This is time consuming cpu bound work.
        """

        # Debounce!
        logger.info("validate! (might debounce)")
        await self.stop_validation()

        text_doc = ls.workspace.get_text_document(self.filename)
        code = text_doc.source

        # Spawn a long running validation task:
        self._validation_task = asyncio.create_task(self._validate_wrapper(code, delay))

    async def _validate_wrapper(self, code, delay):
        if delay:
            logger.info(f"Waiting {delay} seconds for additional changes")
            await asyncio.sleep(delay)
        logger.info("Start compilation!")

        # tokens = await ls.loop.run_in_executor(None, _cpu_validate, filename, code)
        await self._validate(code)

        self._validation_task = None

    async def stop_validation(self):
        if self._validation_task and not self._validation_task.done():
            logger.info("Cancelling validation task")
            self._validation_task.cancel()
            try:
                await self._validation_task
            except asyncio.CancelledError:
                logger.info("task cancelled")

    async def _validate(self, code):
        # todo: prevent duplicate work (parse also tokenizes (again))

        source = zoofc1.Source("", code, 1)
        m = compiler.createModule(self.filename)
        tokens = m.tokenize(source)  # cannot fail
        # m.parse(code)  # Can raise errors

        # Store results
        self.tokens = tokens

    def get_definition(self, filename: str, position):
        """Given a cursor, try to jump to definition."""
        key = (filename, position.row)
        if key in self._references:
            spots = self._references[key]
            for loc, def_id in spots:
                if loc.begin.column <= position.column <= loc.end.column:
                    key = str(def_id)
                    if key in db._definitions:
                        filename, loc = db._definitions[key]
                        return filename, loc
                    break


# class ScopeCrawler(ast.AstVisitor):
#     def __init__(self):
#         super().__init__()
#         self.scope_stack = []

#     def visit_module(self, module):
#         logger.debug(f"Filling scopes for {module.name}")
#         self.enter_scope(module.scope)
#         super().visit_module(module)
#         return self.leave_scope()

#     def visit_definition(self, definition):
#         if isinstance(definition, ast.ScopedDefinition):
#             self.enter_scope(definition.scope)
#         super().visit_definition(definition)
#         if isinstance(definition, ast.ScopedDefinition):
#             self.leave_scope()

#     def visit_block(self, block):
#         self.enter_scope(block.scope)
#         super().visit_block(block)
#         self.leave_scope()

#     def enter_scope(self, scope):
#         # logger.debug(f"Enter scope {scope.span}")
#         item = ScopeTreeItem(scope)
#         if self.scope_stack:
#             self.scope_stack[-1].add_sub_scope(item)
#         self.scope_stack.append(item)

#     def leave_scope(self):
#         # logger.debug("Leave scope")
#         return self.scope_stack.pop()


# class ScopeTreeItem:
#     """A single scope level."""

#     def __init__(self, scope):
#         self.scope = scope
#         self._m = RangeMap()

#     def add_sub_scope(self, s: "ScopeTreeItem"):
#         self._m.insert(s.scope.span.begin.row, s.scope.span.end.row, s)

#     def get_definitions_for_line(self, row):
#         definitions = []
#         definitions.extend(list(self.scope.symbols.values()))
#         sub_item = self._m.get(row)
#         if sub_item:
#             definitions.extend(sub_item.get_definitions_for_line(row))
#         return definitions


# class RangeMap:
#     """A class mapping from"""

#     def __init__(self):
#         self._ranges = []

#     def insert(self, key_begin, key_end, value):
#         self._ranges.append((key_begin, key_end, value))

#     def get(self, key):
#         # TODO: replace linear scan with
#         # a sorted heap
#         for begin, end, value in self._ranges:
#             if begin <= key < end:
#                 return value


# def module_to_scope_tree(module) -> "ScopeTreeItem":
#     """Create a tree of scopes"""
#     logger.info(f"Create scope tree for {module.name}")
#     crawler = ScopeCrawler()
#     return crawler.visit_module(module)


########################################################

db = DataBase()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
server = LanguageServer("Zoof-Server", "v0.1", loop=loop)
compiler = ZoofCompiler()


########################################################


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams):
    await db.validate(ls, params.text_document.uri, delay=0)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams):
    await db.validate(ls, params.text_document.uri, delay=1)


@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
async def did_close(ls: LanguageServer, params: types.DidOpenTextDocumentParams):
    uri = params.text_document.uri
    db.close_file(uri)
    ls.publish_diagnostics(uri, [])


# This would allow (I think) highlighting by the language server, which is nice, because we have the tokens
# so we can avoid duplicate maintenance / work. However, looks like pygls does not support it yet.
# server.feature(types.text_document_SEMANTIC_TOKENS_FULL)


@server.feature(types.TEXT_DOCUMENT_COMPLETION)
def completions(
    ls: LanguageServer, params: types.CompletionParams
) -> types.CompletionList:
    text_doc = ls.workspace.get_text_document(params.text_document.uri)
    filename = text_doc.uri.removeprefix("file://")
    row = params.position.line + 1

    items = [
        types.CompletionItem(label=kw, kind=types.CompletionItemKind.Keyword)
        for kw in zoofc1.tokens.KEYWORDS
    ]
    return types.CompletionList(is_incomplete=False, items=items)

    # print("Document", document)
    # current_line = document.lines[params.position.line].strip()
    items = []

    if filename in db._file_scopes:
        # Get all accessible definitions from the scope tree
        scope_tree = db._file_scopes[filename]
        # if current_line.endswith("hello."):
        # module = db._file_modules[filename]
        for definition in scope_tree.get_definitions_for_line(row):
            items.append(definition_to_completion_item(definition))

    return types.CompletionList(is_incomplete=False, items=items)


def definition_to_completion_item(definition):
    return types.CompletionItem(
        label=definition.id.name, kind=get_completion_item_type(definition)
    )


def get_completion_item_type(definition):
    if isinstance(definition, ast.FunctionDef):
        kind = types.CompletionItemKind.Function
    elif isinstance(definition, ast.EnumDef):
        kind = types.CompletionItemKind.Enum
    elif isinstance(definition, ast.StructDef):
        kind = types.CompletionItemKind.Struct
    elif isinstance(definition, ast.ClassDef):
        kind = types.CompletionItemKind.Class
    elif isinstance(definition, ast.VarDef):
        kind = types.CompletionItemKind.Variable
    else:
        kind = types.CompletionItemKind.Variable
    return kind


# @server.feature(types.TEXT_DOCUMENT_INLAY_HINT)
# def inlay_hints(params: types.InlayHintParams):
#     print("GET INLAY HINTS", params)
#     items = []
#     for row in range(params.range.start.line, params.range.end.line):
#         items.append(
#             types.InlayHint(
#                 label="W))T",
#                 kind=types.InlayHintKind.Type,
#                 padding_left=False,
#                 padding_right=True,
#                 position=types.Position(line=row, character=0),
#             )
#         )
#     return items


# @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
# def document_symbols(params: types.DocumentSymbolParams):
#     document_uri = params.text_document.uri
#     filename = document_uri.removeprefix("file://")
#     symbols = []
#     if filename in db._file_modules:
#         module = db._file_modules[filename]
#         for definition in module.definitions:
#             symbols.append(definition_to_symbol(definition))
#     return symbols


def definition_to_symbol(definition):
    children = None
    kind = types.SymbolKind.Null
    if isinstance(definition, ast.ClassDef):
        kind = types.SymbolKind.Class
        children = []
        for subdef in definition.members:
            children.append(definition_to_symbol(subdef))
    elif isinstance(definition, ast.StructDef):
        kind = types.SymbolKind.Struct
        children = []
        for field in definition.fields:
            children.append(definition_to_symbol(field))
    elif isinstance(definition, ast.StructFieldDef):
        kind = types.SymbolKind.Field
    elif isinstance(definition, ast.FunctionDef):
        kind = types.SymbolKind.Function
    elif isinstance(definition, ast.EnumDef):
        kind = types.SymbolKind.Enum
        children = []
        for field in definition.variants:
            children.append(definition_to_symbol(field))
    elif isinstance(definition, ast.EnumVariant):
        kind = types.SymbolKind.EnumMember
    elif isinstance(definition, ast.VarDef):
        kind = types.SymbolKind.Variable

    range = make_lsp_range(definition.location)
    return types.DocumentSymbol(
        name=definition.id.name,
        kind=kind,
        range=range,
        selection_range=range,
        children=children,
    )


# @server.feature(types.TEXT_DOCUMENT_DEFINITION)
# def definition(ls: LanguageServer, params: types.DefinitionParams):
#     text_doc = ls.workspace.get_text_document(params.text_document.uri)
#     filename = text_doc.uri.removeprefix("file://")
#     row = params.position.line + 1
#     column = params.position.character + 1
#     pos = db.get_definition(filename, SlangPosition(row, column))
#     if pos:
#         filename, loc = pos
#         loc2 = types.Location(uri=f"file://{filename}", range=make_lsp_range(loc))
#         return loc2


def make_lsp_range(location) -> types.Range:
    return types.Range(
        make_lsp_position(location.begin), end=make_lsp_position(location.end)
    )


def make_lsp_position(location) -> types.Position:
    return types.Position(location.row - 1, location.column - 1)


##


def main():
    parser = argparse.ArgumentParser(description="Language server for Zoof.")
    parser.add_argument("--port", type=int, default=8339)
    parser.add_argument("--tcp", help="Start a TCP server", action="store_true")
    parser.add_argument(
        "--stdio", help="Start a STDIO server (default)", action="store_true"
    )
    args = parser.parse_args()

    if True:  # args.tcp:
        logging.getLogger("pygls.protocol").setLevel(logging.WARNING)
        logging.getLogger("namebinding").setLevel(logging.INFO)
        logging.getLogger("parser").setLevel(logging.INFO)
        logging.getLogger("basepass").setLevel(logging.INFO)
        logformat = "%(asctime)s | %(levelname)8s | %(name)10.10s | %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=logformat)
        server.start_tcp("127.0.0.1", args.port)
    else:
        server.start_io()


main()
