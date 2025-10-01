import { Anthropic } from "@anthropic-ai/sdk";
import {
  MessageParam,
  Tool,
} from "@anthropic-ai/sdk/resources/messages/messages.mjs";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

/**
 * MCP Client using official SDK with StreamableHTTP transport
 * Integrates with Claude API to orchestrate tool calls on the MCP server
 */
export class MCPClient {
  private mcp: Client;
  private anthropic: Anthropic;
  private transport: StreamableHTTPClientTransport;
  private tools: Tool[] = [];
  private systemPrompt: string | null = null;
  private connected: boolean = false;

  constructor(baseUrl: string = process.env.NEXT_PUBLIC_MCP_URL || 'http://localhost:8000') {
    // Initialize MCP client with metadata
    this.mcp = new Client(
      {
        name: 'dgro-web-client',
        version: '1.0.0'
      },
      {
        capabilities: {
          tools: {},  // Support tool calls
          prompts: {}, // Support prompts
        }
      }
    );

    // Initialize StreamableHTTP transport
    this.transport = new StreamableHTTPClientTransport(new URL(`${baseUrl}/mcp`));

    // Initialize Anthropic client
    const apiKey = process.env.NEXT_PUBLIC_ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error("NEXT_PUBLIC_ANTHROPIC_API_KEY is not set");
    }
    this.anthropic = new Anthropic({
      apiKey: apiKey,
      dangerouslyAllowBrowser: true,
    });
  }

  async connect(): Promise<void> {
    if (this.connected) {
      return;
    }

    try {
      // Connect to MCP server (handles initialization automatically)
      await this.mcp.connect(this.transport);

      // List available tools from the server
      const toolsResult = await this.mcp.listTools();
      this.tools = toolsResult.tools.map((tool) => {
        return {
          name: tool.name,
          description: tool.description,
          input_schema: tool.inputSchema,
        };
      });

      console.log(
        "Connected to MCP server with tools:",
        this.tools.map(({ name }) => name),
      );

      // Retrieve the system prompt from the MCP server
      try {
        const promptResult = await this.mcp.getPrompt({
          name: 'system_prompt',
          arguments: undefined,
        });

        // Extract the text content from the prompt messages
        if (promptResult.messages && promptResult.messages.length > 0) {
          const message = promptResult.messages[0];
          if (message.role === 'user' && message.content.type === 'text') {
            this.systemPrompt = message.content.text;
            console.log('System prompt retrieved from MCP server');
          }
        }
      } catch (error) {
        console.warn('Could not retrieve system prompt from MCP server:', error);
      }

      this.connected = true;
    } catch (error) {
      console.error("Failed to connect to MCP server:", error);
      throw error;
    }
  }

  async sendMessage(content: string, history: Array<{role: string, content: string}>): Promise<string> {
    // Ensure we're connected
    if (!this.connected) {
      await this.connect();
    }

    // Build message history for Claude
    const messages: MessageParam[] = [
      ...history.map(msg => ({
        role: msg.role as "user" | "assistant",
        content: msg.content,
      })),
      {
        role: "user" as const,
        content: content,
      }
    ];

    try {
      // Initial Claude API call with MCP tools and system prompt
      let response = await this.anthropic.messages.create({
        model: "claude-sonnet-4-0",
        max_tokens: 4000,
        messages,
        tools: this.tools,
        ...(this.systemPrompt && { system: this.systemPrompt }),
      });

      // Process response and handle tool calls
      const finalText: string[] = [];

      while (response.stop_reason === "tool_use") {
        // Extract text and tool uses from response
        for (const content of response.content) {
          if (content.type === "text") {
            finalText.push(content.text);
          }
        }

        // Collect tool results
        const toolResults = [];

        for (const content of response.content) {
          if (content.type === "tool_use") {
            const toolName = content.name;
            const toolArgs = content.input as { [x: string]: unknown } | undefined;

            console.log(`Calling tool ${toolName} with args:`, toolArgs);

            try {
              // Execute tool call on MCP server
              const result = await this.mcp.callTool({
                name: toolName,
                arguments: toolArgs,
              });

              // Add tool result for Claude
              toolResults.push({
                type: "tool_result" as const,
                tool_use_id: content.id,
                content: JSON.stringify(result.content),
              });
            } catch (error) {
              console.error(`Tool ${toolName} execution failed:`, error);
              // Add error as tool result
              toolResults.push({
                type: "tool_result" as const,
                tool_use_id: content.id,
                content: `Error: ${error instanceof Error ? error.message : String(error)}`,
                is_error: true,
              });
            }
          }
        }

        // Continue conversation with tool results
        messages.push({
          role: "assistant",
          content: response.content,
        });

        messages.push({
          role: "user",
          content: toolResults,
        });

        // Get next response from Claude
        response = await this.anthropic.messages.create({
          model: "claude-sonnet-4-0",
          max_tokens: 4000,
          messages,
          tools: this.tools,
          ...(this.systemPrompt && { system: this.systemPrompt }),
        });
      }

      // Extract final text response
      for (const content of response.content) {
        if (content.type === "text") {
          finalText.push(content.text);
        }
      }

      return finalText.join("\n") || "No response generated";
    } catch (error) {
      console.error("Error processing message:", error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    if (this.connected) {
      await this.mcp.close();
      this.connected = false;
    }
  }

  /**
   * Get the current system prompt
   */
  getSystemPrompt(): string | null {
    return this.systemPrompt;
  }

  /**
   * List all available prompts from the MCP server
   */
  async listPrompts() {
    if (!this.connected) {
      await this.connect();
    }
    return await this.mcp.listPrompts();
  }

  /**
   * Get a specific prompt by name from the MCP server
   */
  async getPrompt(name: string, args?: Record<string, string>) {
    if (!this.connected) {
      await this.connect();
    }
    return await this.mcp.getPrompt({
      name,
      arguments: args,
    });
  }
}
