import Foundation
import Combine
import MCP

@MainActor
final class MCPClientManager: ObservableObject {
    @Published var isConnected: Bool = false
    @Published var statusMessage: String = "Disconnected"

    private var client: Client?

    func connect(endpoint: String = "http://127.0.0.1:8765/mcp") async {
        guard let url = URL(string: endpoint) else {
            statusMessage = "Invalid endpoint URL"
            return
        }

        // If already connected, skip
        if isConnected { return }

        let client = Client(name: "DGro iOS", version: "1.0.0")
        self.client = client

        let transport = HTTPClientTransport(endpoint: url, streaming: true)

        do {
            _ = try await client.connect(transport: transport)
            isConnected = true
            statusMessage = "Connected to MCP at \(url.absoluteString)"
        } catch {
            isConnected = false
            statusMessage = "Failed to connect: \(error.localizedDescription)"
        }
    }

    func disconnect() async {
        guard client != nil else { return }
        isConnected = false
        statusMessage = "Disconnected"
        self.client = nil
    }
}


