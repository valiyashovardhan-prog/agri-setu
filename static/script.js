// --- CONFIGURATION ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const synthesis = window.speechSynthesis;

// 1. Browser Check
if (!SpeechRecognition) {
    console.error("CRITICAL: This browser does not support Web Speech API.");
}

// Fix for Chrome voice loading bug
if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

const recognition = new SpeechRecognition();
recognition.lang = 'en-IN'; 
recognition.continuous = false;
recognition.interimResults = false;

// STATE TRACKER
let activeMode = null; 
let bubbleTimer = null;
let isAIProcessing = false; 
let lastRequestTime = 0;    

// ============================================
//  EVENT LISTENERS
// ============================================

recognition.onstart = function() {
    if (activeMode === 'mascot') {
        updateMascotState('listening');
        showBubble("Listening...");
    }
};

recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript;
    console.log("Heard:", transcript);

    const now = Date.now();
    if (now - lastRequestTime < 2000) { console.log("Ignored: Too fast."); return; }
    
    if (isAIProcessing) return;

    if (activeMode === 'dashboard' || activeMode === 'chat') {
        const chatInput = document.getElementById('userInput');
        if (chatInput) chatInput.value = transcript;
        
        const chatWindow = document.getElementById('chatWindow');
        if (chatWindow && chatWindow.style.display !== 'flex') {
            toggleChat();
        }
        
        sendMessage(); 
        
        const statusMsg = document.getElementById('statusMsg');
        if (statusMsg) statusMsg.innerText = "Heard: " + transcript;
        
        resetMics();
        activeMode = null;
    }
    else if (activeMode === 'mascot') {
        showBubble("You: " + transcript);
        sendMascotMessage(transcript);
    }
};

recognition.onend = function() {
    if (!isAIProcessing) {
        resetMics();
        if (activeMode === 'mascot') updateMascotState('idle');
        activeMode = null;
    }
};

recognition.onerror = function(event) {
    console.error("Microphone ERROR -> ", event.error);
    resetMics();
    if (activeMode === 'mascot') {
        showBubble("Sorry, didn't catch that.");
        updateMascotState('idle');
    }
    activeMode = null;
    isAIProcessing = false;
};

function resetMics() {
    const micBtn = document.getElementById('micBtn');
    if(micBtn) micBtn.classList.remove('mic-listening');
    const statusMsg = document.getElementById('statusMsg');
    if(statusMsg) statusMsg.innerText = "Tap to speak";
    const micIcon = document.getElementById('micIcon');
    if(micIcon) micIcon.classList.remove('recording');
}


// ============================================
//  AGRI-BUDDY MASCOT LOGIC
// ============================================

document.addEventListener("DOMContentLoaded", function() {
    injectMascot();
    injectBotStyles(); 
    // Auto-Load Weather
    if(document.querySelector('.fa-cloud-sun')) {
        fetch('/tool/weather', { method: 'POST' }).then(r=>r.json()).then(d=>console.log("Weather:", d)).catch(e=>{});
    }
});

function injectBotStyles() {
    // UPDATED: More realistic 3D Metallic Bot Look with "Cloud" Bubble
    const css = `
    @keyframes bot-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    @keyframes eye-blink { 0%, 90%, 100% { height: 10px; } 95% { height: 2px; } }
    @keyframes antenna-glow { 0%, 100% { box-shadow: 0 0 5px #00E676; background: #00E676; } 50% { box-shadow: 0 0 15px #00E676; background: #69F0AE; } }
    @keyframes talk-wobble { 0% { transform: rotate(0deg); } 25% { transform: rotate(-5deg); } 75% { transform: rotate(5deg); } 100% { transform: rotate(0deg); } }

    #agri-buddy-container { 
        transition: all 1.0s cubic-bezier(0.25, 1, 0.5, 1); /* Smoother cursor-like movement */
        z-index: 10000; 
        animation: bot-float 3.5s ease-in-out infinite; 
        filter: drop-shadow(0 10px 10px rgba(0,0,0,0.3));
    }
    #agri-buddy-container.buddy-moving { animation: none; }
    
    .buddy-body-wrapper { position: relative; width: 80px; height: 80px; display: flex; justify-content: center; align-items: center; }
    
    /* 3D Body */
    .buddy-avatar {
        width: 100%; height: 100%; border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #ffffff, #B0BEC5); /* Metallic White */
        border: 2px solid #fff;
        position: relative; display: flex; justify-content: center; align-items: center;
        z-index: 5;
    }
    
    /* Screen Face */
    .buddy-face-plate {
        width: 65%; height: 55%; background: #111; border-radius: 12px;
        display: flex; justify-content: center; align-items: center; gap: 8px;
        box-shadow: inset 0 0 5px #000; border: 1px solid #333;
    }
    
    .buddy-eye {
        width: 10px; height: 10px; background: #00E676; border-radius: 50%;
        box-shadow: 0 0 5px #00E676; animation: eye-blink 4s infinite;
    }

    /* Antenna */
    .buddy-antenna { position: absolute; top: -10px; width: 3px; height: 15px; background: #555; z-index: 1; }
    .buddy-antenna::after { content: ''; position: absolute; top: -5px; left: -3.5px; width: 10px; height: 10px; border-radius: 50%; background: #00E676; border: 1px solid white; animation: antenna-glow 2s infinite; }

    /* 3D Hands */
    .buddy-hand { 
        position: absolute; width: 20px; height: 20px; background: radial-gradient(circle at 30% 30%, #FFD54F, #FF8F00); 
        border-radius: 50%; border: 2px solid #fff; top: 50px; 
        box-shadow: 0 3px 5px rgba(0,0,0,0.2); transition: all 0.3s ease; z-index: 2; 
    }
    .buddy-hand.left { left: -8px; }
    .buddy-hand.right { right: -8px; }
    
    .buddy-talking .buddy-avatar { animation: talk-wobble 0.2s infinite; }
    .buddy-pointing .buddy-hand.right { transform: translate(45px, -35px) scale(1.3); background: #2E7D32; } /* Pointing Gesture */
    .buddy-pointing .buddy-avatar { transform: rotate(-10deg); }

    /* Cloud Bubble */
    .buddy-bubble {
        background: white; border: 1px solid #eee; color: #333; padding: 12px 18px;
        border-radius: 20px; border-bottom-right-radius: 2px;
        font-size: 0.9rem; font-weight: 500;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1); margin-bottom: 8px;
        max-width: 200px; opacity: 0; transform: translateY(10px) scale(0.9);
        transition: all 0.3s ease; pointer-events: none; text-align: center;
        position: absolute; bottom: 85px; right: 5px;
    }
    .buddy-bubble.show { opacity: 1; transform: translateY(0) scale(1); }
    `;
    const style = document.createElement('style');
    style.type = 'text/css';
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
}

function injectMascot() {
    if (document.getElementById('agri-buddy-container')) return;
    const container = document.createElement('div');
    container.id = 'agri-buddy-container';
    container.onclick = toggleMascotVoice; 
    container.style.position = 'fixed';
    container.style.bottom = '110px';
    container.style.right = '20px';
    container.innerHTML = `<div class="buddy-bubble" id="buddy-bubble">Namaste! Click me.</div><div class="buddy-body-wrapper"><div class="buddy-antenna"></div><div class="buddy-hand left"></div><div class="buddy-avatar" id="buddy-avatar"><div class="buddy-face-plate"><div class="buddy-eye"></div><div class="buddy-eye"></div></div></div><div class="buddy-hand right"></div></div>`;
    document.body.appendChild(container);
    setTimeout(() => showBubble("Namaste! Need help?"), 1500);
}

function toggleMascotVoice() {
    if (!SpeechRecognition) { alert("Voice not supported."); return; }
    if (isAIProcessing) { showBubble("Thinking..."); return; }

    if (activeMode === 'mascot') {
        recognition.stop();
        activeMode = null;
        updateMascotState('idle');
    } else {
        if (activeMode) recognition.stop();
        synthesis.cancel();
        setTimeout(() => {
            activeMode = 'mascot';
            try { recognition.start(); } catch(e) { console.error(e); }
        }, 200);
    }
}

function sendMascotMessage(message) {
    if (isAIProcessing) return;
    isAIProcessing = true;
    lastRequestTime = Date.now();
    showBubble("Thinking...");

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, page_context: document.title })
    })
    .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.reply || "Server Error");
        return data;
    })
    .then(data => {
        isAIProcessing = false;
        let aiText = data.reply || "Sorry, I can't think right now.";
        const processed = processAIResponse(aiText);
        showBubble(processed.cleanText);
        speakText(processed.cleanText, true);
    })
    .catch(error => {
        isAIProcessing = false;
        console.error("Mascot Error:", error);
        let displayMsg = "Connection lost.";
        showBubble(displayMsg);
        speakText(displayMsg, true);
        updateMascotState('idle');
    });
}

// --- CENTRAL AI RESPONSE PROCESSOR ---
function processAIResponse(rawText) {
    let text = rawText || "Sorry, I am offline.";
    
    let targetId = null;
    if (text.includes("POINT_SELL")) targetId = "target-sell";
    else if (text.includes("POINT_WEATHER")) targetId = "target-weather";
    else if (text.includes("POINT_FINANCE")) targetId = "target-finance";
    else if (text.includes("POINT_TOOLS")) targetId = "target-tools";
    else if (text.includes("POINT_PROFILE")) targetId = "target-profile";
    else if (text.includes("POINT_SUBMIT")) targetId = "target-submit";
    else if (text.includes("POINT_NAME")) targetId = "target-name";
    else if (text.includes("POINT_PRICE")) targetId = "target-price";
    else if (text.includes("POINT_BACK")) targetId = "target-back";

    let cleanText = text.replace(/[\{\[]*POINT_[A-Z]+[\}\]]*/g, '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*/g, '');
    let formattedHTML = text.replace(/[\{\[]*POINT_[A-Z]+[\}\]]*/g, '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    if (targetId) moveMascotTo(targetId);

    return { cleanText, formattedHTML };
}

// --- UPDATED MOVEMENT ENGINE (Better Calibration) ---
function getVisibleTarget(selector) {
    const elements = document.querySelectorAll(selector);
    for (let el of elements) {
        if (el.offsetWidth > 0 && el.offsetHeight > 0) return el;
    }
    return null;
}

function moveMascotTo(elementId) {
    let target = document.getElementById(elementId);
    
    // Smart Fallback
    if (!target || target.offsetWidth === 0) {
        if(elementId === 'target-sell') target = getVisibleTarget('a[href*="sell_crop"]');
        if(elementId === 'target-weather') target = getVisibleTarget('.glass-panel .fa-cloud-sun')?.closest('.glass-panel');
        if(elementId === 'target-finance') target = getVisibleTarget('.glass-panel .fa-wallet')?.closest('.glass-panel');
        if(elementId === 'target-tools') target = getVisibleTarget('.tool-grid');
        if(elementId === 'target-profile') target = getVisibleTarget('a[href*="settings"]');
        if(elementId === 'target-submit') target = getVisibleTarget('button[type="submit"], .btn-submit, button[onclick]');
        if(elementId === 'target-name') target = getVisibleTarget('input[type="text"], select');
        if(elementId === 'target-price') target = getVisibleTarget('input[type="number"]');
        if(elementId === 'target-back') target = getVisibleTarget('.btn-secondary');
        
        if(target && target.tagName === 'I') target = target.closest('.glass-panel') || target.closest('a');
    }

    const bot = document.getElementById('agri-buddy-container');
    
    if (target && bot) {
        // 1. Scroll Center
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // 2. Move
        setTimeout(() => {
            const rect = target.getBoundingClientRect();
            const botRect = bot.getBoundingClientRect();

            bot.style.bottom = 'auto';
            bot.style.right = 'auto';
            bot.style.left = botRect.left + 'px';
            bot.style.top = botRect.top + 'px';
            
            void bot.offsetWidth; 

            // CALIBRATION: Move higher (-80px) so the HAND points at center
            let flyTop = rect.top - 80; 
            let flyLeft = rect.left + (rect.width / 2);

            // Boundary Check
            if (flyTop < 10) flyTop = rect.bottom + 10; // If too high, point from bottom
            if (window.innerWidth < 768) {
                 flyLeft = Math.min(window.innerWidth - 70, Math.max(10, flyLeft));
            }

            bot.classList.add('buddy-moving'); 
            bot.style.top = flyTop + "px";
            bot.style.left = flyLeft + "px";
            
            bot.classList.add('buddy-pointing');
            
            setTimeout(resetMascotPosition, 5000);
        }, 800); 
    }
}

function resetMascotPosition() {
    const bot = document.getElementById('agri-buddy-container');
    if(bot) {
        bot.classList.remove('buddy-pointing');
        
        const homeTop = window.innerHeight - 110 - bot.offsetHeight; 
        const homeLeft = window.innerWidth - 20 - bot.offsetWidth; 
        
        bot.style.top = homeTop + "px";
        bot.style.left = homeLeft + "px";
        
        setTimeout(() => {
            bot.classList.remove('buddy-moving');
            bot.style.transition = ""; 
            bot.style.top = "";
            bot.style.left = "";
            bot.style.bottom = "110px";
            bot.style.right = "20px";
        }, 1500);
    }
}

function updateMascotState(state) {
    const avatar = document.getElementById('agri-buddy-container');
    const face = document.getElementById('buddy-avatar');
    if (!avatar || !face) return;

    avatar.classList.remove('buddy-listening', 'buddy-talking');
    
    if (state === 'listening') {
        avatar.classList.add('buddy-listening');
    } else if (state === 'talking') {
        avatar.classList.add('buddy-talking');
    }
}

function showBubble(text) {
    const bubble = document.getElementById('buddy-bubble');
    if (!bubble) return;
    bubble.innerText = text;
    bubble.classList.add('show');
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => { bubble.classList.remove('show'); }, 8000); 
}


// ============================================
//  STANDARD CHAT & HELPERS
// ============================================

function toggleVoice() {
    if (!SpeechRecognition) return;
    const micBtn = document.getElementById('micBtn');

    if (isAIProcessing) return;

    if (activeMode === 'dashboard') {
        recognition.stop();
        activeMode = null;
        return; 
    }
    if (activeMode) recognition.stop();

    setTimeout(() => {
        activeMode = 'dashboard';
        if(micBtn) micBtn.classList.add('mic-listening');
        const statusMsg = document.getElementById('statusMsg');
        if(statusMsg) statusMsg.innerText = "Listening...";
        try { recognition.start(); } catch (e) {}
    }, 200);
}

function startVoiceInput() {
    if (activeMode === 'chat') { recognition.stop(); return; }
    if (activeMode) recognition.stop();
    activeMode = 'chat';
    const micIcon = document.getElementById('micIcon');
    if(micIcon) micIcon.classList.add('recording');
    setTimeout(() => { try { recognition.start(); } catch (e) {} }, 200);
}

function toggleChat() {
    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow) {
        chatWindow.style.display = (chatWindow.style.display === 'flex') ? 'none' : 'flex';
    }
}

function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (message === "") return;
    
    if (isAIProcessing) return; 
    isAIProcessing = true;
    lastRequestTime = Date.now();

    addMessage(message, 'user-msg', false);
    inputField.value = "";
    
    addMessage("Typing...", 'bot-msg-loading', false); 

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, page_context: document.title })
    })
    .then(async response => {
        const loadingMsg = document.querySelector('.bot-msg-loading');
        if(loadingMsg) loadingMsg.remove();
        const data = await response.json(); 
        if (!response.ok) throw new Error(data.reply || "Server Error");
        return data;
    })
    .then(data => {
        isAIProcessing = false; 
        let aiText = data.reply || "Sorry, I am confused.";
        const processed = processAIResponse(aiText);
        addMessage(processed.formattedHTML, 'bot-msg', true);
        speakText(processed.cleanText, false);
    })
    .catch(error => {
        isAIProcessing = false; 
        const loadingMsg = document.querySelector('.bot-msg-loading');
        if(loadingMsg) loadingMsg.remove();
        addMessage("Connection error.", 'bot-msg', false);
    });
}

window.currentSpeech = null;

function detectLanguage(text) {
    if (/[\u0900-\u097F]/.test(text)) return 'hi-IN'; 
    if (/[\u0C00-\u0C7F]/.test(text)) return 'te-IN'; 
    if (/[\u0B80-\u0BFF]/.test(text)) return 'ta-IN'; 
    return 'en-IN'; 
}

function speakText(text, animateMascot) {
    if (!text) return;
    window.speechSynthesis.cancel();
    if (animateMascot) updateMascotState('talking');

    setTimeout(() => {
        window.currentSpeech = new SpeechSynthesisUtterance(text);
        const lang = detectLanguage(text);
        window.currentSpeech.lang = lang; 
        let voices = window.speechSynthesis.getVoices();
        let selectedVoice = voices.find(v => v.lang === lang && v.name.includes('Google'));
        if (selectedVoice) window.currentSpeech.voice = selectedVoice;
        
        window.currentSpeech.onend = function() {
            if (animateMascot) updateMascotState('idle');
        };
        window.speechSynthesis.speak(window.currentSpeech);
    }, 100);
}

function addMessage(text, className, isHTML = false) {
    const chatBody = document.getElementById('chatBody');
    if (!chatBody) return;
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('chat-message', className);
    if (isHTML) msgDiv.innerHTML = text; else msgDiv.innerText = text;
    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function handleEnter(event) { if (event.key === 'Enter') sendMessage(); }

document.addEventListener("DOMContentLoaded", function() {
    const chatInput = document.getElementById('userInput');
    if(chatInput) {
        chatInput.addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMessage();
            }
        });
    }
});

function runSoilTest(e) { e.preventDefault(); fetch('/tool/soil_test', {method:'POST', body:new FormData(e.target)}).then(r=>r.json()).then(d=>{ document.getElementById('res-ph').innerText=d.ph; document.getElementById('res-advice').innerText=d.advice; document.getElementById('soil-result').style.display='block'; }); }
function runPestCheck(e) { e.preventDefault(); const f = new FormData(); document.querySelectorAll('.pest-sym:checked').forEach(c=>f.append('symptoms[]',c.value)); fetch('/tool/pest_check', {method:'POST',body:f}).then(r=>r.json()).then(d=>{ document.getElementById('res-disease').innerText=d.disease; document.getElementById('res-remedy').innerText=d.remedy; document.getElementById('pest-result').style.display='block'; }); }
function runCropRec(e) { e.preventDefault(); const f = new FormData(e.target); if(f.get('month')) f.set('month', f.get('month').split('-')[1]); fetch('/tool/crop_recommend', {method:'POST',body:f}).then(r=>r.json()).then(d=>{ document.getElementById('res-crop').innerText=d.crop; document.getElementById('crop-result').style.display='block'; }); }
function runWaterLogic(e) { e.preventDefault(); fetch('/tool/water_schedule', {method:'POST', body:new FormData(e.target)}).then(r=>r.json()).then(d=>{ document.getElementById('res-water').innerText=d.advice; document.getElementById('water-result').style.display='block'; }); }
function openQR(name, id) { const t = document.getElementById('qr-title'); if(t) t.innerText = "QR Code for " + name; const i = document.getElementById('qr-image'); if(i) i.src = "/generate_qr/" + id; const m = document.getElementById('modal-qr'); if(m) m.style.display = "block"; }