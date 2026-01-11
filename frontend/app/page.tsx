'use client';

import { useState, useCallback, useRef } from 'react';
import { Header } from '@/components/Header';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { TranscriptList } from '@/components/TranscriptList';
import { PendingList } from '@/components/PendingList';
import { RecordingStatus } from '@/components/RecordingStatus';
import { useLatentLoop } from '@/hooks/useLatentLoop';
import { useRecording } from '@/hooks/useRecording';
import { resolvePending, clearNotes } from '@/lib/api';

export default function Home() {
  const [projectName, setProjectName] = useState('my-project');
  const [showRaw, setShowRaw] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [processingItems, setProcessingItems] = useState<Map<string, { text: string; status: string; message?: string }>>(new Map());
  const textInputRef = useRef<HTMLTextAreaElement>(null);

  const {
    markdownContent,
    pendingUpdates,
    setPendingUpdates,
    transcript,
    addTranscriptItem,
    groqAvailable,
    geminiAvailable,
    animatingSection,
    loadInitialState
  } = useLatentLoop(projectName);

  // Handle transcript updates from recording
  const handleTranscript = useCallback((text: string, chunkNum: number, status: 'processing' | 'queued' | 'error') => {
    const id = `chunk-${chunkNum}`;
    setProcessingItems(prev => {
      const next = new Map(prev);
      next.set(id, { 
        text, 
        status,
        message: status === 'queued' ? 'Queued for processing' : 
                 status === 'error' ? 'Failed to process' : 
                 'Processing...'
      });
      
      // Remove completed items after a delay
      if (status === 'queued') {
        setTimeout(() => {
          setProcessingItems(p => {
            const n = new Map(p);
            n.delete(id);
            return n;
          });
        }, 3000);
      }
      
      return next;
    });
  }, []);

  const {
    isRecording,
    progress,
    chunkCounter,
    processingCount,
    secondsLeft,
    startRecording,
    stopRecording
  } = useRecording({
    projectName,
    onTranscript: handleTranscript
  });

  const handleTextSubmit = useCallback(async () => {
    const text = textInput.trim();
    if (!text || isSubmitting) return;

    setIsSubmitting(true);
    const id = `text-${Date.now()}`;
    
    setProcessingItems(prev => {
      const next = new Map(prev);
      next.set(id, { text, status: 'processing', message: 'Processing...' });
      return next;
    });
    
    setTextInput('');

    try {
      const { processText } = await import('@/lib/api');
      const result = await processText(text, projectName);
      
      setProcessingItems(prev => {
        const next = new Map(prev);
        next.set(id, { 
          text, 
          status: result.status === 'queued' ? 'queued' : 'success',
          message: result.status === 'queued' ? 'Queued for processing' : 'Sent'
        });
        return next;
      });
      
      // Add to transcript
      addTranscriptItem(text);
      
      // Remove from processing after delay
      setTimeout(() => {
        setProcessingItems(p => {
          const n = new Map(p);
          n.delete(id);
          return n;
        });
      }, 3000);
    } catch (error) {
      setProcessingItems(prev => {
        const next = new Map(prev);
        next.set(id, { text, status: 'error', message: 'Failed to process' });
        return next;
      });
      console.error('Text processing error:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [textInput, isSubmitting, projectName, addTranscriptItem]);

  const handlePendingResolve = useCallback(async (pendingId: string, action: string) => {
    try {
      await resolvePending(pendingId, action, projectName);
      setPendingUpdates(prev => prev.filter(p => p.id !== pendingId));
    } catch (error) {
      console.error('Error resolving pending:', error);
    }
  }, [projectName, setPendingUpdates]);

  const handleExport = useCallback(() => {
    const blob = new Blob([markdownContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [markdownContent, projectName]);

  const handleClear = useCallback(async () => {
    if (!confirm('Are you sure you want to clear all notes?')) return;
    try {
      await clearNotes(projectName);
      await loadInitialState();
    } catch (error) {
      console.error('Error clearing notes:', error);
    }
  }, [projectName, loadInitialState]);

  const handleProjectChange = useCallback((name: string) => {
    setProjectName(name);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTextSubmit();
    }
  }, [handleTextSubmit]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <Header
        projectName={projectName}
        onProjectChange={handleProjectChange}
        groqAvailable={groqAvailable}
        geminiAvailable={geminiAvailable}
        pendingCount={pendingUpdates.length}
        onExport={handleExport}
        onClear={handleClear}
      />
      
      <main className="pt-20 px-6 pb-6">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-6rem)]">
          {/* Left Panel - Input & Transcript */}
          <div className="flex flex-col gap-4 min-h-0">
            {/* Input Section */}
            <div className="bg-gray-900/50 rounded-2xl p-4 border border-gray-800/50">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide">Input</h2>
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition ${
                    isRecording
                      ? 'bg-red-500 hover:bg-red-600 text-white'
                      : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white'
                  }`}
                >
                  {isRecording ? (
                    <>
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <rect x="6" y="6" width="12" height="12" rx="1" />
                      </svg>
                      Stop
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                      </svg>
                      Record
                    </>
                  )}
                </button>
              </div>
              <div className="relative">
                <textarea
                  ref={textInputRef}
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your thoughts here... (Enter to send, Shift+Enter for new line)"
                  className="w-full h-24 bg-gray-800/50 border border-gray-700 rounded-xl p-3 resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                />
                <button
                  onClick={handleTextSubmit}
                  disabled={isSubmitting || !textInput.trim()}
                  className="absolute right-3 bottom-3 p-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Pending Updates */}
            <PendingList pendingUpdates={pendingUpdates} onResolve={handlePendingResolve} />

            {/* Transcript */}
            <div className="flex-1 bg-gray-900/50 rounded-2xl p-4 border border-gray-800/50 min-h-0 overflow-hidden flex flex-col">
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Transcript</h2>
              <div className="flex-1 overflow-y-auto">
                <TranscriptList transcript={transcript} processingItems={processingItems} />
              </div>
            </div>
          </div>

          {/* Right Panel - Notes */}
          <div className="bg-gray-900/50 rounded-2xl p-4 border border-gray-800/50 min-h-0 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide">Notes</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowRaw(false)}
                  className={`px-3 py-1 text-xs rounded-lg transition ${
                    !showRaw ? 'bg-purple-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  Rendered
                </button>
                <button
                  onClick={() => setShowRaw(true)}
                  className={`px-3 py-1 text-xs rounded-lg transition ${
                    showRaw ? 'bg-purple-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  Raw
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto markdown-content">
              {showRaw ? (
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">{markdownContent}</pre>
              ) : (
                <MarkdownRenderer content={markdownContent} animatingSection={animatingSection} />
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Recording Status */}
      <RecordingStatus
        isRecording={isRecording}
        progress={progress}
        secondsLeft={secondsLeft}
        chunkCounter={chunkCounter}
        processingCount={processingCount}
      />
    </div>
  );
}
