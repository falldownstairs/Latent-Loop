/**
 * Latent Loop - Transcript UI
 * Handles transcript list and pending updates UI
 */

// --- TRANSCRIPT RENDERING ---
function renderTranscript(transcript) {
    if (!transcript || transcript.length === 0) {
        transcriptContainer.innerHTML = '<p class="text-gray-600 text-sm italic">Waiting for input...</p>';
        return;
    }
    
    transcriptContainer.innerHTML = transcript.map(t => `
        <div class="transcript-item text-gray-400 text-sm py-2 border-b border-gray-800/50">
            <p>"${t.text}"</p>
            <span class="text-xs text-gray-600">${new Date(t.timestamp).toLocaleTimeString()}</span>
        </div>
    `).join('');
    
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function addTranscriptItem(text, status = '', itemId = null) {
    const id = itemId || 'transcript-' + Date.now();
    const item = document.createElement('div');
    item.className = 'transcript-item text-gray-400 text-sm py-2 border-b border-gray-800/50';
    item.id = id;
    
    let statusBadge = '';
    if (status === 'processing') {
        statusBadge = '<span class="status-badge ml-2 text-xs text-blue-400 animate-pulse">processing...</span>';
    }
    
    item.innerHTML = `
        <p class="transcript-text">"${text}"</p>
        ${statusBadge}
        <span class="text-xs text-gray-600">${new Date().toLocaleTimeString()}</span>
    `;
    
    const waiting = transcriptContainer.querySelector('.italic');
    if (waiting) waiting.remove();
    
    transcriptContainer.appendChild(item);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
    
    return id;
}

function updateTranscriptItem(itemId, text, status, message) {
    const item = document.getElementById(itemId);
    if (!item) return;
    
    // Update text
    const textEl = item.querySelector('.transcript-text');
    if (textEl) {
        textEl.innerHTML = `"${text}"`;
    }
    
    // Update or add status badge
    let badge = item.querySelector('.status-badge');
    if (!badge) {
        badge = document.createElement('span');
        badge.className = 'status-badge ml-2 text-xs';
        const timeEl = item.querySelector('.text-gray-600');
        if (timeEl) {
            item.insertBefore(badge, timeEl);
        } else {
            item.appendChild(badge);
        }
    }
    
    badge.classList.remove('animate-pulse', 'text-blue-400', 'text-green-400', 'text-amber-400', 'text-red-400', 'text-purple-400');
    
    if (status === 'success') {
        badge.className = 'status-badge ml-2 text-xs text-green-400';
        badge.textContent = `✓ ${message}`;
    } else if (status === 'queued') {
        badge.className = 'status-badge ml-2 text-xs text-purple-400';
        badge.textContent = `⏳ ${message}`;
    } else if (status === 'pending') {
        badge.className = 'status-badge ml-2 text-xs text-amber-400';
        badge.textContent = `⚠ ${message}`;
    } else if (status === 'error') {
        badge.className = 'status-badge ml-2 text-xs text-red-400';
        badge.textContent = `✗ ${message}`;
    } else {
        badge.className = 'status-badge ml-2 text-xs text-gray-400';
        badge.textContent = message;
    }
}

// --- PENDING UPDATES ---
function renderPending() {
    if (pendingUpdates.length === 0) {
        pendingSection.classList.add('hidden');
        pendingBadge.classList.add('hidden');
        pendingBadge.classList.remove('flex');
        return;
    }
    
    pendingSection.classList.remove('hidden');
    pendingBadge.classList.remove('hidden');
    pendingBadge.classList.add('flex');
    pendingCountEl.textContent = pendingUpdates.length;
    
    pendingList.innerHTML = pendingUpdates.map(p => `
        <div class="pending-card bg-gray-900 rounded-lg p-3 border border-amber-900/50">
            <p class="text-sm text-gray-300 mb-2">"${p.transcript}"</p>
            <p class="text-xs text-amber-400 mb-2">${p.reason}</p>
            ${p.matched_section ? `<p class="text-xs text-gray-500 mb-2">Matched: ${p.matched_section} (${(p.similarity * 100).toFixed(0)}%)</p>` : ''}
            <div class="flex gap-2">
                <button onclick="resolvePending('${p.id}', 'approve')" class="px-2 py-1 text-xs bg-green-900/50 hover:bg-green-900 rounded transition">
                    ✓ ${p.matched_section ? 'Update Section' : 'Create New'}
                </button>
                ${p.matched_section ? `
                    <button onclick="resolvePending('${p.id}', 'create_new')" class="px-2 py-1 text-xs bg-blue-900/50 hover:bg-blue-900 rounded transition">
                        + New Section
                    </button>
                ` : ''}
                <button onclick="resolvePending('${p.id}', 'reject')" class="px-2 py-1 text-xs bg-red-900/50 hover:bg-red-900 rounded transition">
                    ✗ Reject
                </button>
            </div>
        </div>
    `).join('');
}
