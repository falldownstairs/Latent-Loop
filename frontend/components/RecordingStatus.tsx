'use client';

interface RecordingStatusProps {
  isRecording: boolean;
  progress: number;
  secondsLeft: number;
  chunkCounter: number;
  processingCount: number;
}

export function RecordingStatus({ 
  isRecording, 
  progress, 
  secondsLeft, 
  chunkCounter, 
  processingCount 
}: RecordingStatusProps) {
  if (!isRecording) return null;

  return (
    <div className="fixed bottom-4 right-4 bg-gray-900 border border-purple-600 rounded-lg px-4 py-3 text-sm shadow-lg z-50 min-w-64">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-3 h-3 bg-red-500 rounded-full recording-indicator"></div>
        <span className="font-medium">Recording continuously</span>
        <span className={`text-xs ${processingCount > 0 ? 'text-amber-400 animate-pulse' : 'text-purple-400'}`}>
          ({processingCount} processing)
        </span>
      </div>
      <div className="mb-1">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Next chunk in {secondsLeft}s</span>
          <span>Chunk #{chunkCounter + 1}</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
          <div 
            className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-100" 
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      <div className="text-xs text-gray-500">Audio sent every 10 seconds</div>
    </div>
  );
}
