// Court Replay - painel publico de clips (somente visualizar e baixar)
document.addEventListener('DOMContentLoaded', () => {
  const DEFAULT_START = '00:00';
  const DEFAULT_END = '23:59';
  const AUTO_REFRESH_MS = 30000;

  let clips = [];
  let currentClipId = null;
  let lastFocus = null;

  const $ = (id) => document.getElementById(id);
  const refreshBtn = $('refreshBtn');
  const searchBtn = $('searchBtn');
  const clearBtn = $('clearBtn');
  const searchStart = $('searchStart');
  const searchEnd = $('searchEnd');
  const resultsCount = $('resultsCount');
  const clipsGrid = $('clipsGrid');
  const videoModal = $('videoModal');
  const modalClose = $('modalClose');
  const modalDownload = $('modalDownload');
  const modalOverlay = videoModal.querySelector('.modal-overlay');
  const previewVideo = $('previewVideo');
  const modalTitle = $('modalTitle');
  const toastContainer = $('toastContainer');
  const statusPill = $('statusPill');
  const statusLabel = $('statusLabel');
  const chips = Array.from(document.querySelectorAll('.chip'));

  const ICON_PLAY = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>';
  const ICON_EMPTY = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>';

  // ----- Eventos -----
  loadClips();
  checkStatus();
  setInterval(() => {
    if (document.hidden || videoModal.classList.contains('active')) return;
    loadClips(searchStart.value, searchEnd.value, { silent: true });
    checkStatus();
  }, AUTO_REFRESH_MS);

  refreshBtn.addEventListener('click', async () => {
    await loadClips(searchStart.value, searchEnd.value, { silent: true });
    showToast('Lista atualizada');
  });

  searchBtn.addEventListener('click', () => {
    setPreset(null);
    loadClips(searchStart.value, searchEnd.value);
  });

  clearBtn.addEventListener('click', () => applyPreset('all'));

  [searchStart, searchEnd].forEach((input) => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchBtn.click();
    });
  });

  chips.forEach((chip) => chip.addEventListener('click', () => applyPreset(chip.dataset.preset)));

  // Delegacao: um unico listener para todos os cards
  clipsGrid.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    const id = target.dataset.id;
    if (target.dataset.action === 'preview') openPreview(id, target);
    if (target.dataset.action === 'download') downloadClip(id);
  });

  modalClose.addEventListener('click', closeModal);
  modalOverlay.addEventListener('click', closeModal);
  modalDownload.addEventListener('click', () => currentClipId && downloadClip(currentClipId));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && videoModal.classList.contains('active')) closeModal();
  });

  // ----- Atalhos de horario -----
  function applyPreset(name) {
    const pad = (n) => String(n).padStart(2, '0');
    let start = DEFAULT_START;
    let end = DEFAULT_END;

    if (name === 'hour') {
      const now = new Date();
      const before = new Date(now.getTime() - 60 * 60 * 1000);
      // Se a janela cruzar a meia-noite, comeca em 00:00.
      start = before.getDate() === now.getDate() ? `${pad(before.getHours())}:${pad(before.getMinutes())}` : DEFAULT_START;
      end = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    } else if (name === 'morning') {
      start = '05:00'; end = '11:59';
    } else if (name === 'afternoon') {
      start = '12:00'; end = '17:59';
    } else if (name === 'night') {
      start = '18:00'; end = '23:59';
    }

    searchStart.value = start;
    searchEnd.value = end;
    setPreset(name);
    loadClips(start, end);
  }

  function setPreset(name) {
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.preset === name)));
  }

  // ----- Dados -----
  async function loadClips(startTime, endTime, { silent = false } = {}) {
    if (!silent) {
      clipsGrid.setAttribute('aria-busy', 'true');
      clipsGrid.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
      resultsCount.textContent = '';
    }

    try {
      const params = new URLSearchParams();
      if (startTime) params.append('start', startTime);
      if (endTime) params.append('end', endTime);

      const response = await fetch('/api/clips' + (params.toString() ? '?' + params : ''));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      const next = data.clips || [];
      // Em atualizacao silenciosa, so redesenha se algo mudou (evita piscar).
      if (!silent || JSON.stringify(next.map((c) => c.id)) !== JSON.stringify(clips.map((c) => c.id))) {
        clips = next;
        renderClips(clips);
      }
    } catch (error) {
      if (silent) {
        showToast('Não foi possível atualizar', 'error');
        return;
      }
      clipsGrid.setAttribute('aria-busy', 'false');
      clipsGrid.innerHTML = `
        <div class="empty-state">
          ${ICON_EMPTY}
          <h3>Não foi possível carregar</h3>
          <p>Verifique sua conexão e tente novamente.</p>
        </div>`;
    }
  }

  async function checkStatus() {
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      const online = data.agent === 'online';
      statusPill.className = `status-pill ${online ? 'online' : 'offline'}`;
      statusLabel.textContent = online ? 'Quadra online' : 'Quadra offline';
    } catch {
      statusPill.className = 'status-pill offline';
      statusLabel.textContent = 'Sem conexão';
    }
  }

  // ----- Renderizacao -----
  function renderClips(list) {
    clipsGrid.setAttribute('aria-busy', 'false');

    if (list.length === 0) {
      resultsCount.textContent = '';
      clipsGrid.innerHTML = `
        <div class="empty-state">
          ${ICON_EMPTY}
          <h3>Nenhum replay por aqui</h3>
          <p>Nada foi gravado nesse intervalo. Aperte o botão do meio do mouse na quadra e atualize em ~5 segundos.</p>
        </div>`;
      return;
    }

    resultsCount.textContent = `${list.length} ${list.length === 1 ? 'replay' : 'replays'}`;
    clipsGrid.innerHTML = list.map(createClipCard).join('');
  }

  function createClipCard(clip, index) {
    const id = escapeHtml(clip.id);
    const delay = Math.min(index, 12) * 40;
    return `
      <article class="clip-card" style="animation-delay:${delay}ms">
        <button class="clip-thumb" data-action="preview" data-id="${id}" aria-label="Assistir replay das ${formatTime(clip.triggerTime)}">
          <span class="play-btn">${ICON_PLAY}</span>
          <span class="duration-badge">${formatDuration(clip.duration)}</span>
        </button>
        <div class="clip-card-body">
          <div>
            <div class="clip-card-time">${formatTime(clip.triggerTime)}</div>
            <div class="clip-card-meta">${formatSize(clip.size)}</div>
          </div>
          <div class="clip-card-actions">
            <button class="btn btn-secondary btn-sm" data-action="preview" data-id="${id}">Assistir</button>
            <button class="btn btn-primary btn-sm" data-action="download" data-id="${id}">Baixar</button>
          </div>
        </div>
      </article>`;
  }

  // ----- Modal -----
  function openPreview(clipId, trigger) {
    const clip = clips.find((c) => c.id === clipId);
    if (!clip) return;

    lastFocus = trigger || document.activeElement;
    currentClipId = clipId;
    modalTitle.textContent = `Replay das ${formatTime(clip.triggerTime)}`;
    previewVideo.src = `/api/clips/${encodeURIComponent(clipId)}/download`;
    videoModal.classList.add('active');
    document.body.style.overflow = 'hidden';
    modalClose.focus();
    previewVideo.play().catch(() => {});
  }

  function closeModal() {
    videoModal.classList.remove('active');
    document.body.style.overflow = '';
    previewVideo.pause();
    previewVideo.removeAttribute('src');
    previewVideo.load();
    currentClipId = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function downloadClip(clipId) {
    window.location.href = `/api/clips/${encodeURIComponent(clipId)}/download`;
  }

  // ----- Utilitarios -----
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 2600);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function formatTime(isoString) {
    if (!isoString) return '--:--:--';
    return new Date(isoString).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function formatDuration(seconds) {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  }

  function formatSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return `${size.toFixed(1)} ${units[i]}`;
  }
});
