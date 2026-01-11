/**
 * Latent Loop - Audio Recording
 * Handles continuous voice recording with chunked processing
 */

// --- RECORDING CONTROL ---
async function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        await startRecording();
    }
}

async function startRecording() {
    try {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        chunkCounter = 0;
        isRecording = true;
        
        // Start first recording session
        startNewRecordingSession();
        
        // Set up interval to cycle recording sessions every 10 seconds
        chunkInterval = setInterval(() => {
            if (!isRecording) return;
            cycleRecordingSession();
        }, CHUNK_DURATION);
        
        recordBtn.classList.add('bg-red-600');
        recordBtn.classList.remove('from-blue-600', 'to-purple-600');
        recordText.textContent = 'Recording...';
        micIcon.classList.add('recording-indicator');
        
        // Show continuous recording indicator with progress bar
        addChunkStatusIndicator();
        startProgressBar();
        
    } catch (err) {
        console.error('Microphone access error:', err);
        alert('Could not access microphone.');
    }
}

function stopRecording() {
    if (!isRecording) return;
    
    // Clear intervals first
    if (chunkInterval) {
        clearInterval(chunkInterval);
        chunkInterval = null;
    }
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    
    isRecording = false;
    
    // Stop the current MediaRecorder session (triggers onstop and processes remaining audio)
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    
    // Stop the audio stream
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
    
    recordBtn.classList.remove('bg-red-600');
    recordBtn.classList.add('from-blue-600', 'to-purple-600');
    recordText.textContent = 'Start Continuous Recording';
    micIcon.classList.remove('recording-indicator');
    
    removeChunkStatusIndicator();
}

// --- RECORDING SESSIONS ---
function startNewRecordingSession() {
    // Create a new MediaRecorder for this session
    mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
    audioChunks = [];
    chunkStartTime = Date.now();
    
    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
            audioChunks.push(e.data);
        }
    };
    
    mediaRecorder.onstop = () => {
        // When this session stops, process the complete audio
        if (audioChunks.length > 0) {
            chunkCounter++;
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            if (audioBlob.size > 1000) {
                processChunkAsync(audioBlob, chunkCounter);
            }
            audioChunks = [];
        }
    };
    
    mediaRecorder.start();
}

function cycleRecordingSession() {
    if (!isRecording || !mediaRecorder) return;
    
    // Stop current session (triggers onstop which processes the audio)
    if (mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    
    // Start a new session immediately
    startNewRecordingSession();
}

// --- PROGRESS BAR ---
function startProgressBar() {
    // Update progress bar every 100ms
    progressInterval = setInterval(() => {
        const elapsed = Date.now() - chunkStartTime;
    const progress = Math.min((elapsed / CHUNK_DURATION) * 100, 100);
        const progressBar = document.getElementById('chunk-progress-bar');
        const progressText = document.getElementById('chunk-progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        if (progressText) {
            const secondsLeft = Math.max(0, Math.ceil((CHUNK_DURATION - elapsed) / 1000));
            progressText.textContent = `Next chunk in ${secondsLeft}s`;
        }
    }, 100);
}

// --- CHUNK PROCESSING ---
async function processChunkAsync(audioBlob, chunkNum) {
    const transcriptId = `chunk-${chunkNum}-${Date.now()}`;
    processingChunks.add(transcriptId);
    updateChunkStatus();
    
    addTranscriptItem(`🎤 Chunk #${chunkNum} transcribing...`, 'processing', transcriptId);
    
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, `chunk-${chunkNum}.webm`);
        
        // Send audio for transcription + queue processing
        const response = await fetch(`/api/audio?project=${encodeURIComponent(projectName)}&chunk=${chunkNum}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (result.status === 'queued') {
            // Successfully transcribed and queued
            updateTranscriptItem(transcriptId, result.transcription, 'queued', `queued #${result.chunk_num}`);
            console.log(`Chunk #${chunkNum} queued with ID: ${result.request_id}`);
        } else if (result.error) {
            updateTranscriptItem(transcriptId, result.error, 'error', 'failed');
        }
    } catch (err) {
        console.error(`Chunk ${chunkNum} processing error:`, err);
        updateTranscriptItem(transcriptId, `Chunk #${chunkNum} failed to process`, 'error', 'error');
    } finally {
        processingChunks.delete(transcriptId);
        updateChunkStatus();
    }
}

// --- STATUS INDICATOR ---
function addChunkStatusIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'chunk-status';
    indicator.className = 'fixed bottom-4 right-4 bg-gray-900 border border-purple-600 rounded-lg px-4 py-3 text-sm shadow-lg z-50 min-w-64';
    indicator.innerHTML = `
        <div class="flex items-center gap-3 mb-2">
            <div class="w-3 h-3 bg-red-500 rounded-full recording-indicator"></div>
            <span class="font-medium">Recording continuously</span>
            <span id="processing-count" class="text-purple-400 text-xs">(0 processing)</span>
        </div>
        <div class="mb-1">
            <div class="flex justify-between text-xs text-gray-400 mb-1">
                <span id="chunk-progress-text">Next chunk in 10s</span>
                <span>Chunk #<span id="chunk-number">1</span></span>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
                <div id="chunk-progress-bar" class="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-100" style="width: 0%"></div>
            </div>
        </div>
    <div class="text-xs text-gray-500">Audio sent every 10 seconds</div>
    `;
    document.body.appendChild(indicator);
}

function removeChunkStatusIndicator() {
    const indicator = document.getElementById('chunk-status');
    if (indicator) {
        indicator.remove();
    }
}

function updateChunkStatus() {
    const countEl = document.getElementById('processing-count');
    const chunkNumEl = document.getElementById('chunk-number');
    
    if (countEl) {
        const count = processingChunks.size;
        countEl.textContent = `(${count} processing)`;
        countEl.className = count > 0 ? 'text-amber-400 animate-pulse text-xs' : 'text-purple-400 text-xs';
    }
    
    if (chunkNumEl) {
        chunkNumEl.textContent = chunkCounter + 1;
    }
}
