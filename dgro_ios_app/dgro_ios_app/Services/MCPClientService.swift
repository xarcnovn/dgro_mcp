import Foundation
import MCP

@MainActor
class MCPClientService: ObservableObject {
    private var client: Client?
    private var transport: HTTPClientTransport?
    @Published var isConnected = false
    @Published var availableTools: [MCP.Tool] = []
    
    init() {
        setupClient()
    }
    
    private func setupClient() {
        client = Client(
            name: "MCPCaseSearchiOS",
            version: "1.0.0",
            configuration: .default
        )
    }
    
    func connect() async throws {
        // Parse the server URL
        guard let url = URL(string: Config.mcpServerURL) else {
            throw MCPError.invalidRequest("Invalid server URL")
        }
        
        // Create HTTP transport with streaming
        transport = HTTPClientTransport(
            endpoint: url,
            streaming: true
        )
        
        guard let client = client, let transport = transport else {
            throw MCPError.invalidRequest("Client or transport not initialized")
        }
        
        // Connect to server
        let result = try await client.connect(transport: transport)
        
        // Check capabilities
        print("Server capabilities: \(result.capabilities)")
        
        // List available tools
        let (tools, _) = try await client.listTools()
        
        await MainActor.run {
            self.availableTools = tools
            self.isConnected = true
            print("Connected with \(tools.count) tools available")
        }
    }
    
    func disconnect() async {
        guard let transport = transport else { return }
        
        await transport.disconnect()
        
        await MainActor.run {
            self.isConnected = false
            self.availableTools = []
        }
    }
    
    func callTool(name: String, arguments: [String: Any]) async throws -> (content: [ContentBlock], isError: Bool) {
        guard let client = client else {
            throw MCPError.invalidRequest("Client not connected")
        }
        
        print("Calling tool: \(name) with arguments: \(arguments)")
        
        let (content, isError) = try await client.callTool(name: name, arguments: arguments)
        
        print("Tool result: \(content)")
        
        return (content: content, isError: isError)
    }
    
    func getPrompt(name: String, arguments: [String: Any]? = nil) async throws -> (description: String?, messages: [PromptMessage]) {
        guard let client = client else {
            throw MCPError.invalidRequest("Client not connected")
        }
        
        let (description, messages) = try await client.getPrompt(name: name, arguments: arguments)
        return (description: description, messages: messages)
    }
    
    func listPrompts() async throws -> [Prompt] {
        guard let client = client else {
            throw MCPError.invalidRequest("Client not connected")
        }
        
        let (prompts, _) = try await client.listPrompts()
        return prompts
    }
}
