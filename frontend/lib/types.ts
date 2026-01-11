export interface TranscriptItem {
  text: string;
  timestamp: string;
}

export interface PendingUpdate {
  id: string;
  transcript: string;
  matched_section: string | null;
  similarity: number;
  suggested_action: string;
  reason: string;
  timestamp: string;
}

export interface ChangeInfo {
  target_section?: string;
  changed_lines?: number[];
  added_lines?: number[];
  total_changes?: number;
}

export interface SSEData {
  type: 'init' | 'file_updated' | 'pending_update' | 'pending_resolved';
  content?: string;
  sections?: unknown[];
  transcript?: TranscriptItem[];
  pending?: PendingUpdate[] | PendingUpdate;
  pending_id?: string;
  section?: string;
  change_info?: ChangeInfo;
  action?: string;
}

export interface HealthStatus {
  groq_available: boolean;
  gemini_available: boolean;
}

export interface NotesResponse {
  content: string;
  pending_updates?: PendingUpdate[];
}

export interface TranscriptResponse {
  transcript: TranscriptItem[];
}

export interface AudioResponse {
  status: string;
  request_id?: string;
  transcription?: string;
  error?: string;
  chunk_num?: number;
}

export interface ProcessResponse {
  status: string;
  pending_id?: string;
  reason?: string;
  action?: string;
  error?: string;
}
