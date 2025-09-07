import Foundation
import Combine
import MCP

@MainActor
final class MCPClientManager: ObservableObject {
    @Published var isConnected: Bool = false
    @Published var statusMessage: String = "Disconnected"

    private var client: Client?
    // Minimal DTO used for OpenAI request body (avoid SDK types here)
    private struct ChatMessageDTO: Encodable { let role: String; let content: String }
    private var openAIKey: String? {
        // Prefer Info.plist, fall back to env for dev
        if let key = Bundle.main.object(forInfoDictionaryKey: "OpenAI_API_Key") as? String, !key.isEmpty {
            return key
        }
        return ProcessInfo.processInfo.environment["OPENAI_API_KEY"]
    }
    private var openAIModel: String {
        if let model = Bundle.main.object(forInfoDictionaryKey: "OpenAI_Model") as? String, !model.isEmpty {
            return model
        }
        return "gpt-5"
    }

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

            // Register sampling handler so the server can request LLM completions via this client
            await client.withSamplingHandler { [weak self] parameters async throws in
                guard let self else {
                    return await CreateSamplingMessage.Result(
                        model: self?.openAIModel ?? "gpt-5",
                        stopReason: .endTurn,
                        role: .assistant,
                        content: .text("Client unavailable")
                    )
                }

                // Build chat sequence for OpenAI
                var chat: [ChatMessageDTO] = []
                if let sys = parameters.systemPrompt, !sys.isEmpty {
                    chat.append(ChatMessageDTO(role: "system", content: sys))
                }
                for msg in parameters.messages {
                    // Extract text content only for now
                    var roleString = "user"
                    switch msg.role {
                    case .user: roleString = "user"
                    case .assistant: roleString = "assistant"
                    default: roleString = "user"
                    }
                    if case let .text(text) = msg.content {
                        chat.append(ChatMessageDTO(role: roleString, content: text))
                    }
                }

                let completionText = try await self.sampleWithOpenAI(
                    chat: chat,
                    maxTokens: parameters.maxTokens,
                    temperature: parameters.temperature
                )

                return await CreateSamplingMessage.Result(
                    model: self.openAIModel,
                    stopReason: .endTurn,
                    role: .assistant,
                    content: .text(completionText)
                )
            }

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

    // MARK: - OpenAI sampling
    private func sampleWithOpenAI(
        chat: [ChatMessageDTO],
        maxTokens: Int?,
        temperature: Double?
    ) async throws -> String {
        guard let apiKey = openAIKey else {
            return "OpenAI API key missing. Add OpenAI_API_Key to Info.plist or OPENAI_API_KEY env."
        }

        struct RequestDTO: Encodable {
            let model: String
            let messages: [ChatMessageDTO]
            let max_tokens: Int?
            let temperature: Double?
        }
        struct ResponseDTO: Decodable {
            struct Choice: Decodable { struct Msg: Decodable { let role: String; let content: String }; let message: Msg }
            let choices: [Choice]
        }
        let body = RequestDTO(model: openAIModel, messages: chat, max_tokens: maxTokens, temperature: temperature)
        let data = try JSONEncoder().encode(body)

        var request = URLRequest(url: URL(string: "https://api.openai.com/v1/chat/completions")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.httpBody = data

        let (respData, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let text = String(data: respData, encoding: .utf8) ?? "<no body>"
            return "OpenAI error: \(text)"
        }
        let decoded = try JSONDecoder().decode(ResponseDTO.self, from: respData)
        return decoded.choices.first?.message.content ?? "<no completion>"
    }

    // MARK: - Simple chat orchestration with one optional tool call
    struct ToolCall: Codable { let tool: String; let arguments: [String: String]? }

    func chatOnce(userText: String) async -> String {
        guard let client else { return "Not connected to MCP server." }

        do {
            // Fetch tool list for the system prompt
            let (tools, _) = try await client.listTools()
            let toolSummary = tools.map { "- \($0.name): \($0.description ?? "")" }.joined(separator: "\n")

            let system = """
            You are a helpful assistant. You can call at most ONE tool from the list below by replying with ONLY a JSON object of the form:
            {"tool":"<name>","arguments":{...}}
            If no tool is needed, reply with a normal helpful answer.
            Available tools:\n\n\(toolSummary)
            """

            let chat: [ChatMessageDTO] = [
                .init(role: "system", content: system),
                .init(role: "user", content: userText)
            ]
            let first = try await sampleWithOpenAI(chat: chat, maxTokens: 600, temperature: 0.2)

            if let data = first.data(using: .utf8), let toolCall = try? JSONDecoder().decode(ToolCall.self, from: data) {
                // Execute tool
                let args = toolCall.arguments ?? [:]
                let (content, isError) = try await client.callTool(name: toolCall.tool, arguments: args)
                let resultText: String
                switch content {
                case .text(let t): resultText = t
                default: resultText = String(describing: content)
                }
                // Ask the model to produce the final user-facing answer using the tool result
                let followup: [ChatMessageDTO] = [
                    .init(role: "system", content: system),
                    .init(role: "user", content: userText),
                    .init(role: "assistant", content: "[Tool \(toolCall.tool) \(isError ? "error" : "result")]\n\n\(resultText)")
                ]
                return try await sampleWithOpenAI(chat: followup, maxTokens: 600, temperature: 0.3)
            } else {
                return first
            }
        } catch {
            return "Chat error: \(error.localizedDescription)"
        }
    }
}


