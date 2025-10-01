/**
 * Test script to verify MCP client can retrieve the system prompt
 *
 * Run with: npx tsx test-mcp-client.ts
 */

import { MCPClient } from './lib/mcp-client';

async function testMCPClient() {
  console.log('🧪 Testing MCP Client...\n');

  const client = new MCPClient();

  try {
    console.log('📡 Connecting to MCP server...');
    await client.connect();
    console.log('✅ Connected successfully\n');

    // Test listing prompts
    console.log('📋 Listing available prompts...');
    const promptsList = await client.listPrompts();
    console.log('Available prompts:', promptsList.prompts.map(p => p.name));
    console.log('');

    // Test getting the system prompt
    console.log('📥 Retrieving system prompt...');
    const systemPrompt = client.getSystemPrompt();

    if (systemPrompt) {
      console.log('✅ System prompt retrieved successfully!');
      console.log('📝 System prompt (first 500 chars):');
      console.log(systemPrompt.substring(0, 500) + '...\n');
    } else {
      console.log('❌ System prompt is null\n');
    }

    // Test getting a prompt directly
    console.log('📥 Getting system_prompt via getPrompt method...');
    const promptResult = await client.getPrompt('system_prompt');
    console.log('Prompt result:', JSON.stringify(promptResult, null, 2).substring(0, 500) + '...\n');

    console.log('🎉 All tests completed!');

    await client.disconnect();
    console.log('👋 Disconnected from MCP server');

  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}

testMCPClient();
