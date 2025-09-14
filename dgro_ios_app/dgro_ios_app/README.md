# MCP Case Search iOS App

A Swift iOS client for the MCP Case Search server, featuring chat interface with Claude AI and database visualization.

## Features

- 💬 **Chat Interface**: Converse with Claude 3.5 Sonnet using MCP tools
- 📊 **Database Viewer**: Browse cases and offers with direct SQLite access
- 🔧 **MCP Integration**: Full support for all 19 server tools
- 🎨 **Elegant UI**: Simple yet beautiful SwiftUI interface

## Requirements

- iOS 16.0+
- Xcode 16.0+
- Swift 6.0+
- MCP server running locally

## Setup Instructions

### 1. Start the MCP Server

```bash
cd /Users/karol/final_mcp
python mcp_server_incremental.py
```

The server will run on `http://localhost:8000/mcp`

### 2. Open in Xcode

#### Option A: Create New Xcode Project
1. Open Xcode
2. File → New → Project
3. Choose iOS → App
4. Product Name: `MCPCaseSearch`
5. Interface: SwiftUI
6. Language: Swift
7. Copy all files from this directory into the project

#### Option B: Open Existing Files
1. Open Xcode
2. File → Open
3. Navigate to `/Users/karol/final_mcp/MCPCaseSearch`
4. Select the folder

### 3. Add MCP SDK Dependency

1. In Xcode: File → Add Package Dependencies
2. Enter URL: `https://github.com/modelcontextprotocol/swift-sdk.git`
3. Version: Up to Next Major Version: `0.10.0`
4. Add Package

### 4. Configure for Testing

#### For iOS Simulator:
- No changes needed, uses `localhost:8000`

#### For Physical Device:
1. Find your Mac's IP address:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
2. Update `Config/Configuration.swift`:
   ```swift
   static let mcpServerURL = "http://YOUR_IP:8000/mcp"
   ```

### 5. Build and Run

1. Select your target device (Simulator or physical device)
2. Press Cmd+R or click the Run button
3. The app will launch and automatically connect to the server

## Project Structure

```
MCPCaseSearch/
├── App/
│   └── MCPCaseSearchApp.swift      # Main app entry point
├── Config/
│   └── Configuration.swift          # API keys and server URLs
├── Models/
│   ├── AnthropicModels.swift       # Claude API models
│   ├── CaseModel.swift             # Database models
│   ├── ChatMessage.swift           # Chat message model
│   └── OfferModel.swift            # Offer model
├── Services/
│   ├── AnthropicService.swift      # Claude API service
│   ├── DatabaseService.swift       # SQLite database access
│   └── MCPClientService.swift      # MCP client implementation
└── Views/
    ├── CaseDetailView.swift        # Case details screen
    ├── ChatView.swift              # Main chat interface
    ├── ContentView.swift           # Tab container
    ├── DatabaseView.swift          # Database browser
    ├── MessageBubble.swift         # Chat message UI
    └── OfferDetailView.swift       # Offer details screen
```

## Usage

### Chat Tab
1. Ask questions about cases, vendors, or offers
2. Claude will use MCP tools to:
   - Create and manage cases
   - Search for vendors
   - Send emails
   - Track offers

### Database Tab
1. **Cases**: View all cases with details
2. **Offers**: Browse vendor offers with status
3. Pull to refresh for latest data
4. Tap any item for detailed view

## Available MCP Tools

The app can use all 19 server tools:
- Case management (create, update, get)
- User management
- Google search integration
- Website scraping
- Email communications
- Offer tracking

## Troubleshooting

### Connection Issues
- Ensure server is running: `python mcp_server_incremental.py`
- Check server URL in Configuration.swift
- For physical device, use Mac's IP instead of localhost

### Database Not Loading
- Verify database path in Configuration.swift
- Check file permissions for case_search.db

### Chat Not Working
- Verify Anthropic API key in Configuration.swift
- Check console for error messages

## Security Notes

⚠️ **For Testing Only**
- API key is hardcoded (move to Keychain for production)
- HTTP transport allowed (use HTTPS in production)
- No authentication implemented

## License

Private - For testing purposes only
