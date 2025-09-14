import SwiftUI

struct MessageBubble: View {
    let message: ChatMessage
    
    var backgroundColor: Color {
        switch message.role {
        case .user:
            return Color.blue
        case .assistant:
            return Color(.systemGray5)
        case .system:
            return Color.orange.opacity(0.2)
        }
    }
    
    var alignment: HorizontalAlignment {
        message.role == .user ? .trailing : .leading
    }
    
    var body: some View {
        HStack {
            if message.role == .user { Spacer() }
            
            VStack(alignment: alignment, spacing: 4) {
                if message.role == .system {
                    Text("System")
                        .font(.caption2)
                        .foregroundColor(.orange)
                }
                
                Text(message.content)
                    .padding(12)
                    .background(backgroundColor)
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(16)
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: UIScreen.main.bounds.width * 0.75, alignment: alignment == .trailing ? .trailing : .leading)
            
            if message.role != .user { Spacer() }
        }
    }
}
