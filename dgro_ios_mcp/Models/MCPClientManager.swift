import Foundation
import MCP

@MainActor
final class MCPClientManager: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var isConnected: Bool = false
    @Published var connectionStatus: String = "Disconnected"
    
    private var client: Client?
    private var transport: HTTPClientTransport?
    
    init() {
        setupInitialMessages()
    }
    
    private func setupInitialMessages() {
        messages = [
            ChatMessage(text: "Hi! I'm your MCP-powered agent. How can I help you today?", isUser: false, timestamp: Date())
        ]
    }
    
    func connect() async {
        do {
            connectionStatus = "Connecting..."
            
            // Create client
            client = Client(name: "DGroMCP-iOS", version: "1.0.0")
            
            // Create HTTP transport for streamable connection
            // FastMCP with streamable-http transport runs on port 8000 by default with /mcp endpoint
            guard let serverURL = URL(string: "http://localhost:8000/mcp") else {
                throw MCPError.invalidRequest("Invalid server URL")
            }
            
            transport = HTTPClientTransport(
                endpoint: serverURL,
                streaming: true
            )
            
            // Connect to the server
            if let client = client, let transport = transport {
                let result = try await client.connect(transport: transport)
                isConnected = true
                connectionStatus = "Connected to MCP Server"
                
                // Log available capabilities
                print("Connected to MCP server with capabilities:")
                if result.capabilities.tools != nil {
                    print("- Tools supported")
                }
                if result.capabilities.resources != nil {
                    print("- Resources supported")
                }
                if result.capabilities.prompts != nil {
                    print("- Prompts supported")
                }
            }
            
        } catch {
            isConnected = false
            connectionStatus = "Connection failed: \(error.localizedDescription)"
            print("MCP connection error: \(error)")
        }
    }
    
    func disconnect() async {
        client = nil
        transport = nil
        isConnected = false
        connectionStatus = "Disconnected"
    }
    
    func sendMessage(_ text: String) async {
        // Add user message
        let userMessage = ChatMessage(text: text, isUser: true, timestamp: Date())
        messages.append(userMessage)
        
        guard isConnected, let client = client else {
            // If not connected, show error message
            let errorMessage = ChatMessage(
                text: "Not connected to MCP server. Please check connection.",
                isUser: false,
                timestamp: Date()
            )
            messages.append(errorMessage)
            return
        }
        
        do {
            // For now, let's try to list available tools and show them
            let (tools, _) = try await client.listTools()
            
            var responseText = "Available MCP tools:\n"
            for tool in tools {
                let description = tool.description
                responseText += "• \(tool.name): \(description)\n"
            }
            
            if tools.isEmpty {
                responseText = "No tools available from the MCP server."
            }
            
            let botMessage = ChatMessage(text: responseText, isUser: false, timestamp: Date())
            messages.append(botMessage)
            
        } catch {
            let errorMessage = ChatMessage(
                text: "Error communicating with MCP server: \(error.localizedDescription)",
                isUser: false,
                timestamp: Date()
            )
            messages.append(errorMessage)
        }
    }
    
    func callTool(name: String, arguments: [String: Any] = [:]) async {
        guard isConnected, let client = client else {
            let errorMessage = ChatMessage(
                text: "Not connected to MCP server.",
                isUser: false,
                timestamp: Date()
            )
            messages.append(errorMessage)
            return
        }
        
        do {
            // Convert arguments to MCP Value format
            var mcpArgs: [String: MCP.Value] = [:]
            for (key, value) in arguments {
                mcpArgs[key] = MCP.Value.safe(value)
            }
            
            let (content, isError) = try await client.callTool(name: name, arguments: mcpArgs)
            
            var responseText = ""
            for item in content {
                switch item {
                case .text(let text):
                    responseText += text + "\n"
                case .image(_, let mimeType, _):
                    responseText += "[Image: \(mimeType)]\n"
                case .audio(_, let mimeType):
                    responseText += "[Audio: \(mimeType)]\n"
                case .resource(let uri, let mimeType, let text):
                    responseText += "[Resource: \(uri) (\(mimeType))]\n"
                    if let text = text {
                        responseText += text + "\n"
                    }
                }
            }
            
            if responseText.isEmpty {
                responseText = (isError ?? false) ? "Tool execution failed" : "Tool executed successfully"
            }
            
            let message = ChatMessage(
                text: responseText.trimmingCharacters(in: .whitespacesAndNewlines),
                isUser: false,
                timestamp: Date()
            )
            messages.append(message)
            
        } catch {
            let errorMessage = ChatMessage(
                text: "Tool execution error: \(error.localizedDescription)",
                isUser: false,
                timestamp: Date()
            )
            messages.append(errorMessage)
        }
    }
}
