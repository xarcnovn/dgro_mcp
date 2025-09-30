import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";

/**
 * HTTP Transport for browser-based MCP connections
 * Official SDK handles protocol details, we just provide transport layer
 */
class HTTPTransport implements Transport {
  private baseUrl: string;
  private sessionId: string | null = null;
  private onMessage?: (message: any) => void;
  private onError?: (error: Error) => void;
  private onClose?: () => void;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async start(): Promise<void> {
    // Connection established
  }

  async send(message: any): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/mcp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json, text/event-stream',
          ...(this.sessionId && { 'Mcp-Session-Id': this.sessionId }),
        },
        body: JSON.stringify(message),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Extract and store session ID
      const newSessionId = response.headers.get('Mcp-Session-Id');
      if (newSessionId) {
        this.sessionId = newSessionId;
      }

      const data = await response.json();
      if (this.onMessage) {
        this.onMessage(data);
      }
    } catch (error) {
      if (this.onError) {
        this.onError(error as Error);
      }
      throw error;
    }
  }

  async close(): Promise<void> {
    this.sessionId = null;
    if (this.onClose) {
      this.onClose();
    }
  }

  setMessageHandler(handler: (message: any) => void): void {
    this.onMessage = handler;
  }

  setErrorHandler(handler: (error: Error) => void): void {
    this.onError = handler;
  }

  setCloseHandler(handler: () => void): void {
    this.onClose = handler;
  }
}

/**
 * MCP Client using official SDK
 * Handles all protocol details automatically
 */
export class MCPClient {
  private client: Client;
  private transport: HTTPTransport;
  private connected: boolean = false;

  constructor(baseUrl: string = process.env.NEXT_PUBLIC_MCP_URL || 'http://localhost:8000') {
    this.transport = new HTTPTransport(baseUrl);
    this.client = new Client(
      {
        name: 'dgro-web-client',
        version: '1.0.0'
      },
      {
        capabilities: {
          tools: {},  // Support tool calls
        }
      }
    );
  }

  async connect(): Promise<void> {
    if (!this.connected) {
      await this.client.connect(this.transport);
      this.connected = true;
    }
  }

  async sendMessage(content: string, history: Array<{role: string, content: string}>): Promise<string> {
    if (!this.connected) {
      await this.connect();
    }

    // Call the 'chat' tool on your MCP server
    const result = await this.client.callTool({
      name: 'chat',
      arguments: {
        message: content,
        history: history,
      },
    });

    // Extract response from tool result
    if (result.content && result.content.length > 0) {
      const firstContent = result.content[0];
      if (firstContent.type === 'text') {
        return firstContent.text;
      }
    }

    return 'No response';
  }

  async disconnect(): Promise<void> {
    if (this.connected) {
      await this.client.close();
      this.connected = false;
    }
  }
}
