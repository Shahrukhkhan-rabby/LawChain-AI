import React, { useEffect, useRef, useState } from 'react';
import type { Message, Citation } from '../types';

interface ChatThreadProps {
  messages: Message[];
}

export default function ChatThread({ messages }: ChatThreadProps): React.ReactElement {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const toggleCitation = (chunkId: string): void => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(chunkId)) {
        next.delete(chunkId);
      } else {
        next.add(chunkId);
      }
      return next;
    });
  };

  return (
    <div style={styles.thread} role="log" aria-live="polite" aria-label="Chat messages">
      {messages.length === 0 && (
        <p style={styles.empty}>Ask a question about your uploaded documents.</p>
      )}
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          expandedCitations={expandedCitations}
          onToggleCitation={toggleCitation}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
  expandedCitations: Set<string>;
  onToggleCitation: (chunkId: string) => void;
}

function MessageBubble({ message, expandedCitations, onToggleCitation }: MessageBubbleProps): React.ReactElement {
  const isUser = message.role === 'user';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
      <span style={{ fontSize: 11, color: '#888', marginBottom: 4, [isUser ? 'marginRight' : 'marginLeft']: 4 }}>
        {isUser ? 'You' : 'Assistant'}
      </span>
      <div
        style={{
          maxWidth: '72%',
          padding: '10px 14px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: isUser ? '#1a73e8' : '#f1f3f4',
          color: isUser ? '#fff' : '#202124',
          fontSize: 14,
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {message.content}
      </div>
      {!isUser && message.citations && message.citations.length > 0 && (
        <CitationList
          citations={message.citations}
          expandedCitations={expandedCitations}
          onToggle={onToggleCitation}
        />
      )}
    </div>
  );
}

interface CitationListProps {
  citations: Citation[];
  expandedCitations: Set<string>;
  onToggle: (chunkId: string) => void;
}

function CitationList({ citations, expandedCitations, onToggle }: CitationListProps): React.ReactElement {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8, maxWidth: '72%' }}>
      {citations.map((citation) => (
        <CitationBadge
          key={citation.chunk_id}
          citation={citation}
          isExpanded={expandedCitations.has(citation.chunk_id)}
          onToggle={() => onToggle(citation.chunk_id)}
        />
      ))}
    </div>
  );
}

interface CitationBadgeProps {
  citation: Citation;
  isExpanded: boolean;
  onToggle: () => void;
}

function CitationBadge({ citation, isExpanded, onToggle }: CitationBadgeProps): React.ReactElement {
  const { filename, page_number, chunk_text } = citation;

  return (
    <div>
      <button
        type="button"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '3px 10px',
          borderRadius: 12,
          background: isExpanded ? '#d2e3fc' : '#e8f0fe',
          color: '#1a73e8',
          fontSize: 12,
          fontWeight: 500,
          cursor: 'pointer',
          border: '1px solid #c5d8fb',
          userSelect: 'none',
        }}
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-label={`Citation: ${filename}, page ${page_number}`}
      >
        <span>📄</span>
        <span>{filename} · p.{page_number}</span>
        <span style={{ fontSize: 10 }}>{isExpanded ? '▲' : '▼'}</span>
      </button>
      {isExpanded && chunk_text && (
        <div
          style={{
            marginTop: 6,
            padding: '10px 12px',
            background: '#f8f9fa',
            border: '1px solid #dadce0',
            borderRadius: 6,
            fontSize: 12,
            color: '#3c4043',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxWidth: 400,
          }}
        >
          {chunk_text}
        </div>
      )}
    </div>
  );
}

const styles = {
  thread: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 12,
    padding: '16px',
    overflowY: 'auto' as const,
    flex: 1,
    minHeight: 0,
  },
  empty: {
    color: '#aaa',
    textAlign: 'center' as const,
    marginTop: 40,
    fontSize: 14,
  },
};
