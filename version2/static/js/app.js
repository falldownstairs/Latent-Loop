/**
 * Latent Loop - Main Application
 * Initialization and event handlers
 */

// --- INITIALIZATION ---
async function init() {
    // Set up project input
    projectInput.value = projectName;
    projectInput.addEventListener('change', () => {
        projectName = projectInput.value.trim() || 'My Project';
        localStorage.setItem('projectName', projectName);
        restartProjectView();
    });
    
    // Check API status
    await checkHealth();
    
    // Load initial state via REST first (more reliable)
    await loadInitialState();
    
    // Then connect to SSE for updates
    connectSSE();
}

// --- EVENT HANDLERS ---

// Text input handler
textInput.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter' && textInput.value.trim()) {
        const text = textInput.value.trim();
        textInput.value = '';
        textInput.disabled = true;
        
        await processTextInput(text);
        
        textInput.disabled = false;
        textInput.focus();
    }
});

// --- VIEW TOGGLE ---
function toggleView() {
    showRawView = !showRawView;
    
    if (showRawView) {
        renderedView.classList.add('hidden');
        rawView.classList.remove('hidden');
        viewToggle.textContent = 'Show Rendered';
    } else {
        renderedView.classList.remove('hidden');
        rawView.classList.add('hidden');
        viewToggle.textContent = 'Show Raw';
    }
}

// --- GLOBAL ACTIONS ---
async function exportNotes() {
    window.open(`/api/export?project=${encodeURIComponent(projectName)}`, '_blank');
}

async function clearAll() {
    if (!confirm('Clear all notes? This cannot be undone.')) return;
    
    try {
        await fetch(`/api/clear?project=${encodeURIComponent(projectName)}`, { method: 'POST' });
    } catch (e) {
        console.error('Failed to clear notes:', e);
    }
}

async function resolvePending(pendingId, action) {
    try {
        const response = await fetch(`/api/pending/${pendingId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, project: projectName })
        });
        const result = await response.json();
        
        if (result.status === 'success' || result.status === 'rejected') {
            pendingUpdates = pendingUpdates.filter(p => p.id !== pendingId);
            renderPending();
        }
    } catch (e) {
        console.error('Failed to resolve pending update:', e);
    }
}

// --- START APPLICATION ---
init();
