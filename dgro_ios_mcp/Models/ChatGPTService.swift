import Foundation

struct ChatGPTMessage: Codable {
    let role: String
    let content: String
}

struct ChatGPTRequest: Codable {
    let model: String
    let messages: [ChatGPTMessage]
    let temperature: Double
    let maxTokens: Int?
    
    enum CodingKeys: String, CodingKey {
        case model, messages, temperature
        case maxTokens = "max_tokens"
    }
}

struct ChatGPTChoice: Codable {
    let message: ChatGPTMessage
}

struct ChatGPTResponse: Codable {
    let choices: [ChatGPTChoice]
}

@MainActor
class ChatGPTService: ObservableObject {
    private let apiKey = "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"
    private let baseURL = "https://api.openai.com/v1/chat/completions"
    
    func sendMessage(_ message: String, conversationHistory: [ChatMessage] = []) async throws -> String {
        var messages: [ChatGPTMessage] = [
            ChatGPTMessage(role: "system", content: """
            You are a helpful assistant with access to MCP (Model Context Protocol) tools. 
            You can help users with case management, searching, email communications, and offer management.
            
            Available MCP tools include:
            - create_case: Create new cases for users
            - execute_google_search: Search for vendors and services
            - scrape_website_contacts: Extract contact information from websites
            - send_email_to_vendor: Send emails to vendors
            - get_unread_vendor_emails: Check for vendor responses
            - create_offer: Create offers from vendor communications
            - get_case_offers: Get all offers for a case
            
            When users ask for help with finding services or vendors, guide them through creating a case and searching for options.
            """)
        ]
        
        // Add conversation history
        for chatMessage in conversationHistory.suffix(10) { // Keep last 10 messages for context
            messages.append(ChatGPTMessage(
                role: chatMessage.isUser ? "user" : "assistant",
                content: chatMessage.text
            ))
        }
        
        // Add current message
        messages.append(ChatGPTMessage(role: "user", content: message))
        
        let request = ChatGPTRequest(
            model: "gpt-4",
            messages: messages,
            temperature: 0.7,
            maxTokens: 1000
        )
        
        guard let url = URL(string: baseURL) else {
            throw ChatGPTError.invalidURL
        }
        
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(request)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ChatGPTError.invalidResponse
        }
        
        if httpResponse.statusCode != 200 {
            throw ChatGPTError.httpError(httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        let chatResponse = try decoder.decode(ChatGPTResponse.self, from: data)
        
        guard let firstChoice = chatResponse.choices.first else {
            throw ChatGPTError.noResponse
        }
        
        return firstChoice.message.content
    }
}

enum ChatGPTError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(Int)
    case noResponse
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .invalidResponse:
            return "Invalid response from ChatGPT"
        case .httpError(let code):
            return "HTTP error: \(code)"
        case .noResponse:
            return "No response from ChatGPT"
        }
    }
}
