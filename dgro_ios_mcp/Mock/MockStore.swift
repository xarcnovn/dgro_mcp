import Foundation

final class MockStore: ObservableObject {
    @Published var messages: [ChatMessage]
    @Published var cases: [CaseItem]
    @Published var offers: [OfferItem]

    init() {
        self.messages = [
            ChatMessage(text: "Hi! I'm your agent. How can I help today?", isUser: false, timestamp: Date().addingTimeInterval(-3600)),
            ChatMessage(text: "Show me latest cases and best offers.", isUser: true, timestamp: Date().addingTimeInterval(-3500)),
            ChatMessage(text: "Sure—check the Data tab for a quick peek!", isUser: false, timestamp: Date().addingTimeInterval(-3400))
        ]

        self.cases = [
            CaseItem(title: "Case 2410-A", summary: "Customer reported sync issues across devices.", createdAt: Date().addingTimeInterval(-86400 * 2)),
            CaseItem(title: "Case 2411-B", summary: "Payment discrepancy flagged and reviewed.", createdAt: Date().addingTimeInterval(-86400))
        ]

        self.offers = [
            OfferItem(title: "Premium Support", details: "24/7 concierge and prioritized routing.", value: "$29/mo"),
            OfferItem(title: "Data Insights", details: "Weekly insights and anomaly alerts.", value: "$19/mo")
        ]
    }

    func sendUser(_ text: String) {
        let msg = ChatMessage(text: text, isUser: true, timestamp: Date())
        messages.append(msg)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            let reply = ChatMessage(text: "(mock) Noted: \(text)", isUser: false, timestamp: Date())
            self.messages.append(reply)
        }
    }
}


