import Foundation

struct Request: Encodable {
    let model: String
    let messages: [Message]
    let max_tokens: Int
    let tools: [Tool]?
    
    struct Message: Encodable {
        enum Role: String, Encodable {
            case user
            case assistant
        }
        
        let role: Role
        let content: [Content]
    }
}

struct Response: Decodable {
    let content: [Content]
}

struct Content: Codable {
    let type: String
    let text: String?
    let name: String?
    let input: [String: AnyCodable]?
    let id: String?
    let tool_use_id: String?
    
    enum CodingKeys: String, CodingKey {
        case type, text, name, input, id
        case tool_use_id
    }
}

struct Tool: Encodable {
    let name: String
    let description: String
    let input_schema: [String: AnyCodable]?
}

// Helper for encoding/decoding Any types
struct AnyCodable: Codable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dictionary = try? container.decode([String: AnyCodable].self) {
            value = dictionary.mapValues { $0.value }
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode value")
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dictionary as [String: Any]:
            try container.encode(dictionary.mapValues { AnyCodable($0) })
        default:
            throw EncodingError.invalidValue(value, EncodingError.Context(codingPath: [], debugDescription: "Cannot encode value"))
        }
    }
}

// Extension to convert MCP types to our types
extension [String: Any] {
    var toAnyCodable: [String: AnyCodable] {
        return self.mapValues { AnyCodable($0) }
    }
}

extension [String: AnyCodable] {
    var toAny: [String: Any] {
        return self.mapValues { $0.value }
    }
}
