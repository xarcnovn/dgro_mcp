#!/bin/bash

echo "🔧 Fixing dgro_ios_app build issues..."

# Clean Xcode derived data
echo "Cleaning Xcode cache..."
rm -rf ~/Library/Developer/Xcode/DerivedData/dgro_ios_app-*

# Clean project
echo "Cleaning project build folder..."
cd /Users/karol/final_mcp/dgro_ios_app
xcodebuild clean -project dgro_ios_app.xcodeproj -scheme dgro_ios_app

echo "✅ Build cache cleaned!"
echo ""
echo "Now in Xcode:"
echo "1. Make sure MCP SDK is added: File → Add Package Dependencies"
echo "2. URL: https://github.com/modelcontextprotocol/swift-sdk.git" 
echo "3. Add NSAppTransportSecurity settings in project Info"
echo "4. Build again (Cmd+B)"
echo ""
echo "🚀 Ready to build!"
