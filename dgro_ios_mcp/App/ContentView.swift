import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            NavigationStack { ChatView() }
                .tabItem {
                    Image(systemName: "")
                    Text("Chat")
                }

            DataView()
                .tabItem {
                    Image(systemName: "tray.full")
                    Text("Data")
                }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}

#Preview {
    ContentView()
}

