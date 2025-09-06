import Foundation

struct ChatMessage: Identifiable, Hashable {
    let id: UUID = UUID()
    let text: String
    let isUser: Bool
    let timestamp: Date
}

struct CaseItem: Identifiable, Hashable {
    let id: UUID = UUID()
    let title: String
    let summary: String
    let createdAt: Date
}

struct OfferItem: Identifiable, Hashable {
    let id: UUID = UUID()
    let title: String
    let details: String
    let value: String
}


