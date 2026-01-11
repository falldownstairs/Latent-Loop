'use client';

import type { TranscriptItem } from '@/lib/types';

interface TranscriptListProps {
  transcript: TranscriptItem[];
  processingItems: Map<string, { text: string; status: string; message?: string }>;
}

export function TranscriptList({ transcript, processingItems }: TranscriptListProps) {
  if (transcript.length === 0 && processingItems.size === 0) {
    return (
      <p className="text-gray-600 text-sm italic">Waiting for input...</p>
    );
  }

  return (
    <>
      {transcript.map((t, i) => (
        <div 
          key={`${t.timestamp}-${i}`} 
          className="transcript-item text-gray-400 text-sm py-2 border-b border-gray-800/50"
        >
          <p>&quot;{t.text}&quot;</p>
          <span className="text-xs text-gray-600">
            {new Date(t.timestamp).toLocaleTimeString()}
          </span>
        </div>
      ))}
      {Array.from(processingItems.entries()).map(([id, item]) => (
        <div 
          key={id} 
          className="transcript-item text-gray-400 text-sm py-2 border-b border-gray-800/50"
        >
          <p className="transcript-text">&quot;{item.text}&quot;</p>
          <span className={`ml-2 text-xs ${
            item.status === 'processing' ? 'text-blue-400 animate-pulse' :
            item.status === 'queued' ? 'text-purple-400' :
            item.status === 'error' ? 'text-red-400' :
            item.status === 'success' ? 'text-green-400' :
            'text-gray-400'
          }`}>
            {item.status === 'processing' ? 'processing...' :
             item.status === 'queued' ? `⏳ ${item.message}` :
             item.status === 'error' ? `✗ ${item.message}` :
             item.status === 'success' ? `✓ ${item.message}` :
             item.message}
          </span>
          <span className="text-xs text-gray-600 block">
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      ))}
    </>
  );
}
