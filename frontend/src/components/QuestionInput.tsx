import React, { useState, useRef } from 'react';

const MAX_CHARS = 2000;

interface QuestionInputProps {
  onSend: (question: string) => void;
  isLoading: boolean;
}

export default function QuestionInput({ onSend, isLoading }: QuestionInputProps): React.ReactElement {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSubmit = !isLoading && value.trim().length > 0;

  const handleSubmit = (): void => {
    if (!canSubmit) return;
    onSend(value.trim());
    setValue('');
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const remaining = MAX_CHARS - value.length;
  const isNearLimit = remaining <= 200;

  return (
    <div style={styles.container}>
      <div style={styles.row}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value.slice(0, MAX_CHARS))}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents… (Enter to send)"
          disabled={isLoading}
          rows={2}
          style={{
            ...styles.textarea,
            background: isLoading ? '#f8f9fa' : '#fff',
          }}
          aria-label="Question input"
          maxLength={MAX_CHARS}
        />
        <button
          type="button"
          style={{
            ...styles.submitButton,
            background: canSubmit ? '#1a73e8' : '#c5d8fb',
            cursor: canSubmit ? 'pointer' : 'not-allowed',
          }}
          onClick={handleSubmit}
          disabled={!canSubmit}
          aria-label="Send question"
        >
          {isLoading && <Spinner />}
          Ask
        </button>
      </div>
      <span style={{ fontSize: 11, color: isNearLimit ? '#d93025' : '#888', textAlign: 'right' }}>
        {value.length} / {MAX_CHARS}
      </span>
    </div>
  );
}

function Spinner(): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 14,
        height: 14,
        border: '2px solid rgba(255,255,255,0.4)',
        borderTopColor: '#fff',
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
        marginRight: 6,
      }}
      aria-hidden="true"
    />
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 6,
    padding: '12px 16px',
    borderTop: '1px solid #e0e0e0',
    background: '#fff',
  },
  row: {
    display: 'flex',
    gap: 8,
    alignItems: 'flex-end' as const,
  },
  textarea: {
    flex: 1,
    resize: 'none' as const,
    padding: '10px 12px',
    borderRadius: 6,
    border: '1px solid #dadce0',
    fontSize: 14,
    lineHeight: 1.5,
    outline: 'none',
    fontFamily: 'inherit',
    minHeight: 44,
    maxHeight: 160,
    overflowY: 'auto' as const,
    color: '#202124',
  },
  submitButton: {
    padding: '10px 20px',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
    height: 44,
    whiteSpace: 'nowrap' as const,
  },
};
