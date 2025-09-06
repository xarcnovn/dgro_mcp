import SwiftUI

struct ChatView: View {
    @StateObject private var store = MockStore()
    @State private var draft: String = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(store.messages) { message in
                            HStack(alignment: .bottom) {
                                if message.isUser { Spacer(minLength: 50) }
                                MessageBubble(message: message)
                                if !message.isUser { Spacer(minLength: 50) }
                            }
                            .id(message.id)
                        }
                        .padding(.horizontal, 12)
                        .padding(.top, 12)
                    }
                }
                .onChange(of: store.messages.count) { _ in
                    if let last = store.messages.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
                .onAppear {
                    if let last = store.messages.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }

            Divider()
            HStack(spacing: 10) {
                TextField("Message…", text: $draft, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...4)
                Button(action: send) {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 18, weight: .semibold))
                }
                .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.all, 12)
        }
        .navigationTitle("Chat")
    }

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        store.sendUser(text)
        draft = ""
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(message.text)
                .foregroundColor(message.isUser ? .white : .primary)
                .padding(12)
                .background(message.isUser ? Color.accentColor : Color(.systemGray5))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            Text(Self.dateFormatter.string(from: message.timestamp))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)
        }
        .frame(maxWidth: 280, alignment: message.isUser ? .trailing : .leading)
    }

    private static let dateFormatter: DateFormatter = {
        let df = DateFormatter()
        df.timeStyle = .short
        df.dateStyle = .none
        return df
    }()
}

struct ChatView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationStack { ChatView() }
    }
}


