#!/bin/bash

# DGro MCP iOS System Runner
# This script helps you run the complete iOS + MCP + ChatGPT system

echo "🚀 Starting DGro MCP iOS System..."
echo

# Check if Python server dependencies are installed
echo "📋 Checking Python dependencies..."
cd /Users/karol/final_mcp_september

if ! python -c "import mcp" 2>/dev/null; then
    echo "❌ MCP Python package not found. Installing..."
    pip install mcp
fi

if ! python -c "import sqlite3" 2>/dev/null; then
    echo "❌ SQLite not available"
    exit 1
fi

echo "✅ Python dependencies OK"
echo

# Check if the database exists
if [ ! -f "case_search.db" ]; then
    echo "⚠️  Database not found. The server will create it automatically."
fi

echo "📱 Instructions to run the iOS app:"
echo "1. Open Xcode:"
echo "   cd /Users/karol/final_mcp_september/dgro_ios_mcp"
echo "   open dgro_ios_mcp.xcodeproj"
echo
echo "2. In Xcode:"
echo "   - Select your target device/simulator"
echo "   - Press Cmd+R to build and run"
echo
echo "3. The app will automatically:"
echo "   - Start the Python MCP server on port 8000"
echo "   - Connect to the server via HTTP transport"
echo "   - Initialize ChatGPT with MCP tools access"
echo
echo "4. Look for the connection indicator:"
echo "   - 🔴 Red dot = connecting/disconnected"  
echo "   - 🟢 Green dot = connected and ready"
echo
echo "5. Try these example messages:"
echo "   - 'What tools do you have available?'"
echo "   - 'Help me find web development services'"
echo "   - 'Create a case for mobile app development'"
echo "   - 'Search for React developers'"
echo

# Option to manually start server for testing
read -p "Would you like to manually start the MCP server for testing? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🐍 Starting Python MCP server in HTTP mode..."
    echo "Server will run on http://localhost:8000/mcp"
    echo "Press Ctrl+C to stop the server"
    echo
    python mcp_server_incremental.py http
fi

echo "✅ Setup complete! Launch the iOS app in Xcode."
