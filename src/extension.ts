import { ExtensionContext, workspace } from "vscode";
import * as path from "path";
import * as net from "net";
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient;

export function activate(context: ExtensionContext) {
    // Whether or not to start the python server itself

    // context.workspaceState.
    const devMode: boolean = false;  //workspace.getConfiguration("zoof-lang").get("some-config-option");

    let serverOptions: ServerOptions;
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
    } else {
        const pythonPath = workspace
            .getConfiguration("python")
            .get<string>("defaultInterpreterPath");
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
            transport: TransportKind.stdio,
        };
    }

    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: "zoof" }],
        // synchronize: {
        //     // Notify the server about file changes to '.clientrc files contained in the workspace
        //     fileEvents: workspace.createFileSystemWatcher('**/.clientrc')
        // }
    };

    client = new LanguageClient(
        "zoof",
        "Zoof",
        serverOptions,
        clientOptions
    );

    client.start();
}

export function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
