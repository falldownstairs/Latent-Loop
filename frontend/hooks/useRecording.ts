'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { processAudio } from '@/lib/api';

const CHUNK_DURATION = 10000; // 10 seconds

interface UseRecordingOptions {
  projectName: string;
  onTranscript?: (text: string, chunkNum: number, status: 'processing' | 'queued' | 'error') => void;
}

export function useRecording({ projectName, onTranscript }: UseRecordingOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [chunkCounter, setChunkCounter] = useState(0);
  const [processingCount, setProcessingCount] = useState(0);
  const [progress, setProgress] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(10);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chunkIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const chunkStartTimeRef = useRef(0);
  const chunkCounterRef = useRef(0);

  // Process a chunk of audio
  const processChunkAsync = useCallback(async (audioBlob: Blob, chunkNum: number) => {
    setProcessingCount(prev => prev + 1);
    onTranscript?.(`🎤 Chunk #${chunkNum} transcribing...`, chunkNum, 'processing');

    try {
      const result = await processAudio(audioBlob, projectName, chunkNum);

      if (result.status === 'queued' && result.transcription) {
        onTranscript?.(result.transcription, chunkNum, 'queued');
        console.log(`Chunk #${chunkNum} queued with ID: ${result.request_id}`);
      } else if (result.error) {
        onTranscript?.(result.error, chunkNum, 'error');
      }
    } catch (err) {
      console.error(`Chunk ${chunkNum} processing error:`, err);
      onTranscript?.(`Chunk #${chunkNum} failed to process`, chunkNum, 'error');
    } finally {
      setProcessingCount(prev => prev - 1);
    }
  }, [projectName, onTranscript]);

  // Start a new recording session
  const startNewRecordingSession = useCallback(() => {
    if (!audioStreamRef.current) return;

    const mediaRecorder = new MediaRecorder(audioStreamRef.current, { mimeType: 'audio/webm' });
    mediaRecorderRef.current = mediaRecorder;
    audioChunksRef.current = [];
    chunkStartTimeRef.current = Date.now();

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunksRef.current.push(e.data);
      }
    };

    mediaRecorder.onstop = () => {
      if (audioChunksRef.current.length > 0) {
        chunkCounterRef.current++;
        setChunkCounter(chunkCounterRef.current);
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (audioBlob.size > 1000) {
          processChunkAsync(audioBlob, chunkCounterRef.current);
        }
        audioChunksRef.current = [];
      }
    };

    mediaRecorder.start();
  }, [processChunkAsync]);

  // Cycle recording session
  const cycleRecordingSession = useCallback(() => {
    if (!mediaRecorderRef.current) return;

    if (mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    startNewRecordingSession();
  }, [startNewRecordingSession]);

  // Start progress bar
  const startProgressBar = useCallback(() => {
    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - chunkStartTimeRef.current;
      const prog = Math.min((elapsed / CHUNK_DURATION) * 100, 100);
      setProgress(prog);
      setSecondsLeft(Math.max(0, Math.ceil((CHUNK_DURATION - elapsed) / 1000)));
    }, 100);
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      audioChunksRef.current = [];
      chunkCounterRef.current = 0;
      setChunkCounter(0);
      setIsRecording(true);

      startNewRecordingSession();

      chunkIntervalRef.current = setInterval(() => {
        cycleRecordingSession();
      }, CHUNK_DURATION);

      startProgressBar();
    } catch (err) {
      console.error('Microphone access error:', err);
      alert('Could not access microphone.');
    }
  }, [startNewRecordingSession, cycleRecordingSession, startProgressBar]);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (chunkIntervalRef.current) {
      clearInterval(chunkIntervalRef.current);
      chunkIntervalRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }

    setIsRecording(false);
    setProgress(0);
    setSecondsLeft(10);

    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      audioStreamRef.current = null;
    }
  }, []);

  // Toggle recording
  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chunkIntervalRef.current) {
        clearInterval(chunkIntervalRef.current);
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return {
    isRecording,
    chunkCounter,
    processingCount,
    progress,
    secondsLeft,
    toggleRecording,
    startRecording,
    stopRecording
  };
}
