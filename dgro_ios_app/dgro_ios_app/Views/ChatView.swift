import SwiftUI
import MCP

struct ChatView: View {
    @StateObject private var mcpClient = MCPClientService()
    @State private var anthropicService: AnthropicService?
    @State private var messages: [ChatMessage] = []
    @State private var anthropicMessages: [Request.Message] = []
    @State private var inputText = ""
    @State private var isProcessing = false
    @State private var showError = false
    @State private var errorMessage = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "message.badge.filled.fill")
                    .font(.title2)
                    .foregroundColor(.blue)
                Text("Case Search Assistant")
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(mcpClient.isConnected ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(mcpClient.isConnected ? "Connected" : "Disconnected")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding()
            .background(Color(.systemBackground))
            .shadow(radius: 1)
            
            // Messages list
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        if messages.isEmpty {
                            Text("Ask me about cases, vendors, or offers...")
                                .foregroundColor(.secondary)
                                .padding()
                                .frame(maxWidth: .infinity)
                        } else {
                            ForEach(messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                        }
                    }
                    .padding()
                    .onChange(of: messages.count) {
                        withAnimation {
                            proxy.scrollTo(messages.last?.id, anchor: .bottom)
                        }
                    }
                }
            }
            
            // Input field
            HStack(spacing: 12) {
                TextField("Ask about cases, vendors, or offers...", text: $inputText)
                    .textFieldStyle(.roundedBorder)
                    .disabled(isProcessing || !mcpClient.isConnected)
                    .onSubmit {
                        sendMessage()
                    }
                
                Button(action: sendMessage) {
                    Image(systemName: isProcessing ? "ellipsis.circle" : "paperplane.fill")
                        .foregroundColor(inputText.isEmpty || isProcessing ? .gray : .blue)
                }
                .disabled(inputText.isEmpty || isProcessing || !mcpClient.isConnected)
                .animation(.easeInOut, value: isProcessing)
            }
            .padding()
            .background(Color(.secondarySystemBackground))
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(errorMessage)
        }
        .task {
            await connectToServer()
        }
    }
    
    private func connectToServer() async {
        do {
            try await mcpClient.connect()
            
            // Initialize Anthropic service with MCP tools
            let tools = mcpClient.availableTools.map { mcpTool in
                Tool(
                    name: mcpTool.name,
                    description: mcpTool.description,
                    input_schema: convertToAnyCodable(mcpTool.inputSchema)
                )
            }
            
            anthropicService = AnthropicService(
                apiKey: Config.anthropicAPIKey,
                tools: tools
            )
            
            // Check if we have the system prompt
            do {
                let prompts = try await mcpClient.listPrompts()
                if prompts.contains(where: { $0.name == "system_prompt" }) {
                    let (description, messages) = try await mcpClient.getPrompt(name: "system_prompt")
                    
                    // Add system prompt as first message
                    if let firstMessage = messages.first,
                       case .text(let text) = firstMessage.content {
                        await MainActor.run {
                            self.messages.append(ChatMessage(role: .system, content: "System initialized with multi-agent capabilities"))
                        }
                        
                        // Add system context to Anthropic messages
                        anthropicMessages.append(Request.Message(
                            role: .user,
                            content: [Content(type: "text", text: "System: \(text)", name: nil, input: nil, id: nil, tool_use_id: nil)]
                        ))
                        anthropicMessages.append(Request.Message(
                            role: .assistant,
                            content: [Content(type: "text", text: "I understand. I'm ready to help you find the best offers for products or services using the multi-agent system.", name: nil, input: nil, id: nil, tool_use_id: nil)]
                        ))
                    }
                }
            } catch {
                print("Could not get system prompt: \(error)")
            }
            
        } catch {
            await MainActor.run {
                errorMessage = "Failed to connect: \(error.localizedDescription)"
                showError = true
            }
        }
    }
    
    private func sendMessage() {
        let text = inputText
        inputText = ""
        
        Task {
            await processUserMessage(text)
        }
    }
    
    private func processUserMessage(_ text: String) async {
        guard !text.isEmpty else { return }
        
        // Add user message to UI
        let userMessage = ChatMessage(role: .user, content: text)
        await MainActor.run {
            messages.append(userMessage)
        }
        
        // Add to Anthropic messages format
        anthropicMessages.append(Request.Message(
            role: .user,
            content: [Content(type: "text", text: text, name: nil, input: nil, id: nil, tool_use_id: nil)]
        ))
        
        await MainActor.run {
            isProcessing = true
        }
        defer {
            Task { @MainActor in
                isProcessing = false
            }
        }
        
        // Send to Claude
        do {
            guard let service = anthropicService else {
                throw AnthropicError.httpError(statusCode: 0)
            }
            let response = try await service.send(messages: anthropicMessages)
            
            // Process response and handle tool calls
            await processClaudeResponse(response)
        } catch {
            await MainActor.run {
                messages.append(ChatMessage(
                    role: .assistant,
                    content: "Error: \(error.localizedDescription)"
                ))
            }
        }
    }
    
    private func processClaudeResponse(_ response: Response) async {
        var assistantContent: [Content] = []
        var hasToolUse = false
        
        for content in response.content {
            if content.type == "text" {
                // Add text to UI
                if let text = content.text {
                    await MainActor.run {
                        messages.append(ChatMessage(role: .assistant, content: text))
                    }
                    assistantContent.append(content)
                }
            } else if content.type == "tool_use" {
                hasToolUse = true
                // Execute tool via MCP
                if let toolName = content.name,
                   let toolInput = convertFromAnyCodable(content.input) {
                    
                    assistantContent.append(content)
                    
                    do {
                        let (resultContent, isError) = try await mcpClient.callTool(
                            name: toolName,
                            arguments: toolInput
                        )
                        
                        // Show tool execution in UI
                        await MainActor.run {
                            messages.append(ChatMessage(
                                role: .system,
                                content: "🔧 Executed: \(toolName)"
                            ))
                        }
                        
                        // Add assistant message with tool use to messages
                        anthropicMessages.append(Request.Message(
                            role: .assistant,
                            content: assistantContent
                        ))
                        
                        // Add tool result as user message
                        let toolResultText = resultContent.compactMap { item in
                            if case .text(let text) = item {
                                return text
                            }
                            return nil
                        }.joined(separator: "\n")
                        
                        anthropicMessages.append(Request.Message(
                            role: .user,
                            content: [Content(
                                type: "tool_result",
                                text: toolResultText,
                                name: nil,
                                input: nil,
                                id: nil,
                                tool_use_id: content.id
                            )]
                        ))
                        
                        // Continue conversation
                        await continueConversation()
                        
                    } catch {
                        await MainActor.run {
                            messages.append(ChatMessage(
                                role: .system,
                                content: "❌ Tool error: \(error.localizedDescription)"
                            ))
                        }
                        
                        // Add error result to continue
                        anthropicMessages.append(Request.Message(
                            role: .assistant,
                            content: assistantContent
                        ))
                        
                        anthropicMessages.append(Request.Message(
                            role: .user,
                            content: [Content(
                                type: "tool_result",
                                text: "Error: \(error.localizedDescription)",
                                name: nil,
                                input: nil,
                                id: nil,
                                tool_use_id: content.id
                            )]
                        ))
                        
                        await continueConversation()
                    }
                }
            }
        }
        
        // If we only got text (no tool calls), add to anthropic messages
        if !hasToolUse && !assistantContent.isEmpty {
            anthropicMessages.append(Request.Message(
                role: .assistant,
                content: assistantContent
            ))
        }
    }
    
    private func continueConversation() async {
        // Send continuation to Claude with tool results
        do {
            guard let service = anthropicService else { return }
            let response = try await service.send(messages: anthropicMessages)
            await processClaudeResponse(response)
        } catch {
            await MainActor.run {
                messages.append(ChatMessage(
                    role: .assistant,
                    content: "Error continuing conversation: \(error.localizedDescription)"
                ))
            }
        }
    }
    
    // Helper function to convert MCP types to AnyCodable
    private func convertToAnyCodable(_ value: Any?) -> [String: AnyCodable]? {
        guard let value = value else { return nil }
        
        if let dict = value as? [String: Any] {
            return dict.mapValues { AnyCodable($0) }
        }
        
        return nil
    }
    
    // Helper function to convert from AnyCodable to [String: Any]
    private func convertFromAnyCodable(_ value: [String: AnyCodable]?) -> [String: Any]? {
        guard let value = value else { return nil }
        return value.mapValues { $0.value }
    }
}
