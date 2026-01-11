/**
 * Latent Loop - Glow Animation System
 * Updates glow green to show changes
 */

// Animation state
var updateQueue = [];
var isProcessingQueue = false;
var activeTimeouts = [];
var GLOW_DURATION = 500;
var displayedContent = '';

// Core rendering
function renderMarkdownBase() {
    var html = marked.parse(markdownContent);
    markdownContentEl.innerHTML = html;
    rawContentEl.textContent = markdownContent;
    displayedContent = markdownContent;
}

function renderMarkdown() {
    renderMarkdownBase();
}

// Timeout management
function scheduleTimeout(fn, delay) {
    var id = setTimeout(function() {
        var idx = activeTimeouts.indexOf(id);
        if (idx > -1) activeTimeouts.splice(idx, 1);
        fn();
    }, delay);
    activeTimeouts.push(id);
    return id;
}

// Queue system
function scheduleFileUpdate(oldContent, newContent, sectionName) {
    updateQueue.push({
        oldContent: oldContent,
        newContent: newContent,
        sectionName: sectionName,
        timestamp: Date.now()
    });
    processNextUpdate();
}

function processNextUpdate() {
    if (isProcessingQueue || updateQueue.length === 0) return;
    
    isProcessingQueue = true;
    var update = updateQueue.shift();
    
    // Update content and DOM first, then animate
    markdownContent = update.newContent;
    rawContentEl.textContent = markdownContent;
    renderMarkdownBase();
    
    if (update.sectionName) {
        animateSection(update.sectionName, function() {
            finishProcessing();
        });
    } else {
        finishProcessing();
    }
}

function finishProcessing() {
    isProcessingQueue = false;
    displayedContent = markdownContent;
    if (updateQueue.length > 0) {
        scheduleTimeout(processNextUpdate, 100);
    }
}

// Section detection
function detectNewSection(oldContent, newContent) {
    // Match any header #, ##, ###
    var headerRegex = /^#{1,3}\s+(.+)$/gm;
    var oldHeaders = [];
    var match;
    
    while ((match = headerRegex.exec(oldContent)) !== null) {
        oldHeaders.push(match[1].trim());
    }
    
    // Reset regex for next search
    headerRegex.lastIndex = 0;
    var newHeaders = [];
    while ((match = headerRegex.exec(newContent)) !== null) {
        newHeaders.push(match[1].trim());
    }
    
    // Find first headers that didn't exist before
    for (var i = 0; i < newHeaders.length; i++) {
        if (oldHeaders.indexOf(newHeaders[i]) === -1) {
            return newHeaders[i];
        }
    }
    
    // No new header found
    return null;
}

function findHeaderElement(sectionName) {
    if (!sectionName) return null;
    var headers = markdownContentEl.querySelectorAll('h1, h2, h3');
    var bestMatch = null;
    var bestScore = -1;
    var search = sectionName.toLowerCase().trim();
    
    headers.forEach(function(h) {
        var text = h.textContent.toLowerCase().trim();
        var score = 0;
        
        if (text === search) {
            score = 100; // Perfect match
        } else if (text.startsWith(search) || search.startsWith(text)) {
            score = 50; // Strong match (one starts with other)
        } else if (text.indexOf(search) !== -1 || search.indexOf(text) !== -1) {
            score = 10; // Fuzzy match (substring)
        }
        
        // Small penalty for being further down the file if scores are tied
        if (score > bestScore) {
            bestScore = score;
            bestMatch = h;
        }
    });
    
    return bestScore > 0 ? bestMatch : null;
}

function getSectionElements(header) {
    var elements = [];
    if (!header) return elements;
    var sibling = header.nextElementSibling;
    while (sibling && ['H1', 'H2', 'H3'].indexOf(sibling.tagName) === -1) {
        elements.push(sibling);
        sibling = sibling.nextElementSibling;
    }
    return elements;
}

// Animation
function animateSection(sectionName, onComplete) {
    var header = findHeaderElement(sectionName);
    
    // Safety net: if provided section name not found (e.g. renamed), 
    // try to detect the change automatically
    if (!header) {
        var detectedName = detectNewSection(displayedContent, markdownContent);
        header = findHeaderElement(detectedName);
    }
    
    if (!header) {
        if (onComplete) onComplete();
        return;
    }
    
    scrollToElement(header);
    var elements = getSectionElements(header);
    
    // Add green glow to header and all elements
    header.classList.add('glow-green');
    elements.forEach(function(el) { el.classList.add('glow-green'); });
    
    // Remove glow after duration
    scheduleTimeout(function() {
        header.classList.remove('glow-green');
        elements.forEach(function(el) { el.classList.remove('glow-green'); });
        if (onComplete) onComplete();
    }, GLOW_DURATION);
}

function scrollToElement(element) {
    var scrollContainer = document.getElementById('rendered-view');
    if (scrollContainer && element) {
        var containerRect = scrollContainer.getBoundingClientRect();
        var elementRect = element.getBoundingClientRect();
        var scrollTop = elementRect.top - containerRect.top + scrollContainer.scrollTop - 60;
        scrollContainer.scrollTo({ top: scrollTop, behavior: 'smooth' });
    }
}
