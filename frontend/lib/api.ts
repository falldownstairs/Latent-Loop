import type { 
  HealthStatus, 
  NotesResponse, 
  TranscriptResponse, 
  AudioResponse, 
  ProcessResponse 
} from './types';

// Backend API URL - can be configured via environment variable
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5050';

export async function checkHealth(project: string): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health?project=${encodeURIComponent(project)}`);
  return res.json();
}

export async function getNotes(project: string): Promise<NotesResponse> {
  const res = await fetch(`${API_BASE}/api/notes?project=${encodeURIComponent(project)}`);
  return res.json();
}

export async function getTranscript(project: string): Promise<TranscriptResponse> {
  const res = await fetch(`${API_BASE}/api/transcript?project=${encodeURIComponent(project)}`);
  return res.json();
}

export async function processText(text: string, project: string): Promise<ProcessResponse> {
  const res = await fetch(`${API_BASE}/api/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, project })
  });
  return res.json();
}

export async function processAudio(audioBlob: Blob, project: string, chunkNum: number): Promise<AudioResponse> {
  const formData = new FormData();
  formData.append('audio', audioBlob, `chunk-${chunkNum}.webm`);
  
  const res = await fetch(
    `${API_BASE}/api/audio?project=${encodeURIComponent(project)}&chunk=${chunkNum}`,
    { method: 'POST', body: formData }
  );
  return res.json();
}

export async function resolvePending(pendingId: string, action: string, project: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/pending/${pendingId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, project })
  });
  return res.json();
}

export async function clearNotes(project: string): Promise<void> {
  await fetch(`${API_BASE}/api/clear?project=${encodeURIComponent(project)}`, { method: 'POST' });
}

export function getExportUrl(project: string): string {
  return `${API_BASE}/api/export?project=${encodeURIComponent(project)}`;
}

export function getSSEUrl(project: string): string {
  return `${API_BASE}/api/stream?project=${encodeURIComponent(project)}`;
}
