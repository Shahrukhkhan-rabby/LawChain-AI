import React, { useEffect, useState, useCallback } from 'react';
import apiClient, { setAuthToken, DEV_TOKEN } from './api/client';
import UploadPanel from './components/UploadPanel';
import ChatThread from './components/ChatThread';
import QuestionInput from './components/QuestionInput';
import { useChat } from './hooks/useChat';
import type { Document, SessionResponse } from './types';

export default function App(): React.ReactElement {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);

  const { messages, sendQuestion, isLoading: chatLoading } = useChat(sessionId);

  const createSession = useCallback(async (): Promise<void> => {
    setSessionLoading(true);
    setSessionError(null);
    try {
      setAuthToken(DEV_TOKEN);
      const res = await apiClient.post<SessionResponse>('/session');
      setSessionId(res.data.session_id);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      const msg =
        axiosErr.response?.data?.detail ??
        axiosErr.response?.data?.message ??
        axiosErr.message ??
        'Failed to create session.';
      setSessionError(msg);
    } finally {
      setSessionLoading(false);
    }
  }, []);

  useEffect(() => {
    void createSession();
  }, [createSession]);

  useEffect(() => {
    if (!sessionId) return;
    const handleBeforeUnload = (): void => {
      void fetch(`http://localhost:8000/session/${sessionId}`, {
        method: 'DELETE',
        keepalive: true,
        headers: {
          Authorization: (apiClient.defaults.headers.common['Authorization'] as string) ?? '',
        },
      });
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [sessionId]);

  const endSession = async (): Promise<void> => {
    if (!sessionId) return;
    try {
      await apiClient.delete(`/session/${sessionId}`);
    } catch {
      // best-effort
    }
    setSessionId(null);
    setDocuments([]);
    void createSession();
  };

  const handleDocumentReady = useCallback((docId: string, filename: string): void => {
    setDocuments((prev) => {
      if (prev.some((d) => d.docId === docId)) return prev;
      return [...prev, { docId, filename }];
    });
  }, []);

  if (sessionLoading) {
    return (
      <div style={styles.centered}>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <LoadingSpinner />
        <p style={{ color: '#555', marginTop: 12 }}>Starting session…</p>
      </div>
    );
  }

  if (sessionError) {
    return (
      <div style={styles.centered}>
        <p style={{ color: '#d93025' }}>⚠️ {sessionError}</p>
        <button style={styles.retryButton} onClick={() => void createSession()}>Retry</button>
      </div>
    );
  }

  return (
    <div style={styles.appShell}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>⚖️ LawChain-AI</span>
          {documents.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
              {documents.map((doc) => (
                <span key={doc.docId} style={styles.docBadge} title={doc.filename}>
                  📄 {doc.filename.length > 20 ? `${doc.filename.slice(0, 18)}…` : doc.filename}
                </span>
              ))}
            </div>
          )}
        </div>
        <button style={styles.endSessionButton} onClick={() => void endSession()}>End Session</button>
      </header>

      <div style={styles.main}>
        <aside style={styles.sidebar}>
          <UploadPanel sessionId={sessionId} onDocumentReady={handleDocumentReady} />
        </aside>
        <section style={styles.chatColumn}>
          <ChatThread messages={messages} />
          <QuestionInput onSend={sendQuestion} isLoading={chatLoading} />
        </section>
      </div>
    </div>
  );
}

function LoadingSpinner(): React.ReactElement {
  return (
    <div
      style={{ width: 36, height: 36, border: '3px solid #e0e0e0', borderTopColor: '#1a73e8', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}
      aria-label="Loading"
    />
  );
}

const styles = {
  appShell: { display: 'flex', flexDirection: 'column' as const, height: '100vh', fontFamily: "'Segoe UI', system-ui, sans-serif", background: '#f8f9fa', color: '#202124' },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', height: 56, background: '#fff', borderBottom: '1px solid #e0e0e0', flexShrink: 0, gap: 12 },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 12, overflow: 'hidden' },
  logo: { fontSize: 18, fontWeight: 700, whiteSpace: 'nowrap' as const, color: '#1a73e8' },
  docBadge: { fontSize: 11, padding: '2px 8px', background: '#e8f0fe', color: '#1a73e8', borderRadius: 10, border: '1px solid #c5d8fb', whiteSpace: 'nowrap' as const },
  endSessionButton: { padding: '6px 14px', background: 'transparent', color: '#d93025', border: '1px solid #d93025', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap' as const },
  main: { display: 'flex', flex: 1, overflow: 'hidden' },
  sidebar: { width: 440, flexShrink: 0, padding: 16, overflowY: 'auto' as const, borderRight: '1px solid #e0e0e0', background: '#fff' },
  chatColumn: { display: 'flex', flexDirection: 'column' as const, flex: 1, overflow: 'hidden' },
  centered: { display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: "'Segoe UI', system-ui, sans-serif" },
  retryButton: { marginTop: 12, padding: '8px 20px', background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14 },
};
