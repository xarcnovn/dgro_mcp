'use client';

import { useState, useRef } from 'react';
import { MCPClient } from '@/lib/mcp-client';

export function useMCPChat() {
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<MCPClient | null>(null);

  // Lazy initialize client only when needed
  const getClient = () => {
    if (clientRef.current) {
      return clientRef.current;
    }

    try {
      clientRef.current = new MCPClient();
      setError(null);
      return clientRef.current;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to initialize MCP client';
      setError(errorMessage);
      console.error('MCP client initialization error:', err);
      return null;
    }
  };

  const sendMessage = async (content: string) => {
    setIsLoading(true);
    setMessages(prev => [...prev, { role: 'user', content }]);

    try {
      const client = getClient();
      if (!client) {
        throw new Error(error || 'MCP client not available');
      }

      const response = await client.sendMessage(content, messages);
      setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    } catch (error) {
      console.error('MCP chat error:', error);
      const errorMsg = error instanceof Error ? error.message : 'An unknown error occurred';
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, there was an error: ${errorMsg}. Please check your configuration and try again.`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  const cleanup = async () => {
    if (clientRef.current) {
      try {
        await clientRef.current.disconnect();
      } catch (err) {
        console.error('Error disconnecting MCP client:', err);
      }
      clientRef.current = null;
    }
  };

  return { messages, isLoading, error, sendMessage, clearChat, cleanup };
}
