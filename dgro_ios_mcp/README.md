# DGro MCP iOS App

This iOS app demonstrates integration between a Swift MCP client and a Python MCP server, with ChatGPT providing intelligent responses using MCP tools.

## Features

- **ChatGPT Integration**: Uses GPT-4 to provide intelligent responses
- **MCP Tools Access**: Can execute MCP tools for case management, vendor searches, etc.
- **Real-time Communication**: Streamable HTTP transport between iOS client and Python server
- **Auto Server Startup**: Automatically starts the Python MCP server when the app launches

## Architecture

```
iOS App (Swift)
├── ChatGPTService: Handles OpenAI API calls
├── IntegratedChatManager: Combines ChatGPT with MCP tools
├── MCPClientManager: Basic MCP client (legacy)
└── UI: SwiftUI chat interface

Python MCP Server
├── Case Management Tools
├── Google Search Integration
├── Email Communication
├── Web Scraping
└── Offer Management
```

## Available MCP Tools

The Python server provides these tools that ChatGPT can use:

- `create_case`: Create new cases for users
- `execute_google_search`: Search for vendors and services
- `scrape_website_contacts`: Extract contact information from websites
- `send_email_to_vendor`: Send emails to vendors
- `get_unread_vendor_emails`: Check for vendor responses
- `create_offer`: Create offers from vendor communications
- `get_case_offers`: Get all offers for a case

## Usage

1. **Launch the app**: The iOS app will automatically start the Python MCP server
2. **Wait for connection**: Watch the status indicator turn green when connected
3. **Start chatting**: Ask ChatGPT questions like:
   - "What tools do you have available?"
   - "Help me find web development services"
   - "Create a case for mobile app development"
   - "Search for graphic design vendors"

## Example Conversations

**User**: "I need help finding a web development company"

**Assistant**: "I can help you find web development companies! Let me create a case for you and search for options. What's your budget range and any specific requirements?"

**User**: "Budget is $10,000 and I need React expertise"

**Assistant**: *[Creates case using MCP tools, searches for vendors, provides results]*

## Technical Details

- **Transport**: Streamable HTTP (port 8000, endpoint /mcp)
- **Server**: Python FastMCP with case_search.db SQLite database
- **Client**: Swift MCP SDK with HTTPClientTransport
- **AI**: OpenAI GPT-4 with custom system prompt for MCP tool usage

## Requirements

- iOS 16.0+
- Python 3.8+ with MCP dependencies
- OpenAI API key (embedded in ChatGPTService)
- SQLite database (case_search.db)

## Development Notes

The app automatically handles:
- Python server process management
- MCP client connection lifecycle
- Error handling and reconnection
- ChatGPT conversation context
- Tool usage detection and execution