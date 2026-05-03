import { useState, useCallback } from 'react';
import apiClient from '../api/client';
import type { Message, QueryResponse } from '../types';

let _nextMsgId = 1;
function nextMsgId(): number {
  return _nextMsgId++;
}

export interface UseChatReturn {
  messages: Message[];
  sendQuestion: (question: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export function useChat(sessionId: string | null): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendQuestion = useCallback(
    async (question: string): Promise<void> => {
      if (!question.trim() || !sessionId) return;

      const userMessage: Message = {
        id: nextMsgId(),
        role: 'user',
        content: question,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.post<QueryResponse>('/query', {
          question,
          session_id: sessionId,
        });

        const data = response.data;
        const citations = data.citations ?? [];

        const assistantMessage: Message = {
          id: nextMsgId(),
          role: 'assistant',
          content: data.answer ?? '',
          citations,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
        const message =
          axiosErr.response?.data?.detail ??
          axiosErr.response?.data?.message ??
          axiosErr.message ??
          'Failed to get a response.';
        setError(message);

        const errorMessage: Message = {
          id: nextMsgId(),
          role: 'assistant',
          content: `⚠️ ${message}`,
          citations: [],
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId],
  );

  return { messages, sendQuestion, isLoading, error };
}
