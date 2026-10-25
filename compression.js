/**
 * TextTool – Compression Page JavaScript
 * Handles: tab switching, algorithm info toggle, file info preview,
 *          inline compress/decompress via API, savings bar animation.
 */

'use strict';

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.compress-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.compress-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.compress-tab-pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab)?.classList.add('active');
  });
});

// ── Algorithm info panel toggle (compress tab) ────────────────────────────────
document.querySelectorAll('input[name="algorithm"]').forEach(radio => {
  radio.addEventListener('change', () => {
    const huffInfo = document.getElementById('huffmanInfo');
    const zlibInfo = document.getElementById('zlibInfo');
    if (!huffInfo || !zlibInfo) return;
    if (radio.value === 'huffman') {
      huffInfo.style.display = 'block';
      zlibInfo.style.display = 'none';
    } else {
      huffInfo.style.display = 'none';
      zlibInfo.style.display = 'block';
    }
  });
});

// ── File info preview when file selected ─────────────────────────────────────
const compressFile = document.getElementById('compressFile');
const fileInfo     = document.getElementById('fileInfo');
const fileNameEl   = document.getElementById('fileName');
const fileSizeEl   = document.getElementById('fileSize');

compressFile?.addEventListener('change', () => {
  const file = compressFile.files[0];
  if (!file) { fileInfo?.classList.add('hidden'); return; }
  fileInfo?.classList.remove('hidden');
  fileNameEl.textContent = file.name;
  fileSizeEl.textContent = humanSize(file.size);
});

// ── Compress form submission ──────────────────────────────────────────────────
document.getElementById('compressForm')?.addEventListener('submit', function(e) {
  const file = compressFile?.files[0];
  if (!file) {
    e.preventDefault();
    showToast('Please select a .txt file first.', 'warning');
    return;
  }
  showLoading('Compressing file…');
  document.getElementById('compressBtn').disabled = true;
});

// ── Decompress form submission ────────────────────────────────────────────────
document.getElementById('decompressForm')?.addEventListener('submit', function(e) {
  const file = document.getElementById('decompressFile')?.files[0];
  if (!file) {
    e.preventDefault();
    showToast('Please select a compressed file.', 'warning');
    return;
  }
  showLoading('Decompressing file…');
  document.getElementById('decompressBtn').disabled = true;
});

// ── Inline compression via API ────────────────────────────────────────────────
let lastCompressedB64 = null;
let lastAlgorithm     = 'huffman';

document.getElementById('btnInlineCompress')?.addEventListener('click', async () => {
  const text = document.getElementById('inlineText')?.value?.trim();
  if (!text) { showToast('Please enter some text to compress.', 'warning'); return; }
  if (text.length > 50000) { showToast('Text exceeds 50,000 character limit.', 'warning'); return; }

  const algo = document.querySelector('input[name="inlineAlgo"]:checked')?.value || 'huffman';

  showLoading('Compressing…');
  document.getElementById('btnInlineCompress').disabled = true;

  try {
    const res  = await apiPost('/api/compress', { text, algorithm: algo });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'Compression failed.', 'danger');
      return;
    }

    lastCompressedB64 = data.compressed_b64;
    lastAlgorithm     = algo;

    displayMetrics(data);
    document.getElementById('btnInlineDecompress').disabled = false;
    showToast(`Compressed! Saved ${data.savings_percent}%`, 'success');
  } catch (err) {
    console.error(err);
    showToast('Compression failed. Check your connection.', 'danger');
  } finally {
    hideLoading();
    document.getElementById('btnInlineCompress').disabled = false;
  }
});

document.getElementById('btnInlineDecompress')?.addEventListener('click', async () => {
  if (!lastCompressedB64) {
    showToast('Compress some text first.', 'warning');
    return;
  }

  showLoading('Decompressing…');

  try {
    const res  = await apiPost('/api/decompress', {
      compressed_b64: lastCompressedB64,
      algorithm: lastAlgorithm,
    });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'Decompression failed.', 'danger');
      return;
    }

    document.getElementById('inlineText').value = data.decompressed_text;
    showToast('Decompressed successfully!', 'success');
  } catch (err) {
    console.error(err);
    showToast('Decompression failed.', 'danger');
  } finally {
    hideLoading();
  }
});

document.getElementById('btnInlineClear')?.addEventListener('click', () => {
  document.getElementById('inlineText').value = '';
  document.getElementById('inlineResult')?.classList.remove('visible');
  document.getElementById('btnInlineDecompress').disabled = true;
  lastCompressedB64 = null;
});

// Download inline compressed result
document.getElementById('btnDownloadInline')?.addEventListener('click', () => {
  if (!lastCompressedB64) { showToast('Nothing to download.', 'warning'); return; }
  const bytes  = base64ToBytes(lastCompressedB64);
  const blob   = new Blob([bytes], { type: 'application/octet-stream' });
  const ext    = lastAlgorithm === 'zlib' ? 'zlib' : 'huff';
  triggerDownload(blob, `compressed.${ext}`);
});

// Copy result info
document.getElementById('btnCopyResult')?.addEventListener('click', () => {
  const origSize  = document.getElementById('origSize')?.textContent;
  const compSize  = document.getElementById('compSize')?.textContent;
  const ratio     = document.getElementById('compRatio')?.textContent;
  const saved     = document.getElementById('compSaved')?.textContent;
  const info = `Compression Result\n  Original: ${origSize}\n  Compressed: ${compSize}\n  Ratio: ${ratio}\n  Saved: ${saved}`;
  copyToClipboard(info);
});

// ── Display metrics ───────────────────────────────────────────────────────────
function displayMetrics(data) {
  const result = document.getElementById('inlineResult');
  if (!result) return;

  document.getElementById('origSize').textContent  = humanSize(data.original_size);
  document.getElementById('compSize').textContent  = humanSize(data.compressed_size);
  document.getElementById('compRatio').textContent = `${data.compression_ratio}×`;
  document.getElementById('compSaved').textContent = humanSize(Math.max(data.bytes_saved, 0));
  document.getElementById('savingsPct').textContent = `${data.savings_percent}%`;

  // Animate savings bar
  const bar = document.getElementById('savingsBar');
  if (bar) {
    bar.style.width = '0%';
    setTimeout(() => {
      bar.style.width = Math.max(0, Math.min(100, data.savings_percent)) + '%';
    }, 50);
  }

  result.classList.add('visible');
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function base64ToBytes(b64) {
  const binary = atob(b64);
  const bytes  = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
