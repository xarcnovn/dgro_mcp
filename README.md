# MCP Client

A Python client library for connecting to MCP (Model Context Protocol) servers, with a focus on browser integration.

## Features

- Connect to any MCP server using SSE (Server-Sent Events)
- Discover and use tools, prompts, and resources
- Local development server with browser UI
- WebSocket support for real-time updates
- Fully async design for high performance

## Installation

```bash
# From source
pip install -e .

# Or when published
pip install mcp_client
```

## Quickstart

### Running the development server

```bash
# Start the development server
mcp_client serve --server-url http://localhost:8001/mcp
```

This will:
1. Start a local web server on port 8000
2. Open a browser window with the UI
3. Connect to the specified MCP server

### Using the client in your code

```python
import asyncio
from mcp_client import MCPClient

async def example():
    # Initialize client
    client = MCPClient(server_url="http://localhost:8001/mcp")
    
    # Connect to server
    await client.connect()
    
    # List available tools
    tools = await client.list_tools()
    print(f"Available tools: {len(tools)}")
    
    # Call a tool
    result = await client.call_tool("echo_tool", {"message": "Hello, world!"})
    print(f"Tool result: {result}")
    
    # Clean up
    await client.disconnect()

# Run the example
asyncio.run(example())
```

## Development Server UI

The development server provides a web-based UI for:

- Connecting to MCP servers
- Discovering available tools, resources, and prompts
- Testing tool execution with form-based input
- Viewing resource content
- Testing prompt templates

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
