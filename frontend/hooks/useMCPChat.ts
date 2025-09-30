'use client';

import { useState, useRef, useEffect } from 'react';
import { MCPClient } from '@/lib/mcp-client';

export function useMCPChat() {
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const clientRef = useRef<MCPClient | null>(null);

  // Initialize client once
  useEffect(() => {
    clientRef.current = new MCPClient();
    return () => {
      clientRef.current?.disconnect();
    };
  }, []);

  const sendMessage = async (content: string) => {
    if (!clientRef.current) return;

    setIsLoading(true);
    setMessages(prev => [...prev, { role: 'user', content }]);

    try {
      const response = await clientRef.current.sendMessage(content, messages);
      setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    } catch (error) {
      console.error('MCP chat error:', error);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, there was an error processing your request. Please try again.'
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return { messages, isLoading, sendMessage, clearChat };
}
