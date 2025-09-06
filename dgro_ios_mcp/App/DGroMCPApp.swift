
import SwiftUI
import MCP

@main
struct DGroMCPApp: App {
    @StateObject private var mcpManager = MCPClientManager()
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(mcpManager)
                .task {
                    await mcpManager.connect()
                }
        }
    }
}


