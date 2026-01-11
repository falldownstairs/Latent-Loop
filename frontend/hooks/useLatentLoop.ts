'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getSSEUrl, getNotes, getTranscript, checkHealth } from '@/lib/api';
import type { TranscriptItem, PendingUpdate, SSEData, ChangeInfo } from '@/lib/types';

interface UpdateQueueItem {
  oldContent: string;
  newContent: string;
  sectionName: string | null;
  timestamp: number;
}

export function useLatentLoop(projectName: string) {
  const [markdownContent, setMarkdownContent] = useState('');
  const [pendingUpdates, setPendingUpdates] = useState<PendingUpdate[]>([]);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [groqAvailable, setGroqAvailable] = useState(false);
  const [geminiAvailable, setGeminiAvailable] = useState(false);
  const [connected, setConnected] = useState(false);
  const [animatingSection, setAnimatingSection] = useState<string | null>(null);
  
  const evtSourceRef = useRef<EventSource | null>(null);
  const updateQueueRef = useRef<UpdateQueueItem[]>([]);
  const isProcessingRef = useRef(false);
  const displayedContentRef = useRef('');

  // Helper to detect new sections
  const detectNewSection = useCallback((oldContent: string, newContent: string): string | null => {
    const headerRegex = /^#{1,3}\s+(.+)$/gm;
    const oldHeaders: string[] = [];
    let match;
    
    while ((match = headerRegex.exec(oldContent)) !== null) {
      oldHeaders.push(match[1].trim());
    }
    
    headerRegex.lastIndex = 0;
    const newHeaders: string[] = [];
    while ((match = headerRegex.exec(newContent)) !== null) {
      newHeaders.push(match[1].trim());
    }
    
    for (const header of newHeaders) {
      if (!oldHeaders.includes(header)) {
        return header;
      }
    }
    
    return null;
  }, []);

  // Process update queue
  const processNextUpdate = useCallback(() => {
    if (isProcessingRef.current || updateQueueRef.current.length === 0) return;
    
    isProcessingRef.current = true;
    const update = updateQueueRef.current.shift()!;
    
    setMarkdownContent(update.newContent);
    
    if (update.sectionName) {
      setAnimatingSection(update.sectionName);
      setTimeout(() => {
        setAnimatingSection(null);
        isProcessingRef.current = false;
        displayedContentRef.current = update.newContent;
        if (updateQueueRef.current.length > 0) {
          setTimeout(processNextUpdate, 100);
        }
      }, 500);
    } else {
      isProcessingRef.current = false;
      displayedContentRef.current = update.newContent;
      if (updateQueueRef.current.length > 0) {
        setTimeout(processNextUpdate, 100);
      }
    }
  }, []);

  // Schedule file update
  const scheduleFileUpdate = useCallback((oldContent: string, newContent: string, sectionName: string | null) => {
    updateQueueRef.current.push({
      oldContent,
      newContent,
      sectionName,
      timestamp: Date.now()
    });
    processNextUpdate();
  }, [processNextUpdate]);

  // Handle file updated event
  const handleFileUpdated = useCallback((data: SSEData) => {
    const oldContent = displayedContentRef.current || markdownContent;
    const newContent = data.content || '';
    
    let sectionName: string | null = data.section || null;
    
    if (!sectionName || sectionName === 'None') {
      sectionName = data.change_info?.target_section || null;
    }
    
    if (!sectionName || sectionName === 'None') {
      sectionName = detectNewSection(oldContent, newContent);
    }
    
    scheduleFileUpdate(oldContent, newContent, sectionName);
  }, [markdownContent, detectNewSection, scheduleFileUpdate]);

  // Connect SSE
  const connectSSE = useCallback(() => {
    if (evtSourceRef.current) {
      evtSourceRef.current.close();
    }

    const evtSource = new EventSource(getSSEUrl(projectName));
    evtSourceRef.current = evtSource;

    evtSource.onopen = () => {
      console.log('SSE connected');
      setConnected(true);
    };

    evtSource.onmessage = (event) => {
      try {
        const data: SSEData = JSON.parse(event.data);

        if (data.type === 'init') {
          setMarkdownContent(data.content || '');
          displayedContentRef.current = data.content || '';
          setPendingUpdates(Array.isArray(data.pending) ? data.pending : []);
          if (data.transcript) {
            setTranscript(data.transcript);
          }
        } else if (data.type === 'file_updated') {
          handleFileUpdated(data);
        } else if (data.type === 'pending_update' && data.pending && !Array.isArray(data.pending)) {
          setPendingUpdates(prev => [...prev, data.pending as PendingUpdate]);
        } else if (data.type === 'pending_resolved') {
          setPendingUpdates(prev => prev.filter(p => p.id !== data.pending_id));
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    evtSource.onerror = () => {
      evtSource.close();
      setConnected(false);
      setTimeout(() => connectSSE(), 3000);
    };
  }, [projectName, handleFileUpdated]);

  // Load initial state
  const loadInitialState = useCallback(async () => {
    try {
      const [notesData, transcriptData, healthData] = await Promise.all([
        getNotes(projectName),
        getTranscript(projectName),
        checkHealth(projectName)
      ]);

      setMarkdownContent(notesData.content || `# ${projectName}\n`);
      displayedContentRef.current = notesData.content || `# ${projectName}\n`;
      setPendingUpdates(notesData.pending_updates || []);
      setTranscript(transcriptData.transcript || []);
      setGroqAvailable(healthData.groq_available);
      setGeminiAvailable(healthData.gemini_available);
    } catch (e) {
      console.error('Failed to load initial state:', e);
      setMarkdownContent(`# ${projectName}\n`);
    }
  }, [projectName]);

  // Initialize
  useEffect(() => {
    loadInitialState().then(() => connectSSE());

    return () => {
      if (evtSourceRef.current) {
        evtSourceRef.current.close();
      }
    };
  }, [projectName, loadInitialState, connectSSE]);

  // Add transcript item
  const addTranscriptItem = useCallback((text: string, timestamp?: string) => {
    const item: TranscriptItem = {
      text,
      timestamp: timestamp || new Date().toISOString()
    };
    setTranscript(prev => [...prev, item]);
  }, []);

  return {
    markdownContent,
    pendingUpdates,
    setPendingUpdates,
    transcript,
    addTranscriptItem,
    groqAvailable,
    geminiAvailable,
    connected,
    animatingSection,
    loadInitialState,
    connectSSE
  };
}
