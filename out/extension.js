"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode_1 = require("vscode");
const path = require("path");
const net = require("net");
const node_1 = require("vscode-languageclient/node");
let client;
function activate(context) {
    // Whether or not to start the python server itself
    // context.workspaceState.
    const devMode = false; //workspace.getConfiguration("zoof-lang").get("some-config-option");
    let serverOptions;
    if (devMode) {
        serverOptions = () => {
            return new Promise((resolve /*, reject */) => {
                const clientSocket = new net.Socket();
                const port = 8339;
                clientSocket.connect(port, "127.0.0.1", () => {
                    resolve({
                        reader: clientSocket,
                        writer: clientSocket,
                    });
                });
            });
        };
    }
    else {
        const pythonPath = vscode_1.workspace
            .getConfiguration("python")
            .get("defaultInterpreterPath");
        if (!pythonPath) {
            throw new Error("`python.defaultInterpreterPath` is not set");
        }
        const cwd = path.join(__dirname, "..");
        serverOptions = {
            command: pythonPath,
            args: ["pyserver"],
            options: {
                cwd: cwd,
            },
            transport: node_1.TransportKind.stdio,
        };
    }
    const clientOptions = {
        documentSelector: [{ scheme: "file", language: "zoof" }],
        // synchronize: {
        //     // Notify the server about file changes to '.clientrc files contained in the workspace
        //     fileEvents: workspace.createFileSystemWatcher('**/.clientrc')
        // }
    };
    client = new node_1.LanguageClient("zoof", "Zoof", serverOptions, clientOptions);
    client.start();
}
exports.activate = activate;
function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
exports.deactivate = deactivate;
