import React, { useRef, useState, useCallback } from 'react';
import apiClient from '../api/client';
import type { FileEntry, FileStatus, UploadResponse } from '../types';

let _nextId = 1;
function nextId(): number {
  return _nextId++;
}

const STATUS_COLORS: Record<FileStatus, string> = {
  pending: '#888',
  uploading: '#1a73e8',
  ready: '#1e8e3e',
  error: '#d93025',
};

const STATUS_LABELS: Record<FileStatus, string> = {
  pending: 'Pending',
  uploading: 'Uploading',
  ready: 'Ready',
  error: 'Error',
};

interface UploadPanelProps {
  sessionId: string | null;
  onDocumentReady: (docId: string, filename: string) => void;
}

export default function UploadPanel({ sessionId, onDocumentReady }: UploadPanelProps): React.ReactElement {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const updateFile = useCallback((id: number, patch: Partial<FileEntry>): void => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  }, []);

  const uploadFile = useCallback(
    async (entry: FileEntry): Promise<void> => {
      if (!sessionId) return;
      updateFile(entry.id, { status: 'uploading', progress: 0 });

      const formData = new FormData();
      formData.append('file', entry.file);
      formData.append('session_id', sessionId);

      try {
        const response = await apiClient.post<UploadResponse>('/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (evt) => {
            if (evt.total) {
              const pct = Math.round((evt.loaded / evt.total) * 100);
              updateFile(entry.id, { progress: pct });
            }
          },
        });

        const { doc_id } = response.data;
        updateFile(entry.id, { status: 'ready', progress: 100 });
        onDocumentReady(doc_id, entry.file.name);
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
        const message =
          axiosErr.response?.data?.detail ??
          axiosErr.response?.data?.message ??
          axiosErr.message ??
          'Upload failed';
        updateFile(entry.id, { status: 'error', error: message });
      }
    },
    [sessionId, updateFile, onDocumentReady],
  );

  const handleFiles = useCallback(
    (fileList: FileList): void => {
      const pdfs = Array.from(fileList).filter(
        (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'),
      );
      if (pdfs.length === 0) return;

      const entries: FileEntry[] = pdfs.map((file) => ({
        id: nextId(),
        file,
        status: 'pending',
        progress: 0,
        error: null,
      }));

      setFiles((prev) => [...prev, ...entries]);
      entries.forEach((entry) => void uploadFile(entry));
    },
    [uploadFile],
  );

  const handleDragOver = (e: React.DragEvent): void => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDrop = (e: React.DragEvent): void => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    if (e.target.files) handleFiles(e.target.files);
    e.target.value = '';
  };

  return (
    <div style={styles.card}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600 }}>Upload PDFs</h3>

      <div
        style={{
          ...styles.dropZone,
          borderColor: isDragOver ? '#1a73e8' : '#bbb',
          background: isDragOver ? '#e8f0fe' : '#fafafa',
        }}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Drop PDF files here or click to choose"
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <p style={{ margin: 0, color: '#555', fontSize: 14 }}>Drag &amp; drop PDF files here</p>
        <button
          type="button"
          style={styles.chooseButton}
          onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
        >
          Choose PDF files
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        style={{ display: 'none' }}
        onChange={handleInputChange}
      />

      {files.length > 0 && (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {files.map((entry) => <FileRow key={entry.id} entry={entry} />)}
        </ul>
      )}
    </div>
  );
}

function FileRow({ entry }: { entry: FileEntry }): React.ReactElement {
  const { file, status, progress, error } = entry;

  return (
    <li style={{ display: 'flex', flexDirection: 'column', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 240 }} title={file.name}>
          {file.name}
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, color: '#fff', background: STATUS_COLORS[status], whiteSpace: 'nowrap' }}>
          {STATUS_LABELS[status]}{status === 'uploading' ? ` ${progress}%` : ''}
        </span>
      </div>
      {status === 'uploading' && (
        <div style={{ height: 4, background: '#e0e0e0', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${progress}%`, background: STATUS_COLORS.uploading, transition: 'width 0.2s' }} />
        </div>
      )}
      {status === 'error' && error && (
        <span style={{ fontSize: 12, color: STATUS_COLORS.error, marginTop: 4 }}>{error}</span>
      )}
    </li>
  );
}

const styles = {
  card: {
    background: '#fff',
    borderRadius: 8,
    padding: '16px',
    boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
    maxWidth: 420,
  },
  dropZone: {
    border: '2px dashed',
    borderRadius: 6,
    padding: '24px 16px',
    textAlign: 'center' as const,
    cursor: 'pointer',
    transition: 'border-color 0.15s, background 0.15s',
    marginBottom: 12,
  },
  chooseButton: {
    marginTop: 10,
    padding: '8px 18px',
    background: '#1a73e8',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 14,
  },
};
