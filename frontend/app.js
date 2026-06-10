/**
 * OpenGov AI Assistant - Frontend JavaScript
 * Fixed version with proper API calls
 */

// API URL - use relative path since frontend and backend are served together
const API_BASE_URL = '';

let adminToken = '';
let selectedFile = null;

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Check for saved admin token
    const savedToken = localStorage.getItem('adminToken');
    if (savedToken) {
        adminToken = savedToken;
        showAdminUpload();
    }
    
    // Initialize file upload area
    initializeFileUpload();
    
    // Focus on question input
    setTimeout(() => {
        const questionInput = document.getElementById('question-input');
        if (questionInput) questionInput.focus();
    }, 100);
    
    // Test API connection
    testAPIConnection();
}

function testAPIConnection() {
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            console.log('API connected:', data);
            showToast('API connected successfully', 'success');
        })
        .catch(error => {
            console.error('API connection failed:', error);
            showToast('Warning: Backend not running. Please start the server.', 'warning');
        });
}

// ==================== Navigation ====================

function showSection(section) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(sec => {
        sec.classList.remove('active');
    });
    
    // Show selected section
    const sectionId = section + '-section';
    const sectionElement = document.getElementById(sectionId);
    if (sectionElement) {
        sectionElement.classList.add('active');
    }
    
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    if (event && event.target && event.target.closest('.nav-link')) {
        event.target.closest('.nav-link').classList.add('active');
    }
}

// ==================== Chat Functionality ====================

async function askQuestion() {
    console.log('askQuestion called');
    
    const questionInput = document.getElementById('question-input');
    const categorySelect = document.getElementById('category-select');
    const askButton = document.getElementById('ask-button');
    
    if (!questionInput) {
        console.error('Question input not found');
        return;
    }
    
    const question = questionInput.value.trim();
    const category = categorySelect ? categorySelect.value : 'FR';
    
    console.log('Question:', question, 'Category:', category);
    
    if (!question) {
        showToast('Please enter a question', 'warning');
        questionInput.focus();
        return;
    }
    
    // Disable button and show loading
    askButton.disabled = true;
    askButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
    
    // Add user message to chat
    addUserMessage(question);
    
    // Clear input
    questionInput.value = '';
    
    // Add loading message
    const loadingMessageId = addLoadingMessage();
    
    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                category: category
            })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Response data:', data);
        
        // Remove loading message
        removeMessage(loadingMessageId);
        
        // Add AI response
        addAIResponse(data.answer, data.sources, data.category);
        
    } catch (error) {
        console.error('Error:', error);
        removeMessage(loadingMessageId);
        addErrorMessage(error.message || 'Connection error. Please check if the server is running.');
    } finally {
        // Re-enable button
        askButton.disabled = false;
        askButton.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Ask AI';
        questionInput.focus();
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        askQuestion();
    }
}

function addUserMessage(message) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.id = messageId;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-user"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble user-bubble">
                <p class="mb-0">${escapeHtml(message)}</p>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return messageId;
}

function addAIResponse(answer, sources, category) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    messageDiv.id = messageId;
    
    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `
            <div class="sources-section mt-3">
                <h6><i class="fas fa-book me-1"></i> Sources</h6>
                ${sources.map(source => `
                    <span class="source-item">
                        <i class="fas fa-file-pdf"></i>
                        ${escapeHtml(source.source)} - Page ${source.page}
                        <span class="badge bg-light text-dark ms-1">${Math.round(source.relevance_score * 100)}% match</span>
                    </span>
                `).join('')}
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble ai-bubble">
                <div class="ai-answer">${formatAnswer(answer)}</div>
                ${sourcesHtml}
                <div class="message-actions mt-2">
                    <button class="btn btn-sm btn-outline-secondary" onclick="copyToClipboard('${messageId}')">
                        <i class="fas fa-copy me-1"></i>Copy
                    </button>
                </div>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    
    return messageId;
}

function addLoadingMessage() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return null;
    
    const messageId = 'loading-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    messageDiv.id = messageId;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble ai-bubble">
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <span class="ms-2 text-muted">Searching documents...</span>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return messageId;
}

function addErrorMessage(error) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    messageDiv.id = messageId;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble ai-bubble" style="border-left: 4px solid #f56565;">
                <p class="mb-0 text-danger">
                    <strong>Error:</strong> ${escapeHtml(error)}
                </p>
                <p class="mb-0 mt-2 text-muted small">
                    Please make sure the backend is running: python app.py
                </p>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return messageId;
}

function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }
}

function clearChat() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="message ai-message">
                <div class="message-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <div class="message-bubble ai-bubble">
                        <p class="mb-0">
                            <strong>Chat cleared!</strong> How can I help you today?
                        </p>
                    </div>
                </div>
            </div>
        `;
    }
}

function showExamples() {
    const examples = [
        "What are the responsibilities of a voucher certifying officer?",
        "What are the financial regulations for government procurement?",
        "How do I process travel claims?",
        "What is the approval process for expenditures?",
        "Explain the tender evaluation process",
        "What are the spending limits for different officers?"
    ];
    
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    messageDiv.id = messageId;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-lightbulb"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble ai-bubble">
                <p class="mb-2"><strong>Example Questions:</strong></p>
                <div class="example-questions">
                    ${examples.map(ex => `
                        <button class="example-btn" onclick="useExample('${escapeHtml(ex)}')">
                            <i class="fas fa-comment-dots me-1"></i>${ex}
                        </button>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function useExample(question) {
    const questionInput = document.getElementById('question-input');
    if (questionInput) {
        questionInput.value = question;
        questionInput.focus();
    }
}

// ==================== Admin Functionality ====================

function verifyAdmin() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value.trim();
    
    if (!token) {
        showToast('Please enter the admin token', 'warning');
        return;
    }
    
    adminToken = token;
    localStorage.setItem('adminToken', token);
    showAdminUpload();
    showToast('Login successful', 'success');
}

function showAdminUpload() {
    const adminLogin = document.getElementById('admin-login');
    const adminUpload = document.getElementById('admin-upload');
    
    if (adminLogin) adminLogin.classList.add('d-none');
    if (adminUpload) adminUpload.classList.remove('d-none');
}

function logoutAdmin() {
    adminToken = '';
    localStorage.removeItem('adminToken');
    
    const adminLogin = document.getElementById('admin-login');
    const adminUpload = document.getElementById('admin-upload');
    const adminTokenInput = document.getElementById('admin-token');
    
    if (adminLogin) adminLogin.classList.remove('d-none');
    if (adminUpload) adminUpload.classList.add('d-none');
    if (adminTokenInput) adminTokenInput.value = '';
    
    showToast('Logged out successfully', 'info');
}

function initializeFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    
    if (!uploadArea || !fileInput) return;
    
    uploadArea.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });
}

function handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Please select a PDF file', 'error');
        return;
    }
    
    selectedFile = file;
    
    const uploadArea = document.getElementById('upload-area');
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    
    uploadArea.innerHTML = `
        <div class="file-preview">
            <i class="fas fa-file-pdf"></i>
            <div class="file-info">
                <div class="file-name">${escapeHtml(file.name)}</div>
                <div class="file-size">${fileSize} MB</div>
            </div>
            <div class="remove-file" onclick="removeFile()">
                <i class="fas fa-times"></i>
            </div>
        </div>
        <p class="text-muted small mt-2 mb-0">Click to change file</p>
    `;
    
    const uploadButton = document.getElementById('upload-button');
    if (uploadButton) uploadButton.disabled = false;
}

function removeFile() {
    selectedFile = null;
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    
    const uploadArea = document.getElementById('upload-area');
    uploadArea.innerHTML = `
        <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-primary"></i>
        <p class="mb-2"><strong>Drag & drop PDF here</strong></p>
        <p class="text-muted small">or click to browse</p>
        <input type="file" id="file-input" accept=".pdf" class="d-none">
    `;
    
    const uploadButton = document.getElementById('upload-button');
    if (uploadButton) uploadButton.disabled = true;
    
    initializeFileUpload();
}

function uploadFile() {
    if (!selectedFile || !adminToken) {
        showToast('Please select a file and login', 'warning');
        return;
    }
    
    const category = document.getElementById('upload-category').value;
    const uploadButton = document.getElementById('upload-button');
    const progressDiv = document.getElementById('upload-progress');
    const resultDiv = document.getElementById('upload-result');
    
    if (progressDiv) progressDiv.classList.remove('d-none');
    if (resultDiv) resultDiv.innerHTML = '';
    if (uploadButton) uploadButton.disabled = true;
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('category', category);
    
    fetch('/admin/upload', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${adminToken}`
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'Upload failed') });
        }
        return response.json();
    })
    .then(data => {
        if (resultDiv) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <i class="fas fa-check-circle me-2"></i>
                    <strong>Success!</strong> ${data.message}<br>
                    <small>Documents processed: ${data.documents_processed} | Chunks created: ${data.chunks_created}</small>
                </div>
            `;
        }
        removeFile();
        showToast('File uploaded successfully!', 'success');
    })
    .catch(error => {
        if (resultDiv) {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <i class="fas fa-times-circle me-2"></i>
                    <strong>Error:</strong> ${escapeHtml(error.message)}
                </div>
            `;
        }
        showToast(error.message, 'error');
    })
    .finally(() => {
        if (progressDiv) progressDiv.classList.add('d-none');
        if (uploadButton) uploadButton.disabled = false;
    });
}

// ==================== Utility Functions ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatAnswer(text) {
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/\n/g, '<br>');
    formatted = formatted.replace(/^(\d+)\.\s+(.*?)$/gm, '<li>$2</li>');
    return formatted;
}

function copyToClipboard(messageId) {
    const message = document.getElementById(messageId);
    if (!message) return;
    
    const answerDiv = message.querySelector('.ai-answer');
    if (!answerDiv) return;
    
    const text = answerDiv.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        document.body.appendChild(toastContainer);
    }
    
    const toast = document.createElement('div');
    const alertClass = type === 'error' ? 'danger' : (type === 'warning' ? 'warning' : (type === 'success' ? 'success' : 'info'));
    toast.className = `alert alert-${alertClass} alert-dismissible fade show`;
    toast.style.cssText = 'min-width: 250px; animation: slideIn 0.3s ease;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 150);
    }, 3000);
}