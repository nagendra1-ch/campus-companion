let currentStudentId = 1;
let latestAlexaPayload = null;
let recognition = null;
let isRecording = false;
let isLiveClockMode = true;

function formatLiveDateTime(dateObj = new Date()) {
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  const hours = String(dateObj.getHours()).padStart(2, '0');
  const mins = String(dateObj.getMinutes()).padStart(2, '0');
  const secs = String(dateObj.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${mins}:${secs}`;
}

function tickLiveClock() {
  if (isLiveClockMode) {
    const clockEl = document.getElementById('clockText');
    const badgeEl = document.getElementById('clockLiveBadge');
    if (clockEl) {
      clockEl.textContent = formatLiveDateTime();
    }
    if (badgeEl) {
      badgeEl.textContent = '🟢 LIVE';
      badgeEl.style.background = 'rgba(16, 185, 129, 0.2)';
      badgeEl.style.color = '#34d399';
      badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    }
  }
}
setInterval(tickLiveClock, 1000);

// Initialize Speech Recognition if supported in browser
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    document.getElementById('btnMic').classList.add('recording');
    document.getElementById('alexaOrb').classList.add('pulsing');
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    document.getElementById('voiceInput').value = transcript;
    sendVoiceQuery(transcript);
  };

  recognition.onerror = (event) => {
    console.warn('Speech recognition error:', event.error);
    stopMic();
  };

  recognition.onend = () => {
    stopMic();
  };
}

function toggleMic() {
  if (!recognition) {
    alert("Speech recognition is not supported in this browser. Please type your query in the input box!");
    return;
  }
  if (isRecording) {
    recognition.stop();
  } else {
    recognition.start();
  }
}

function stopMic() {
  isRecording = false;
  document.getElementById('btnMic').classList.remove('recording');
  document.getElementById('alexaOrb').classList.remove('pulsing');
}

// Persistent, Single Consistent Female Voice Management
let lockedFemaleVoice = null;

function getConsistentFemaleVoice() {
  if (lockedFemaleVoice) return lockedFemaleVoice;
  if (!('speechSynthesis' in window)) return null;

  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  // Filter out any explicitly male voices
  const isNotMale = v => !/male|david|mark|guy|george|james|richard|stefan|pablo/i.test(v.name);

  // Strict priority list for consistent female voice
  const femalePatterns = [
    /zira/i,                          // Microsoft Zira (Standard Windows English Female)
    /jenny/i,                         // Microsoft Jenny Natural (Edge/Windows Female)
    /aria/i,                          // Microsoft Aria Natural (Edge/Windows Female)
    /samantha/i,                      // Apple Samantha (Mac/iOS Female)
    /karen|victoria|moira|fiona/i,     // Apple English Female
    /google.*female/i,                // Google Female
    /google us english/i,             // Chrome default US Female
    /female/i                         // Any explicitly tagged female voice
  ];

  for (const pattern of femalePatterns) {
    const found = voices.find(v => v.lang.startsWith('en') && pattern.test(v.name) && isNotMale(v));
    if (found) {
      lockedFemaleVoice = found;
      return lockedFemaleVoice;
    }
  }

  // Fallback: any English voice not flagged as male
  const fallback = voices.find(v => v.lang.startsWith('en') && isNotMale(v)) || voices.find(v => isNotMale(v));
  if (fallback) {
    lockedFemaleVoice = fallback;
    return lockedFemaleVoice;
  }

  lockedFemaleVoice = voices[0] || null;
  return lockedFemaleVoice;
}

if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    getConsistentFemaleVoice();
  };
  getConsistentFemaleVoice();
}

// Speak response aloud using Web Speech Synthesis API (Consistent Female Voice Only)
function speakSpeech(text) {
  if (!('speechSynthesis' in window) || !text) return;

  window.speechSynthesis.cancel(); // Stop ongoing speech

  // Strip markdown formatting symbols for natural spoken speech
  const cleanSpoken = text
    .replace(/[#*`_~$]/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\n\n+/g, '. ')
    .replace(/\n/g, ' ')
    .trim();

  const utterance = new SpeechSynthesisUtterance(cleanSpoken);
  utterance.rate = 1.0;
  utterance.pitch = 1.05;

  const femaleVoice = getConsistentFemaleVoice();
  if (femaleVoice) {
    utterance.voice = femaleVoice;
    utterance.lang = femaleVoice.lang || 'en-US';
  }

  const orb = document.getElementById('alexaOrb');
  if (orb) orb.classList.add('pulsing');

  utterance.onend = () => {
    if (orb) orb.classList.remove('pulsing');
  };
  utterance.onerror = () => {
    if (orb) orb.classList.remove('pulsing');
  };

  window.speechSynthesis.speak(utterance);
}

function speakCurrentSpeech() {
  const text = document.getElementById('alexaSpeech').textContent;
  speakSpeech(text);
}

// REST Helper
async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  return res.json();
}

// Student Switcher & User Isolation
async function loadStudents() {
  try {
    const students = await api('/api/students');
    const select = document.getElementById('userSelect');
    select.innerHTML = students.map(s => 
      `<option value="${s.id}">${s.name} (${s.email})</option>`
    ).join('');
    select.value = currentStudentId;
  } catch (e) {
    console.error('Failed to load students:', e);
  }
}

function onStudentChange() {
  const select = document.getElementById('userSelect');
  currentStudentId = parseInt(select.value, 10);
  refreshAll();
}

// Send Voice Query to Alexa pipeline
async function sendVoiceQuery(overrideText = null) {
  const input = document.getElementById('voiceInput');
  const text = overrideText || input.value.trim();
  if (!text) return;

  const orb = document.getElementById('alexaOrb');
  orb.classList.add('pulsing');

  try {
    const res = await api('/api/alexa/simulate-voice', 'POST', {
      utterance: text,
      studentId: currentStudentId
    });

    latestAlexaPayload = res.alexaResponse;
    const spoken = res.spokenResponse || "Request processed.";
    document.getElementById('alexaSpeech').textContent = spoken;
    speakSpeech(spoken);
    input.value = '';
    
    // Refresh schedule, assignments, context
    await refreshAll();
  } catch (err) {
    console.error('Error sending query:', err);
    document.getElementById('alexaSpeech').textContent = "Sorry, error connecting to Alexa endpoint.";
  } finally {
    setTimeout(() => {
      orb.classList.remove('pulsing');
    }, 1500);
  }
}

function askPreset(utterance) {
  document.getElementById('voiceInput').value = utterance;
  sendVoiceQuery(utterance);
}

// Quick Add Assignment Form
async function quickAddAssignment() {
  const subInput = document.getElementById('quickSubject');
  const daysInput = document.getElementById('quickDays');
  const subject = subInput.value.trim();
  const days = parseInt(daysInput.value, 10) || 5;

  if (!subject) {
    alert('Please enter a subject name (e.g. DBMS, Operating Systems)');
    return;
  }

  // We can pass directly as a voice prompt or API call
  const query = `I have to submit ${subject} assignment within ${days} days`;
  document.getElementById('voiceInput').value = query;
  await sendVoiceQuery(query);

  subInput.value = '';
}

// Complete Assignment
async function markTaskComplete(taskId, subjectName) {
  const query = `${subjectName || ''} assignment is completed`;
  await sendVoiceQuery(query);
}

// Delete Assignment
async function deleteTask(taskId) {
  if (confirm('Are you sure you want to delete this assignment and its daily reminders?')) {
    await api(`/api/assignments/${currentStudentId}/${taskId}`, 'DELETE');
    await refreshAll();
  }
}

// Dismiss Reminder
async function dismissReminder(reminderId) {
  await api(`/api/reminders/${currentStudentId}/${reminderId}/dismiss`, 'POST');
  await refreshAll();
}

// Simulator Events
async function simEvent(eventName) {
  await api(`/api/sim/transition/${currentStudentId}`, 'POST', { event: eventName });
  await refreshAll();
}

async function setSimClock() {
  const input = document.getElementById('simTimeInput');
  if (!input.value) return;
  isLiveClockMode = false;
  await api(`/api/sim/clock/${currentStudentId}`, 'POST', { simNow: input.value + ':00' });
  await refreshAll();
}

async function syncLiveClock() {
  await api(`/api/sim/clock/live/${currentStudentId}`, 'POST');
  isLiveClockMode = true;
  await refreshAll();
}

async function advanceOneDay() {
  await api(`/api/sim/advance-day/${currentStudentId}`, 'POST');
  await refreshAll();
}

async function resetDb() {
  if (confirm('Reset database to original demo seed data?')) {
    await api('/api/sim/reset', 'POST');
    await refreshAll();
  }
}

// Modal JSON viewer
function openJsonModal() {
  const modal = document.getElementById('jsonModal');
  const pre = document.getElementById('jsonContent');
  pre.textContent = JSON.stringify(latestAlexaPayload || {
    info: "No Alexa payload sent yet. Try clicking any utterance above!"
  }, null, 2);
  modal.classList.add('open');
}

function closeJsonModal() {
  document.getElementById('jsonModal').classList.remove('open');
}

// Main Refresh Function
async function refreshAll() {
  try {
    // 1. Context & User Info
    const ctx = await api(`/api/context/${currentStudentId}`);
    
    // Update student identity header & card
    if (ctx.student) {
      document.getElementById('identityName').textContent = ctx.student.name;
      document.getElementById('identityEmail').textContent = ctx.student.email;
      document.getElementById('identityAlexaId').textContent = ctx.student.alexa_user_id || 'demo_user';
      document.getElementById('identityAvatar').textContent = ctx.student.avatar || '🎓';
      document.getElementById('userAvatar').textContent = ctx.student.avatar || '🎓';
    }

    // State Pill
    const pill = document.getElementById('statePill');
    pill.textContent = ctx.state.replaceAll('_', ' ');
    pill.className = 'state-pill ' + (ctx.state === 'IN_CLASS' ? 'in-class' : ctx.state === 'BEFORE_LAB' ? 'before-lab' : '');

    // Clock
    if (ctx.isLive !== false) {
      isLiveClockMode = true;
      document.getElementById('clockText').textContent = formatLiveDateTime();
      const badgeEl = document.getElementById('clockLiveBadge');
      if (badgeEl) {
        badgeEl.textContent = '🟢 LIVE';
        badgeEl.style.background = 'rgba(16, 185, 129, 0.2)';
        badgeEl.style.color = '#34d399';
        badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      }
      const now = new Date();
      const offset = now.getTimezoneOffset();
      const localNow = new Date(now.getTime() - (offset * 60 * 1000));
      document.getElementById('simTimeInput').value = localNow.toISOString().slice(0, 16);
    } else {
      isLiveClockMode = false;
      const formattedNow = ctx.now.replace('T', ' ').slice(0, 19);
      document.getElementById('clockText').textContent = formattedNow;
      document.getElementById('simTimeInput').value = ctx.now.slice(0, 16);
      const badgeEl = document.getElementById('clockLiveBadge');
      if (badgeEl) {
        badgeEl.textContent = '🟡 SIM';
        badgeEl.style.background = 'rgba(245, 158, 11, 0.2)';
        badgeEl.style.color = '#fbbf24';
        badgeEl.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      }
    }

    // Current Session
    const currBanner = document.getElementById('currentSessionBanner');
    if (ctx.currentEvent) {
      currBanner.innerHTML = `Currently in: <b style="color: #6ee7b7;">${ctx.currentEvent.title}</b> (${ctx.currentEvent.room}) — Ends in ${ctx.currentEvent.endsInMin} mins`;
    } else {
      currBanner.innerHTML = `Location: <b>${ctx.location.replaceAll('_', ' ')}</b> • No ongoing class right now`;
    }

    // Next Class Live Widget
    const nextBadge = document.getElementById('nextClassBadge');
    const nextTitle = document.getElementById('nextClassTitle');
    const nextRoom = document.getElementById('nextClassRoom');
    const nextStart = document.getElementById('nextClassStart');
    const nextTypeBadge = document.getElementById('nextClassTypeBadge');

    if (ctx.nextEvent) {
      const mins = ctx.nextEvent.startsInMin;
      nextBadge.textContent = mins <= 0 ? 'Starts Now' : `In ${mins} min${mins > 1 ? 's' : ''}`;
      nextBadge.style.display = 'inline-flex';
      nextTitle.textContent = ctx.nextEvent.title;
      nextRoom.textContent = ctx.nextEvent.room || 'TBA';
      nextStart.textContent = ctx.nextEvent.start ? ctx.nextEvent.start.slice(0, 5) : '--';
      nextTypeBadge.textContent = ctx.nextEvent.type || 'THEORY';
      nextTypeBadge.className = ctx.nextEvent.type === 'LAB' ? 'badge-lab' : 'badge-theory';
    } else {
      nextBadge.style.display = 'none';
      nextTitle.textContent = 'No more classes today';
      nextRoom.textContent = 'None';
      nextStart.textContent = '--';
      nextTypeBadge.textContent = 'FREE';
      nextTypeBadge.className = 'badge-theory';
    }

    // 2. Schedule Today
    const schedule = await api(`/api/schedule/today?studentId=${currentStudentId}`);
    const tl = document.getElementById('timelineList');
    if (!schedule || schedule.length === 0) {
      tl.innerHTML = '<div style="color: var(--text-dim); font-size: 0.85rem; padding: 12px;">No sessions scheduled for today.</div>';
    } else {
      tl.innerHTML = schedule.map(s => {
        const isCurrent = ctx.currentEvent && ctx.currentEvent.title === s.title;
        return `
          <div class="timeline-item ${s.type === 'LAB' ? 'lab' : ''} ${isCurrent ? 'active' : ''}">
            <div class="session-info">
              <div class="session-name">${s.title} ${isCurrent ? '<span style="color:#6ee7b7; font-size:0.75rem;">● NOW</span>' : ''}</div>
              <div class="session-room">📍 ${s.room} • <span style="text-transform: uppercase;">${s.type}</span></div>
            </div>
            <div class="session-time">${s.start_formatted || s.start} – ${s.end_formatted || s.end}</div>
          </div>
        `;
      }).join('');
    }

    // 3. Assignments
    const tasks = await api(`/api/assignments/${currentStudentId}`);
    const taskList = document.getElementById('assignmentList');
    const pendingCount = tasks.filter(t => t.status !== 'COMPLETED').length;
    document.getElementById('pendingTasksBadge').textContent = `${pendingCount} Pending`;

    if (!tasks || tasks.length === 0) {
      taskList.innerHTML = '<div style="color: var(--text-dim); font-size: 0.85rem; padding: 12px;">No assignments created yet. Ask Alexa to add one!</div>';
    } else {
      taskList.innerHTML = tasks.map(t => {
        const isDone = t.status === 'COMPLETED';
        let dueClass = 'far';
        let dueText = `Due in ${t.days_left} days (${t.due_date_only})`;
        
        if (t.is_overdue) {
          dueClass = 'urgent';
          dueText = `OVERDUE (${t.due_date_only})`;
        } else if (t.days_left <= 0) {
          dueClass = 'urgent';
          dueText = `Due TODAY! (${t.due_formatted})`;
        } else if (t.days_left === 1) {
          dueClass = 'upcoming';
          dueText = `Due TOMORROW! (${t.due_formatted})`;
        }

        return `
          <div class="assignment-item ${isDone ? 'completed' : ''}">
            <div class="assignment-main">
              <div class="assignment-header">
                <span class="subject-tag">${t.subject_name || 'General'}</span>
                <span class="assignment-title">${t.title}</span>
              </div>
              <div class="assignment-due-row">
                <span class="due-pill ${dueClass}">${dueText}</span>
                <span>Priority: ${'★'.repeat(t.weight || 3)}</span>
              </div>
            </div>
            <div class="assignment-actions">
              ${!isDone ? `
                <button class="btn-action complete" onclick="markTaskComplete(${t.id}, '${t.subject_name || t.title}')" title="Mark completed">
                  ✓ Done
                </button>
              ` : `
                <span style="font-size: 0.75rem; color: #6ee7b7; font-weight: 700;">✓ Completed</span>
              `}
              <button class="btn-action delete" onclick="deleteTask(${t.id})" title="Delete assignment">
                🗑️
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // 4. Daily Reminders Trigger Feed
    const remData = await api(`/api/reminders/${currentStudentId}`);
    const remList = document.getElementById('remindersList');
    const todayReminders = remData.todayReminders || [];

    if (todayReminders.length === 0) {
      remList.innerHTML = '<div style="color: var(--text-dim); font-size: 0.82rem; padding: 6px;">No daily reminder alerts triggered for today.</div>';
    } else {
      remList.innerHTML = todayReminders.map(r => `
        <div class="reminder-item">
          <div class="reminder-text">
            <span>🔔</span>
            <div>
              <b>${r.text}</b>
              <div style="font-size: 0.72rem; color: var(--text-dim);">Trigger: Daily at 8:00 AM • ${r.remind_date || 'Today'}</div>
            </div>
          </div>
          <button class="btn-action complete" onclick="dismissReminder(${r.id})">Dismiss</button>
        </div>
      `).join('');
    }

  } catch (e) {
    console.error('Refresh error:', e);
  }
}

// Initial boot
window.addEventListener('DOMContentLoaded', async () => {
  await loadStudents();
  await refreshAll();
  
  // Also perform a default launch request to populate the latest Alexa JSON inspector
  try {
    const launchRes = await api('/api/alexa', 'POST', {
      version: "1.0",
      request: { type: "LaunchRequest" },
      session: { user: { userId: "amzn1.ask.account.RAVI_123" } }
    });
    latestAlexaPayload = launchRes;
  } catch (e) {}

  // Check Gemini AI Status
  try {
    const aiStatus = await api('/api/ai/status', 'GET');
    const badge = document.getElementById('geminiBadge');
    if (badge && aiStatus.configured) {
      badge.style.display = 'inline-flex';
      badge.title = `Model: ${aiStatus.model}`;
    }
  } catch (e) {}
});

async function loadGeminiStudyPlan() {
  const speechBox = document.getElementById('alexaSpeech');
  speechBox.innerText = "⚡ Consulting Local AI Academic Advisor for a personalized study and task plan...";
  try {
    const res = await api(`/api/ai/advice/${currentStudentId}`, 'GET');
    if (res && res.advice) {
      speechBox.innerText = `⚡ Personalized Study Plan (${res.engine || 'Local AI'}):\n\n` + res.advice;
      speakSpeech(res.advice);
    } else {
      speechBox.innerText = "Could not generate study advice right now.";
    }
  } catch (err) {
    speechBox.innerText = "Error loading study plan: " + err.message;
  }
}

window.loadStudyPlan = loadGeminiStudyPlan;
const loadStudyPlan = loadGeminiStudyPlan;


