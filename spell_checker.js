/**
 * TextTool – Spell Checker Page JavaScript
 * Handles: tab switching, API calls, error highlighting,
 *          single-word correction, auto-correct, download.
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let currentErrors  = [];   // [{word, suggestions, confidence, best}, ...]
let currentCheckId = null; // spell-check record ID from API
let correctedText  = null; // text after auto-correct

// ── DOM refs ──────────────────────────────────────────────────────────────────
const textarea     = document.getElementById('spellTextarea');
const preview      = document.getElementById('highlightedPreview');
const errorList    = document.getElementById('errorList');
const errorBadge   = document.getElementById('errorBadge');
const btnCheck     = document.getElementById('btnCheck');
const btnAutoCorr  = document.getElementById('btnAutoCorrect');
const btnClear     = document.getElementById('btnClear');
const btnCopy      = document.getElementById('btnCopy');
const btnDownload  = document.getElementById('btnDownload');
const btnEditMode  = document.getElementById('btnEditMode');
const charCount    = document.getElementById('charCount');
const spellStats   = document.getElementById('spellStats');
const statWords    = document.getElementById('statWords');
const statErrors   = document.getElementById('statErrors');
const statCorrected = document.getElementById('statCorrected');
const downloadText  = document.getElementById('downloadText');
const downloadForm  = document.getElementById('downloadForm');

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.compress-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.compress-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.compress-tab-pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    const target = document.getElementById('tab-' + tab.dataset.tab);
    target?.classList.add('active');
  });
});

// ── Character counter ─────────────────────────────────────────────────────────
textarea?.addEventListener('input', () => {
  const len = textarea.value.length;
  charCount.textContent = `${len.toLocaleString()} / 50,000 characters`;
  charCount.style.color = len > 45000 ? 'var(--accent-danger)' : '';
});

// ── Check Spelling ────────────────────────────────────────────────────────────
btnCheck?.addEventListener('click', async () => {
  const text = textarea.value.trim();
  if (!text) { showToast('Please enter some text first.', 'warning'); return; }

  showLoading('Checking spelling…');
  btnCheck.disabled = true;
  btnCheck.textContent = '⏳ Checking…';

  try {
    const res  = await apiPost('/api/check-spelling', { text });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'Spell check failed.', 'danger');
      return;
    }

    currentErrors  = data.errors || [];
    currentCheckId = data.check_id;
    correctedText  = null;

    renderStats(data.word_count, data.error_count, 0);
    renderHighlighted(text, currentErrors);
    renderErrorPanel(currentErrors);

    if (data.error_count === 0) {
      showToast('No spelling errors found! ✅', 'success');
    } else {
      showToast(`Found ${data.error_count} spelling error(s).`, 'warning');
    }
    btnAutoCorr.disabled = data.error_count === 0;
  } catch (err) {
    console.error(err);
    showToast('Network error. Please try again.', 'danger');
  } finally {
    hideLoading();
    btnCheck.disabled = false;
    btnCheck.textContent = '🔍 Check Spelling';
  }
});

// ── Auto-Correct All ──────────────────────────────────────────────────────────
btnAutoCorr?.addEventListener('click', async () => {
  const text = textarea.value.trim();
  if (!text) return;

  showLoading('Auto-correcting text…');
  btnAutoCorr.disabled = true;

  try {
    const res  = await apiPost('/api/auto-correct', { text, check_id: currentCheckId });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'Auto-correct failed.', 'danger');
      return;
    }

    correctedText = data.corrected_text;
    textarea.value = correctedText;

    // Update stats
    statCorrected.textContent = data.corrections_made;

    // Re-check to update highlights
    const res2  = await apiPost('/api/check-spelling', { text: correctedText });
    const data2 = await res2.json();
    if (data2.success) {
      currentErrors  = data2.errors || [];
      currentCheckId = data2.check_id;
      renderStats(data2.word_count, data2.error_count, data.corrections_made);
      renderHighlighted(correctedText, currentErrors);
      renderErrorPanel(currentErrors);
    }

    showToast(`Auto-corrected ${data.corrections_made} word(s)!`, 'success');
    setupDownload(correctedText);
    btnDownload.style.display = 'inline-flex';
  } catch (err) {
    console.error(err);
    showToast('Auto-correct failed.', 'danger');
  } finally {
    hideLoading();
    btnAutoCorr.disabled = false;
  }
});

// ── Clear ─────────────────────────────────────────────────────────────────────
btnClear?.addEventListener('click', () => {
  textarea.value = '';
  charCount.textContent = '0 / 50,000 characters';
  currentErrors  = [];
  currentCheckId = null;
  correctedText  = null;
  preview.style.display = 'none';
  textarea.style.display = '';
  btnEditMode.style.display = 'none';
  btnDownload.style.display = 'none';
  btnAutoCorr.disabled = true;
  spellStats.classList.add('hidden');
  renderErrorPanel([]);
  errorBadge.textContent = '0';
});

// ── Copy ──────────────────────────────────────────────────────────────────────
btnCopy?.addEventListener('click', () => {
  const text = correctedText || textarea.value;
  copyToClipboard(text);
});

// ── Edit mode (switch back from preview) ─────────────────────────────────────
btnEditMode?.addEventListener('click', () => {
  preview.style.display = 'none';
  textarea.style.display = '';
  btnEditMode.style.display = 'none';
  btnCheck.textContent = '🔍 Re-Check';
});

// ── Download corrected text ───────────────────────────────────────────────────
function setupDownload(text) {
  if (!downloadText || !downloadForm) return;
  downloadText.value = text;
  btnDownload.style.display = 'inline-flex';
  btnDownload.onclick = (e) => {
    e.preventDefault();
    downloadForm.submit();
  };
}

// ── Render helpers ────────────────────────────────────────────────────────────

function renderStats(words, errors, corrections) {
  spellStats.classList.remove('hidden');
  statWords.textContent     = words.toLocaleString();
  statErrors.textContent    = errors;
  statCorrected.textContent = corrections;
}

function renderHighlighted(text, errors) {
  const errorWords = new Set(errors.map(e => e.word.toLowerCase()));

  // Escape HTML then wrap error words
  const escaped = escapeHtml(text);
  const highlighted = escaped.replace(/\b[A-Za-z]{2,}\b/g, match => {
    if (errorWords.has(match.toLowerCase())) {
      return `<mark class="spelling-error" data-word="${escapeHtml(match)}" onclick="handleErrorClick('${escapeHtml(match)}')">${escapeHtml(match)}</mark>`;
    }
    return match;
  });

  preview.innerHTML = highlighted;
  preview.style.display = 'block';
  textarea.style.display = 'none';
  btnEditMode.style.display = 'inline-flex';
}

function renderErrorPanel(errors) {
  errorBadge.textContent = errors.length;

  if (errors.length === 0) {
    errorList.innerHTML = `
      <div class="empty-state" style="padding:36px 16px">
        <div class="empty-state-icon">${currentErrors.length === 0 && correctedText === null ? '🔍' : '✅'}</div>
        <h3>${currentErrors.length === 0 && correctedText === null ? 'No results yet' : 'All clear!'}</h3>
        <p>${currentErrors.length === 0 && correctedText === null
              ? 'Click "Check Spelling" to analyse your text.'
              : 'No spelling errors found.'}</p>
      </div>`;
    return;
  }

  errorList.innerHTML = errors.map(err => `
    <div class="error-item" id="err-${escapeHtml(err.word)}">
      <div class="error-word">
        <span>${escapeHtml(err.word)}</span>
        ${err.confidence !== null
          ? `<span class="confidence-badge">${Math.round(err.confidence * 100)}% conf.</span>`
          : ''}
      </div>
      <div class="suggestion-chips">
        ${err.suggestions.slice(0, 5).map((s, i) => `
          <span class="chip ${i === 0 ? 'best' : ''}"
                onclick="applyCorrection('${escapeHtml(err.word)}', '${escapeHtml(s)}')"
                data-tooltip="${i === 0 ? 'Best match' : ''}">
            ${escapeHtml(s)}
          </span>`).join('')}
        ${err.suggestions.length === 0
          ? '<span class="text-sm text-muted">No suggestions</span>'
          : ''}
      </div>
    </div>`).join('');
}

// ── Click on highlighted word ─────────────────────────────────────────────────
function handleErrorClick(word) {
  // Scroll to corresponding error item in panel
  const item = document.getElementById(`err-${word}`);
  if (item) {
    item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    item.style.background = 'var(--accent-light)';
    setTimeout(() => item.style.background = '', 1500);
  }
}
window.handleErrorClick = handleErrorClick;

// ── Apply single-word correction ─────────────────────────────────────────────
function applyCorrection(original, replacement) {
  const text = textarea.value;
  // Replace all occurrences (case-insensitive, whole-word)
  const regex = new RegExp(`\\b${escapeRegex(original)}\\b`, 'gi');
  const newText = text.replace(regex, match => {
    // Preserve capitalisation
    if (match[0] === match[0].toUpperCase()) {
      return replacement.charAt(0).toUpperCase() + replacement.slice(1);
    }
    return replacement;
  });

  textarea.value = newText;
  correctedText = newText;

  // Remove from error list
  currentErrors = currentErrors.filter(e => e.word.toLowerCase() !== original.toLowerCase());
  renderErrorPanel(currentErrors);
  renderHighlighted(newText, currentErrors);
  renderStats(
    parseInt(statWords.textContent.replace(/,/g, ''), 10),
    currentErrors.length,
    parseInt(statCorrected.textContent, 10) + 1
  );

  setupDownload(newText);
  showToast(`"${original}" → "${replacement}"`, 'success', 3000);
}
window.applyCorrection = applyCorrection;

// ── Helpers ───────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ── Upload form feedback ──────────────────────────────────────────────────────
document.getElementById('uploadForm')?.addEventListener('submit', function() {
  const file = document.getElementById('spellFile')?.files[0];
  if (!file) { showToast('Please select a file.', 'warning'); return; }
  showLoading('Uploading and checking…');
  document.getElementById('uploadBtn').disabled = true;
});
