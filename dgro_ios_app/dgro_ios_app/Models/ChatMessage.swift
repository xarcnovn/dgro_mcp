import Foundation

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: MessageRole
    let content: String
    let timestamp = Date()
    
    enum MessageRole: String {
        case user = "user"
        case assistant = "assistant"
        case system = "system"
    }
}
