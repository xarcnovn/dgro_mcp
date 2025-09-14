import Foundation

final class AnthropicService {
    private let apiKey: String
    private let tools: [Tool]
    
    init(apiKey: String, tools: [Tool]) {
        self.apiKey = apiKey
        self.tools = tools
    }
    
    func send(messages: [Request.Message]) async throws -> Response {
        var request = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = Request(
            model: "claude-3-5-sonnet-20241022",
            messages: messages,
            max_tokens: 1024,
            tools: tools.isEmpty ? nil : tools
        )
        
        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check for HTTP errors
        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode != 200 {
                if let errorString = String(data: data, encoding: .utf8) {
                    throw AnthropicError.apiError(statusCode: httpResponse.statusCode, message: errorString)
                }
                throw AnthropicError.httpError(statusCode: httpResponse.statusCode)
            }
        }
        
        // Debug print response
        if let responseString = String(data: data, encoding: .utf8) {
            print("Anthropic response: \(responseString)")
        }
        
        return try JSONDecoder().decode(Response.self, from: data)
    }
}

enum AnthropicError: LocalizedError {
    case httpError(statusCode: Int)
    case apiError(statusCode: Int, message: String)
    
    var errorDescription: String? {
        switch self {
        case .httpError(let statusCode):
            return "HTTP Error: \(statusCode)"
        case .apiError(let statusCode, let message):
            return "API Error \(statusCode): \(message)"
        }
    }
}
