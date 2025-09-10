import Foundation
import MCP

// Extension for Value conversion with error handling
extension MCP.Value {
    init(_ value: Any) throws {
        switch value {
        case let string as String:
            self = try MCP.Value(string)
        case let int as Int:
            self = try MCP.Value(Double(int))
        case let double as Double:
            self = try MCP.Value(double)
        case let float as Float:
            self = try MCP.Value(Double(float))
        case let bool as Bool:
            self = try MCP.Value(bool)
        case let array as [Any]:
            let convertedArray = try array.map { try MCP.Value($0) }
            self = try MCP.Value(convertedArray)
        case let dict as [String: Any]:
            let convertedDict = try dict.mapValues { try MCP.Value($0) }
            self = try MCP.Value(convertedDict)
        default:
            self = try MCP.Value(String(describing: value))
        }
    }
    
    // Safe convenience initializer that falls back to string representation
    static func safe(_ value: Any) -> MCP.Value {
        do {
            return try MCP.Value(value)
        } catch {
            // Fallback to string representation if conversion fails
            do {
                return try MCP.Value(String(describing: value))
            } catch {
                // Ultimate fallback - this should never fail
                return try! MCP.Value("")
            }
        }
    }
}
