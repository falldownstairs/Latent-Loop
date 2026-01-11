/**
 * Latent Loop - SSE & API Communication
 */

function connectSSE() {
    if (evtSource) {
        evtSource.close();
    }
    
    evtSource = new EventSource(`/api/stream?project=${encodeURIComponent(projectName)}`);
    
    evtSource.onopen = () => console.log('SSE connected');
    
    evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'init') {
                markdownContent = data.content;
                pendingUpdates = data.pending || [];
                renderMarkdown();
                renderPending();
                renderTranscript(data.transcript);
            } else if (data.type === 'file_updated') {
                handleFileUpdated(data);
            } else if (data.type === 'pending_update') {
                pendingUpdates.push(data.pending);
                renderPending();
            } else if (data.type === 'pending_resolved') {
                pendingUpdates = pendingUpdates.filter(p => p.id !== data.pending_id);
                renderPending();
            }
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };
    
    evtSource.onerror = () => {
        evtSource.close();
        setTimeout(connectSSE, 3000);
    };
}

function handleFileUpdated(data) {
    const oldContent = markdownContent;
    const newContent = data.content;
    
    // Find section to animate
    let sectionName = data.section;
    
    if (!sectionName || sectionName === 'None') {
        sectionName = data.change_info?.target_section;
    }
    
    if (!sectionName || sectionName === 'None') {
        sectionName = detectNewSection(oldContent, newContent);
    }
    
    // Use the queued update system to prevent animation conflicts
    // This ensures current animation completes before new one starts
    // Note: markdownContent is updated inside scheduleFileUpdate/processNextUpdate
    scheduleFileUpdate(oldContent, newContent, sectionName);
}

async function loadInitialState() {
    try {
        const data = await fetch(`/api/notes?project=${encodeURIComponent(projectName)}`).then(r => r.json());
        markdownContent = data.content || `# ${projectName}\n`;
        pendingUpdates = data.pending_updates || [];
        renderMarkdown();
        renderPending();
        
        const transcriptData = await fetch(`/api/transcript?project=${encodeURIComponent(projectName)}`).then(r => r.json());
        renderTranscript(transcriptData.transcript || []);
    } catch (e) {
        console.error('Failed to load initial state:', e);
        markdownContent = `# ${projectName}\n`;
        renderMarkdown();
    }
}

async function checkHealth() {
    try {
        const health = await fetch(`/health?project=${encodeURIComponent(projectName)}`).then(r => r.json());
        
        if (health.groq_available) {
            document.querySelector('#status-groq span:first-child').classList.replace('bg-gray-600', 'bg-green-500');
        }
        if (health.gemini_available) {
            document.querySelector('#status-gemini span:first-child').classList.replace('bg-gray-600', 'bg-green-500');
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}

async function processTextInput(text) {
    const transcriptId = addTranscriptItem(text, 'processing');
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, project: projectName })
        });
        
        const result = await response.json();
        
        if (result.status === 'pending') {
            updateTranscriptItem(transcriptId, text, 'pending', result.reason);
        } else if (result.status === 'success') {
            updateTranscriptItem(transcriptId, text, 'success', result.action);
        } else {
            updateTranscriptItem(transcriptId, text, 'error', result.error || 'Unknown error');
        }
    } catch (err) {
        updateTranscriptItem(transcriptId, text, 'error', 'Failed to process');
    }
}

async function restartProjectView() {
    if (evtSource) evtSource.close();
    await loadInitialState();
    connectSSE();
}
