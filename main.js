/**
 * TextTool – Core JavaScript
 * Handles: theme toggle, sidebar, toast notifications,
 *          loading overlay, flash auto-dismiss, CSRF helpers.
 */

'use strict';

// ── CSRF Helper ──────────────────────────────────────────────────────────────
const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content ?? '';

/**
 * Perform a JSON POST request with CSRF header included.
 * @param {string} url
 * @param {object} body
 * @returns {Promise<Response>}
 */
async function apiPost(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRF_TOKEN,
    },
    body: JSON.stringify(body),
  });
}

// ── Theme ────────────────────────────────────────────────────────────────────
const THEME_KEY = 'texttool_theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
}

function initTheme() {
  // Prefer server-rendered data-theme (already set on <html>)
  // but allow override from localStorage for public pages
  const stored = localStorage.getItem(THEME_KEY);
  const htmlTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const theme = stored || htmlTheme;
  applyTheme(theme);
}

document.getElementById('themeToggle')?.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);

  // Persist preference for authenticated users via API
  fetch('/api/update-theme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
    body: JSON.stringify({ theme: next }),
  }).catch(() => {});
});

// ── Sidebar ──────────────────────────────────────────────────────────────────
const sidebar  = document.getElementById('sidebar');
const overlay  = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburger');
const sidebarClose = document.getElementById('sidebarClose');

function openSidebar() {
  sidebar?.classList.add('open');
  overlay?.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  sidebar?.classList.remove('open');
  overlay?.classList.remove('open');
  document.body.style.overflow = '';
}

hamburger?.addEventListener('click', openSidebar);
sidebarClose?.addEventListener('click', closeSidebar);
overlay?.addEventListener('click', closeSidebar);

// Close sidebar on Esc
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSidebar();
});

// ── Toast Notifications ──────────────────────────────────────────────────────
const toastContainer = document.getElementById('toastContainer');

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'danger'|'warning'|'info'} [type='info']
 * @param {number} [duration=4000] ms before auto-dismiss
 */
function showToast(message, type = 'info', duration = 4000) {
  const icons = { success: '✔', danger: '✖', warning: '⚠', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span style="font-size:1rem;flex-shrink:0">${icons[type] ?? 'ℹ'}</span>
    <span style="flex:1">${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;color:currentColor;opacity:.6;padding:0 4px;font-size:.9rem">✕</button>
  `;
  toastContainer?.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 350);
  }, duration);
}

// Make global
window.showToast = showToast;

// ── Loading Overlay ──────────────────────────────────────────────────────────
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingMsg     = document.getElementById('loadingMsg');

function showLoading(message = 'Processing…') {
  if (!loadingOverlay) return;
  if (loadingMsg) loadingMsg.textContent = message;
  loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
  loadingOverlay?.classList.add('hidden');
}

window.showLoading = showLoading;
window.hideLoading = hideLoading;

// ── Auto-dismiss Flash Messages ──────────────────────────────────────────────
function initFlashAutoDismiss() {
  const container = document.getElementById('flashContainer');
  if (!container) return;
  const flashes = container.querySelectorAll('.flash');
  flashes.forEach((el, i) => {
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(-8px)';
      el.style.transition = 'opacity .4s, transform .4s';
      setTimeout(() => el.remove(), 400);
    }, 5000 + i * 500);
  });
}

// ── Drag-and-Drop File Zones ─────────────────────────────────────────────────
function initDropZones() {
  document.querySelectorAll('.drop-zone').forEach(zone => {
    const input = zone.querySelector('input[type="file"]');

    zone.addEventListener('dragover', e => {
      e.preventDefault();
      zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const files = e.dataTransfer?.files;
      if (files?.length && input) {
        input.files = files;
        updateDropLabel(zone, files[0].name);
      }
    });

    input?.addEventListener('change', () => {
      if (input.files?.length) {
        updateDropLabel(zone, input.files[0].name);
      }
    });
  });
}

function updateDropLabel(zone, filename) {
  let label = zone.querySelector('.drop-selected');
  if (!label) {
    label = document.createElement('p');
    label.className = 'drop-selected';
    zone.appendChild(label);
  }
  label.textContent = `📄 ${filename}`;
}

// ── Password Strength Meter ───────────────────────────────────────────────────
function initPasswordStrength() {
  const pwField = document.getElementById('password');
  const fill    = document.getElementById('strengthFill');
  const text    = document.getElementById('strengthText');
  if (!pwField || !fill || !text) return;

  pwField.addEventListener('input', () => {
    const pw = pwField.value;
    const score = calcStrength(pw);
    const levels = [
      { label: 'Too short',  color: '#ef4444', pct: 10 },
      { label: 'Weak',       color: '#ef4444', pct: 25 },
      { label: 'Fair',       color: '#f59e0b', pct: 55 },
      { label: 'Good',       color: '#3b82f6', pct: 78 },
      { label: 'Strong',     color: '#10b981', pct: 100 },
    ];
    const lvl = levels[Math.min(score, 4)];
    fill.style.width    = lvl.pct + '%';
    fill.style.background = lvl.color;
    text.textContent    = lvl.label;
    text.style.color    = lvl.color;
  });
}

function calcStrength(pw) {
  if (pw.length < 6)  return 0;
  let score = 1;
  if (pw.length >= 10) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return Math.min(score, 4);
}

// ── Copy to clipboard ─────────────────────────────────────────────────────────
function copyToClipboard(text) {
  navigator.clipboard?.writeText(text)
    .then(() => showToast('Copied to clipboard!', 'success', 2500))
    .catch(() => showToast('Copy failed.', 'danger', 2500));
}
window.copyToClipboard = copyToClipboard;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initFlashAutoDismiss();
  initDropZones();
  initPasswordStrength();
});
