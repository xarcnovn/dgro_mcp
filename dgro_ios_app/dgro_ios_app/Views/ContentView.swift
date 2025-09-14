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
