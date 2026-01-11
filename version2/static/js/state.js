/**
 * Latent Loop - Application State
 * Global state and DOM element references
 */

// --- STATE ---
let markdownContent = '';
let pendingUpdates = [];
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let showRawView = false;
let changedLines = [];
let projectName = localStorage.getItem('projectName') || 'My Project';
let chunkInterval = null;
let chunkCounter = 0;
let processingChunks = new Set();
let evtSource = null;

// --- CONSTANTS ---
const CHUNK_DURATION = 10000; // 10 seconds
let chunkStartTime = 0;
let progressInterval = null;
let audioStream = null;

// --- DOM ELEMENTS ---
const textInput = document.getElementById('text-input');
const transcriptContainer = document.getElementById('transcript-container');
const markdownContentEl = document.getElementById('markdown-content');
const rawContentEl = document.getElementById('raw-content');
const renderedView = document.getElementById('rendered-view');
const rawView = document.getElementById('raw-view');
const pendingSection = document.getElementById('pending-section');
const pendingList = document.getElementById('pending-list');
const pendingBadge = document.getElementById('pending-badge');
const pendingCountEl = document.getElementById('pending-count');
const recordBtn = document.getElementById('record-btn');
const recordText = document.getElementById('record-text');
const micIcon = document.getElementById('mic-icon');
const viewToggle = document.getElementById('view-toggle');
const projectInput = document.getElementById('project-input');
