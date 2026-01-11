'use client';

interface HeaderProps {
  projectName: string;
  onProjectChange: (name: string) => void;
  groqAvailable: boolean;
  geminiAvailable: boolean;
  pendingCount: number;
  onExport: () => void;
  onClear: () => void;
}

export function Header({
  projectName,
  onProjectChange,
  groqAvailable,
  geminiAvailable,
  pendingCount,
  onExport,
  onClear
}: HeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#0a0a0f]/80 backdrop-blur-xl border-b border-gray-800/50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold gradient-text">Latent Loop</h1>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">Single Source</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-300">
            <label htmlFor="project-input" className="text-gray-500 text-xs uppercase tracking-wide">Project</label>
            <input 
              id="project-input" 
              type="text" 
              value={projectName}
              onChange={(e) => onProjectChange(e.target.value)}
              className="bg-gray-900 border border-gray-700 text-sm rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-purple-500" 
              placeholder="Project name" 
            />
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className={`w-2 h-2 rounded-full ${groqAvailable ? 'bg-green-500' : 'bg-gray-600'}`}></span>
            <span>Whisper</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className={`w-2 h-2 rounded-full ${geminiAvailable ? 'bg-green-500' : 'bg-gray-600'}`}></span>
            <span>Gemini</span>
          </div>
          {pendingCount > 0 && (
            <div className="flex items-center gap-1 text-sm text-amber-400 bg-amber-900/30 px-2 py-1 rounded">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{pendingCount} pending</span>
            </div>
          )}
          <button onClick={onExport} className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg transition">
            Export
          </button>
          <button onClick={onClear} className="px-3 py-1.5 text-sm bg-red-900/50 hover:bg-red-900 rounded-lg transition">
            Clear
          </button>
        </div>
      </div>
    </header>
  );
}
