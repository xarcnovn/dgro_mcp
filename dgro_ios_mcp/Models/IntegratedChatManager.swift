import Foundation
import MCP

@MainActor
final class IntegratedChatManager: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var isConnected: Bool = false
    @Published var connectionStatus: String = "Disconnected"
    @Published var isProcessing: Bool = false
    
    private var mcpClient: Client?
    private var transport: HTTPClientTransport?
    private let chatGPTService = ChatGPTService()
    // Note: iOS doesn't support Process, so server must be started externally
    
    init() {
        setupInitialMessages()
    }
    
    deinit {
        // Clean up MCP client connection
        mcpClient = nil
        transport = nil
    }
    
    private func setupInitialMessages() {
        messages = [
            ChatMessage(
                text: "Hi! I'm your AI assistant with access to MCP tools. I can help you with case management, vendor searches, email communications, and more. How can I assist you today?",
                isUser: false,
                timestamp: Date()
            )
        ]
    }
    
    func startServer() async {
        connectionStatus = "Connecting to MCP server..."
        
        // Note: On iOS, we can't start the Python server directly
        // The server must be started externally (e.g., from terminal)
        
        // Connect to the externally running server
        await connectToMCPServer()
    }
    
    
    private func connectToMCPServer() async {
        do {
            connectionStatus = "Connecting to MCP server..."
            
            // Create client
            mcpClient = Client(name: "DGroMCP-iOS", version: "1.0.0")
            
            // Create HTTP transport for streamable connection
            guard let serverURL = URL(string: "http://localhost:8000/mcp") else {
                throw MCPError.invalidRequest("Invalid server URL")
            }
            
            transport = HTTPClientTransport(
                endpoint: serverURL,
                streaming: true
            )
            
            // Connect to the server
            if let client = mcpClient, let transport = transport {
                let result = try await client.connect(transport: transport)
                isConnected = true
                connectionStatus = "Connected to MCP Server"
                
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
        mcpClient = nil
        transport = nil
        isConnected = false
        connectionStatus = "Disconnected"
        
        // Note: On iOS, we don't manage the server process
    }
    
    func sendMessage(_ text: String) async {
        // Add user message
        let userMessage = ChatMessage(text: text, isUser: true, timestamp: Date())
        messages.append(userMessage)
        
        isProcessing = true
        
        do {
            // First, check if the user is asking for something that requires MCP tools
            let response = try await chatGPTService.sendMessage(text, conversationHistory: messages)
            
            // Check if the response mentions needing to use tools
            if shouldUseMCPTools(response: response, userMessage: text) {
                // Use MCP tools and get enhanced response
                let enhancedResponse = try await handleMCPToolUsage(userMessage: text, gptResponse: response)
                let botMessage = ChatMessage(text: enhancedResponse, isUser: false, timestamp: Date())
                messages.append(botMessage)
            } else {
                // Just add the ChatGPT response
                let botMessage = ChatMessage(text: response, isUser: false, timestamp: Date())
                messages.append(botMessage)
            }
            
        } catch {
            let errorMessage = ChatMessage(
                text: "I'm sorry, I encountered an error: \(error.localizedDescription)",
                isUser: false,
                timestamp: Date()
            )
            messages.append(errorMessage)
        }
        
        isProcessing = false
    }
    
    private func shouldUseMCPTools(response: String, userMessage: String) -> Bool {
        let toolKeywords = ["search", "find", "vendor", "case", "email", "offer", "contact", "scrape", "create"]
        let combinedText = (response + " " + userMessage).lowercased()
        
        return toolKeywords.contains { keyword in
            combinedText.contains(keyword)
        }
    }
    
    private func handleMCPToolUsage(userMessage: String, gptResponse: String) async throws -> String {
        guard isConnected, let client = mcpClient else {
            return gptResponse + "\n\n(Note: MCP tools are not available - server not connected)"
        }
        
        var enhancedResponse = gptResponse
        
        // If user is asking about available tools or capabilities
        if userMessage.lowercased().contains("tools") || userMessage.lowercased().contains("help") {
            do {
                let (tools, _) = try await client.listTools()
                enhancedResponse += "\n\nAvailable MCP tools:\n"
                for tool in tools {
                    let description = tool.description ?? "No description"
                    enhancedResponse += "• \(tool.name): \(description)\n"
                }
            } catch {
                enhancedResponse += "\n\n(Could not fetch available tools: \(error.localizedDescription))"
            }
        }
        
        // Example: If user wants to create a case
        if userMessage.lowercased().contains("create") && userMessage.lowercased().contains("case") {
            do {
                let arguments: [String: MCP.Value] = [
                    "subject": MCP.Value.safe("User request: \(userMessage)"),
                    "features": MCP.Value.safe("To be determined"),
                    "location": MCP.Value.safe(""),
                    "budget": MCP.Value.safe(0.0)
                ]
                
                let (content, isError) = try await client.callTool(name: "create_case", arguments: arguments)
                
                if !(isError ?? false), let textContent = content.first {
                    switch textContent {
                    case .text(let text):
                        enhancedResponse += "\n\n✅ Created case: \(text)"
                    default:
                        enhancedResponse += "\n\n✅ Case created successfully"
                    }
                }
            } catch {
                enhancedResponse += "\n\n❌ Could not create case: \(error.localizedDescription)"
            }
        }
        
        return enhancedResponse
    }
    
    // Convenience method to call specific MCP tools
    func callMCPTool(name: String, arguments: [String: Any] = [:]) async -> String {
        guard isConnected, let client = mcpClient else {
            return "MCP server not connected"
        }
        
        do {
            var mcpArgs: [String: MCP.Value] = [:]
            for (key, value) in arguments {
                mcpArgs[key] = MCP.Value.safe(value)
            }
            
            let (content, _) = try await client.callTool(name: name, arguments: mcpArgs)
            
            var result = ""
            for item in content {
                switch item {
                case .text(let text):
                    result += text + "\n"
                case .image(_, let mimeType, _):
                    result += "[Image: \(mimeType)]\n"
                case .audio(_, let mimeType):
                    result += "[Audio: \(mimeType)]\n"
                case .resource(let uri, let mimeType, let text):
                    result += "[Resource: \(uri) (\(mimeType))]\n"
                    if let text = text {
                        result += text + "\n"
                    }
                }
            }
            
            return result.trimmingCharacters(in: .whitespacesAndNewlines)
            
        } catch {
            return "Tool execution error: \(error.localizedDescription)"
        }
    }
}

