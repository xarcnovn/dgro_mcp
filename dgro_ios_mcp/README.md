# dgro_ios_mcp (UI-only SwiftUI sample)

SwiftUI app with two tabs and mock data only:
- Chat: simple chat with mock replies
- Data: cases and offers with detail views

No networking. No database.

## Run in Xcode
1. Create a new iOS App project (SwiftUI, Swift, iOS 16+).
2. Delete the default `App` and `ContentView` files from the project.
3. Drag the entire `dgro_ios_mcp` folder into the project (copy items if needed).
4. Build and run. `DGroMCPApp` (with `@main`) is the entry point.

## Structure
- App: entry and tabs (`DGroMCPApp.swift`, `ContentView.swift`)
- Models: simple structs (`Models.swift`)
- Mock: mock store/data (`MockStore.swift`)
- Views: Chat (`ChatView.swift`) and Data (`DataView.swift`)

To integrate real data later, replace `MockStore` with your data layer.
