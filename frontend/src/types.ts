/** Domain types shared across the frontend. */

export interface Citation {
  chunk_id: string;
  filename: string;
  page_number: number;
  chunk_text: string;
}

export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface Document {
  docId: string;
  filename: string;
}

export interface SessionResponse {
  session_id: string;
  created_at: string;
}

export interface UploadResponse {
  doc_id: string;
  filename: string;
  status: 'ready' | 'error';
  chunk_count: number;
  error_message: string | null;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  session_id: string;
  question: string;
  error?: string;
  message?: string;
}

export type FileStatus = 'pending' | 'uploading' | 'ready' | 'error';

export interface FileEntry {
  id: number;
  file: File;
  status: FileStatus;
  progress: number;
  error: string | null;
}
