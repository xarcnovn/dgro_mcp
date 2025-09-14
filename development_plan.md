# iOS MCP Client Development Plan

## Project Overview
Build a simple Swift iOS app that connects to an existing MCP server via streamable HTTP transport, enables chat conversations with Claude Sonnet 3.5, and displays case search database content.

## Architecture Overview

### Core Components
1. **MCP Client Module** - Handles protocol communication with the server
2. **Chat Interface** - User conversation UI
3. **Database Viewer** - Display case_search.db content
4. **Claude Integration** - Anthropic API for LLM sampling

### Technology Stack
- **Swift 6.0+** with SwiftUI
- **MCP Swift SDK** for client implementation
- **HTTPClientTransport** for streamable HTTP connection
- **Anthropic Swift SDK** or URLSession for Claude API
- **SQLite3** for local database viewing

## Implementation Plan

### Phase 1: Project Setup
1. **Create new iOS project**
   - Target iOS 16.0+ (minimum for MCP SDK)
   - SwiftUI app lifecycle
   - Add required packages

2. **Dependencies**
   ```swift
   dependencies: [
       .package(url: "https://github.com/modelcontextprotocol/swift-sdk.git", from: "0.10.0"),
       // No official Anthropic Swift SDK, will use URLSession
   ]
   ```

3. **Project Structure**
   ```
   MCPCaseSearch/
   ├── App/
   │   └── MCPCaseSearchApp.swift
   ├── Views/
   │   ├── ContentView.swift
   │   ├── ChatView.swift
   │   ├── DatabaseView.swift
   │   ├── CaseDetailView.swift
   │   └── OfferDetailView.swift
   ├── Models/
   │   ├── ChatMessage.swift
   │   ├── CaseModel.swift
   │   ├── OfferModel.swift
   │   └── AnthropicModels.swift
   ├── Services/
   │   ├── MCPClientService.swift
   │   ├── AnthropicService.swift
   │   └── DatabaseService.swift
   └── Config/
       └── Configuration.swift
   ```

### Phase 2: MCP Client Implementation

#### MCPClientService.swift
```swift
import MCP
import Foundation

class MCPClientService: ObservableObject {
    private var client: Client?
    private var transport: HTTPClientTransport?
    @Published var isConnected = false
    @Published var availableTools: [Tool] = []
    
    init() {
        setupClient()
    }
    
    private func setupClient() {
        client = Client(
            name: "MCPCaseSearchiOS",
            version: "1.0.0",
            configuration: .default
        )
    }
    
    func connect() async throws {
        // Connect to local server (adjust URL as needed)
        transport = HTTPClientTransport(
            endpoint: URL(string: "http://localhost:8000/mcp")!,
            streaming: true
        )
        
        let result = try await client!.connect(transport: transport!)
        
        // List available tools
        let (tools, _) = try await client!.listTools()
        await MainActor.run {
            self.availableTools = tools
            self.isConnected = true
        }
    }
    
    func callTool(name: String, arguments: [String: Any]) async throws -> CallTool.Result {
        guard let client = client else {
            throw MCPError.invalidRequest("Client not connected")
        }
        return try await client.callTool(name: name, arguments: arguments)
    }
}
```

### Phase 3: Claude Integration

#### Models/AnthropicModels.swift
```swift
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
    let input: [String: Any]?
    let id: String?
    
    enum CodingKeys: String, CodingKey {
        case type, text, name, input, id
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        text = try container.decodeIfPresent(String.self, forKey: .text)
        name = try container.decodeIfPresent(String.self, forKey: .name)
        id = try container.decodeIfPresent(String.self, forKey: .id)
        
        if let inputData = try? container.decode([String: Any].self, forKey: .input) {
            input = inputData
        } else {
            input = nil
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        try container.encodeIfPresent(text, forKey: .text)
        try container.encodeIfPresent(name, forKey: .name)
        try container.encodeIfPresent(id, forKey: .id)
        // Note: Encoding [String: Any] requires custom implementation
    }
}

struct Tool: Codable {
    let name: String
    let description: String
    let input_schema: [String: Any]?
    
    // Custom encoding/decoding for input_schema if needed
}
```

#### Services/AnthropicService.swift
```swift
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
            model: "claude-3-5-sonnet-20241022",  // Using Sonnet 3.5 as requested
            messages: messages,
            max_tokens: 1024,
            tools: tools
        )
        
        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        
        return try JSONDecoder().decode(Response.self, from: data)
    }
}
```

### Phase 4: Chat Interface

#### ChatView.swift
```swift
import SwiftUI
import MCP

struct ChatView: View {
    @StateObject private var mcpClient = MCPClientService()
    @State private var anthropicService: AnthropicService?
    @State private var messages: [ChatMessage] = []
    @State private var anthropicMessages: [Request.Message] = []
    @State private var inputText = ""
    @State private var isProcessing = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "message.badge.filled.fill")
                    .font(.title2)
                    .foregroundColor(.blue)
                Text("Case Search Assistant")
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(mcpClient.isConnected ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(mcpClient.isConnected ? "Connected" : "Disconnected")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding()
            .background(Color(.systemBackground))
            .shadow(radius: 1)
            
            // Messages list
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .padding()
                    .onChange(of: messages.count) { _ in
                        withAnimation {
                            proxy.scrollTo(messages.last?.id, anchor: .bottom)
                        }
                    }
                }
            }
            
            // Input field
            HStack(spacing: 12) {
                TextField("Ask about cases, vendors, or offers...", text: $inputText)
                    .textFieldStyle(.roundedBorder)
                    .disabled(isProcessing || !mcpClient.isConnected)
                    .onSubmit {
                        sendMessage()
                    }
                
                Button(action: sendMessage) {
                    Image(systemName: isProcessing ? "ellipsis.circle" : "paperplane.fill")
                        .foregroundColor(inputText.isEmpty || isProcessing ? .gray : .blue)
                }
                .disabled(inputText.isEmpty || isProcessing || !mcpClient.isConnected)
                .animation(.easeInOut, value: isProcessing)
            }
            .padding()
            .background(Color(.secondarySystemBackground))
        }
        .task {
            await connectToServer()
        }
    }
    
    private func connectToServer() async {
        do {
            try await mcpClient.connect()
            
            // Initialize Anthropic service with MCP tools
            let tools = mcpClient.availableTools.map { mcpTool in
                Tool(
                    name: mcpTool.name,
                    description: mcpTool.description ?? "",
                    input_schema: mcpTool.inputSchema
                )
            }
            
            anthropicService = AnthropicService(
                apiKey: Config.anthropicAPIKey,
                tools: tools
            )
        } catch {
            print("Failed to connect: \(error)")
        }
    }
    
    private func sendMessage() {
        let text = inputText
        inputText = ""
        
        Task {
            await processUserMessage(text)
        }
    }
    
    private func processUserMessage(_ text: String) async {
        guard !text.isEmpty else { return }
        
        // Add user message to UI
        let userMessage = ChatMessage(role: .user, content: text)
        await MainActor.run {
            messages.append(userMessage)
        }
        
        // Add to Anthropic messages format
        anthropicMessages.append(Request.Message(
            role: .user,
            content: [Content(type: "text", text: text, name: nil, input: nil, id: nil)]
        ))
        
        await MainActor.run {
            isProcessing = true
        }
        defer {
            Task { @MainActor in
                isProcessing = false
            }
        }
        
        // Send to Claude
        do {
            guard let service = anthropicService else { return }
            let response = try await service.send(messages: anthropicMessages)
            
            // Process response and handle tool calls
            await processClaudeResponse(response)
        } catch {
            await MainActor.run {
                messages.append(ChatMessage(
                    role: .assistant,
                    content: "Error: \(error.localizedDescription)"
                ))
            }
        }
    }
    
    private func processClaudeResponse(_ response: Response) async {
        var assistantContent: [Content] = []
        
        for content in response.content {
            if content.type == "text" {
                // Add text to UI
                if let text = content.text {
                    await MainActor.run {
                        messages.append(ChatMessage(role: .assistant, content: text))
                    }
                    assistantContent.append(content)
                }
            } else if content.type == "tool_use" {
                // Execute tool via MCP
                if let toolName = content.name,
                   let toolInput = content.input {
                    
                    assistantContent.append(content)
                    
                    do {
                        let result = try await mcpClient.callTool(
                            name: toolName,
                            arguments: toolInput
                        )
                        
                        // Show tool execution in UI
                        await MainActor.run {
                            messages.append(ChatMessage(
                                role: .system,
                                content: "🔧 Executed: \(toolName)"
                            ))
                        }
                        
                        // Add assistant message with tool use to messages
                        anthropicMessages.append(Request.Message(
                            role: .assistant,
                            content: assistantContent
                        ))
                        
                        // Add tool result as user message
                        let toolResultText = result.content.compactMap { item in
                            if case .text(let text) = item {
                                return text
                            }
                            return nil
                        }.joined(separator: "\n")
                        
                        anthropicMessages.append(Request.Message(
                            role: .user,
                            content: [Content(
                                type: "tool_result",
                                text: toolResultText,
                                name: nil,
                                input: nil,
                                id: content.id
                            )]
                        ))
                        
                        // Continue conversation
                        await continueConversation()
                        
                    } catch {
                        await MainActor.run {
                            messages.append(ChatMessage(
                                role: .system,
                                content: "❌ Tool error: \(error.localizedDescription)"
                            ))
                        }
                    }
                }
            }
        }
        
        // If we only got text (no tool calls), add to anthropic messages
        if !assistantContent.isEmpty && assistantContent.allSatisfy({ $0.type == "text" }) {
            anthropicMessages.append(Request.Message(
                role: .assistant,
                content: assistantContent
            ))
        }
    }
    
    private func continueConversation() async {
        // Send continuation to Claude with tool results
        do {
            guard let service = anthropicService else { return }
            let response = try await service.send(messages: anthropicMessages)
            await processClaudeResponse(response)
        } catch {
            await MainActor.run {
                messages.append(ChatMessage(
                    role: .assistant,
                    content: "Error continuing conversation: \(error.localizedDescription)"
                ))
            }
        }
    }
}
```

### Phase 5: Database Viewer (Direct SQLite Access)

#### Services/DatabaseService.swift
```swift
import Foundation
import SQLite3

class DatabaseService: ObservableObject {
    private var db: OpaquePointer?
    private let dbPath = "/Users/karol/final_mcp/case_search.db"
    
    @Published var cases: [CaseModel] = []
    @Published var offers: [OfferModel] = []
    @Published var users: [UserModel] = []
    @Published var communications: [EmailCommunication] = []
    
    init() {
        openDatabase()
    }
    
    deinit {
        if db != nil {
            sqlite3_close(db)
        }
    }
    
    private func openDatabase() {
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("Unable to open database")
        }
    }
    
    func loadCases() {
        cases.removeAll()
        let queryString = "SELECT * FROM cases ORDER BY id DESC"
        
        var queryStatement: OpaquePointer?
        if sqlite3_prepare_v2(db, queryString, -1, &queryStatement, nil) == SQLITE_OK {
            while sqlite3_step(queryStatement) == SQLITE_ROW {
                let id = Int(sqlite3_column_int(queryStatement, 0))
                let subject = String(cString: sqlite3_column_text(queryStatement, 1))
                let features = String(cString: sqlite3_column_text(queryStatement, 2))
                let location = String(cString: sqlite3_column_text(queryStatement, 3))
                let budget = Double(sqlite3_column_double(queryStatement, 4))
                let timeline = String(cString: sqlite3_column_text(queryStatement, 5))
                let additionalFeatures = String(cString: sqlite3_column_text(queryStatement, 6))
                
                let caseModel = CaseModel(
                    id: id,
                    subject: subject,
                    features: features,
                    location: location,
                    budget: budget,
                    timeline: timeline,
                    additionalFeatures: additionalFeatures
                )
                cases.append(caseModel)
            }
        }
        sqlite3_finalize(queryStatement)
    }
    
    func loadOffers() {
        offers.removeAll()
        let queryString = "SELECT * FROM offers ORDER BY created_at DESC"
        
        var queryStatement: OpaquePointer?
        if sqlite3_prepare_v2(db, queryString, -1, &queryStatement, nil) == SQLITE_OK {
            while sqlite3_step(queryStatement) == SQLITE_ROW {
                let offerId = Int(sqlite3_column_int(queryStatement, 0))
                let caseId = Int(sqlite3_column_int(queryStatement, 1))
                let status = String(cString: sqlite3_column_text(queryStatement, 2))
                let price = Double(sqlite3_column_double(queryStatement, 3))
                let timeline = String(cString: sqlite3_column_text(queryStatement, 4))
                let accuracy = Double(sqlite3_column_double(queryStatement, 5))
                let additionalDetails = String(cString: sqlite3_column_text(queryStatement, 6))
                let vendorEmail = String(cString: sqlite3_column_text(queryStatement, 8))
                
                let offer = OfferModel(
                    offerId: offerId,
                    caseId: caseId,
                    status: status,
                    price: price,
                    timeline: timeline,
                    accuracy: accuracy,
                    additionalDetails: additionalDetails,
                    vendorEmail: vendorEmail
                )
                offers.append(offer)
            }
        }
        sqlite3_finalize(queryStatement)
    }
    
    func getCaseById(_ id: Int) -> CaseModel? {
        return cases.first { $0.id == id }
    }
}
```

#### DatabaseView.swift
```swift
import SwiftUI

struct DatabaseView: View {
    @StateObject private var dbService = DatabaseService()
    @State private var selectedTab = 0
    @State private var selectedCase: CaseModel?
    @State private var selectedOffer: OfferModel?
    
    var body: some View {
        TabView(selection: $selectedTab) {
            // Cases Tab
            NavigationStack {
                List(dbService.cases) { caseItem in
                    NavigationLink(destination: CaseDetailView(caseModel: caseItem)) {
                        CaseRowView(caseModel: caseItem)
                    }
                }
                .navigationTitle("Cases")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: refreshData) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
                .refreshable {
                    refreshData()
                }
            }
            .tabItem {
                Label("Cases", systemImage: "folder.fill")
            }
            .tag(0)
            
            // Offers Tab
            NavigationStack {
                List(dbService.offers) { offer in
                    NavigationLink(destination: OfferDetailView(offer: offer, dbService: dbService)) {
                        OfferRowView(offer: offer, caseTitle: dbService.getCaseById(offer.caseId)?.subject ?? "Unknown Case")
                    }
                }
                .navigationTitle("Offers")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: refreshData) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
                .refreshable {
                    refreshData()
                }
            }
            .tabItem {
                Label("Offers", systemImage: "tag.fill")
            }
            .tag(1)
        }
        .task {
            refreshData()
        }
    }
    
    private func refreshData() {
        dbService.loadCases()
        dbService.loadOffers()
    }
}

struct CaseRowView: View {
    let caseModel: CaseModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(caseModel.subject)
                .font(.headline)
                .lineLimit(1)
            
            HStack {
                Label("$\(caseModel.budget, specifier: "%.0f")", systemImage: "dollarsign.circle")
                    .font(.caption)
                    .foregroundColor(.green)
                
                Spacer()
                
                Label(caseModel.location, systemImage: "location")
                    .font(.caption)
                    .foregroundColor(.blue)
            }
            
            Text(caseModel.timeline)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct OfferRowView: View {
    let offer: OfferModel
    let caseTitle: String
    
    var statusColor: Color {
        switch offer.status {
        case "active": return .green
        case "pending": return .orange
        case "accepted": return .blue
        case "rejected": return .red
        case "expired": return .gray
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(caseTitle)
                    .font(.headline)
                    .lineLimit(1)
                
                Spacer()
                
                Text(offer.status.capitalized)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(statusColor.opacity(0.2))
                    .foregroundColor(statusColor)
                    .cornerRadius(4)
            }
            
            HStack {
                Text("$\(offer.price, specifier: "%.0f")")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Text("•")
                    .foregroundColor(.secondary)
                
                Text(offer.timeline)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Text(offer.vendorEmail)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}
```

### Phase 6: Model Definitions

#### Models/CaseModel.swift
```swift
import Foundation

struct CaseModel: Identifiable {
    let id: Int
    let subject: String
    let features: String
    let location: String
    let budget: Double
    let timeline: String
    let additionalFeatures: String
}
```

#### Models/OfferModel.swift
```swift
import Foundation

struct OfferModel: Identifiable {
    let id = UUID()
    let offerId: Int
    let caseId: Int
    let status: String
    let price: Double
    let timeline: String
    let accuracy: Double
    let additionalDetails: String
    let vendorEmail: String
}
```

#### Models/ChatMessage.swift
```swift
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
```

### Phase 7: Main App Structure

#### ContentView.swift
```swift
import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .tabItem {
                    Label("Chat", systemImage: "message.fill")
                }
                .tag(0)
            
            DatabaseView()
                .tabItem {
                    Label("Database", systemImage: "cylinder.fill")
                }
                .tag(1)
        }
        .tint(.blue)
    }
}
```

#### Views/MessageBubble.swift
```swift
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
```

## Server Configuration Requirements

1. **Enable streamable HTTP transport**
   - The server already supports this via `mcp.run(transport="streamable-http")`
   - Default endpoint: `http://localhost:8000/mcp`

2. **CORS Configuration** (if needed for testing)
   - Already configured in the server for browser clients

## Deployment Considerations

### For Testing
1. Run MCP server locally with streamable HTTP:
   ```bash
   cd /Users/karol/final_mcp
   python mcp_server_incremental.py
   # Server will run with streamable HTTP transport on port 8000
   ```

2. Configure iOS app to connect to local server:
   - For iOS Simulator: Use `http://localhost:8000/mcp`
   - For physical device: Use computer's local IP address
   - Example: `http://192.168.1.100:8000/mcp`
   - Find your IP: `ifconfig | grep "inet " | grep -v 127.0.0.1`

### Security Notes (for production - not needed for testing)
- Store API keys in iOS Keychain
- Use secure transport (HTTPS) for production
- Implement proper error handling
- Add request timeout handling

## Testing Plan

1. **Unit Tests**
   - MCP client connection
   - Tool calling
   - Claude API integration

2. **Integration Tests**
   - Full chat flow with tool execution
   - Database operations

3. **Manual Testing**
   - Create case workflow
   - Search functionality
   - Email communications
   - Offer management

## Simplified Features for MVP

Given the "KEEP IT SIMPLE STUPID" requirement:
1. **No authentication** - Direct connection to server
2. **Basic UI** - Simple SwiftUI components
3. **Minimal error handling** - Just display errors to user
4. **No data persistence** - Everything in memory
5. **Hardcoded configuration** - API keys and URLs in code
6. **No logging framework** - Just print statements for debugging

## Quick Start Implementation

To get started immediately:

1. Create new iOS project in Xcode
2. Add MCP Swift SDK package dependency
3. Copy the MCPClientService and ClaudeService classes
4. Build basic chat UI
5. Add Configuration file with:
   ```swift
   struct Config {
       static let anthropicAPIKey = "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"
       static let mcpServerURL = "http://localhost:8000/mcp"
       static let databasePath = "/Users/karol/final_mcp/case_search.db"
   }
   ```
6. Run and test

## Next Steps

1. Set up Xcode project
2. Implement MCP client connection
3. Add Claude integration
4. Build chat interface
5. Add database viewer
6. Test with local server
7. Iterate based on testing

This plan provides a clear roadmap for building the iOS MCP client app with minimal complexity while meeting all requirements.
