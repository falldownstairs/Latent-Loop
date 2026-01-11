'use client';

import type { PendingUpdate } from '@/lib/types';

interface PendingListProps {
  pendingUpdates: PendingUpdate[];
  onResolve: (pendingId: string, action: string) => void;
}

export function PendingList({ pendingUpdates, onResolve }: PendingListProps) {
  if (pendingUpdates.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-amber-900/50 bg-amber-950/20">
      <div className="p-4">
        <h3 className="text-xs font-medium text-amber-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Needs Context
        </h3>
        <div className="space-y-3 max-h-48 overflow-y-auto">
          {pendingUpdates.map((p) => (
            <div key={p.id} className="pending-card bg-gray-900 rounded-lg p-3 border border-amber-900/50">
              <p className="text-sm text-gray-300 mb-2">&quot;{p.transcript}&quot;</p>
              <p className="text-xs text-amber-400 mb-2">{p.reason}</p>
              {p.matched_section && (
                <p className="text-xs text-gray-500 mb-2">
                  Matched: {p.matched_section} ({Math.round(p.similarity * 100)}%)
                </p>
              )}
              <div className="flex gap-2">
                <button 
                  onClick={() => onResolve(p.id, 'approve')}
                  className="px-2 py-1 text-xs bg-green-900/50 hover:bg-green-900 rounded transition"
                >
                  ✓ {p.matched_section ? 'Update Section' : 'Create New'}
                </button>
                {p.matched_section && (
                  <button 
                    onClick={() => onResolve(p.id, 'create_new')}
                    className="px-2 py-1 text-xs bg-blue-900/50 hover:bg-blue-900 rounded transition"
                  >
                    + New Section
                  </button>
                )}
                <button 
                  onClick={() => onResolve(p.id, 'reject')}
                  className="px-2 py-1 text-xs bg-red-900/50 hover:bg-red-900 rounded transition"
                >
                  ✗ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
