'use strict';

// ── Config ────────────────────────────────────────────────────────────────────

const REFRESH_INTERVAL = 15_000; // ms

const STATUS = {
    downloading:         { label: 'Téléchargement', cls: 's-downloading' },
    finishing:           { label: 'Finalisation',   cls: 's-downloading' },
    extracting:          { label: 'Extraction',     cls: 's-downloading' },
    hash_checking:       { label: 'Vérification',   cls: 's-default'     },
    waiting:             { label: 'En attente',     cls: 's-default'     },
    filehosting_waiting: { label: 'En attente',     cls: 's-default'     },
    finished:            { label: 'Terminé',        cls: 's-finished'    },
    seeding:             { label: 'Partage',        cls: 's-seeding'     },
    paused:              { label: 'En pause',       cls: 's-paused'      },
    error:               { label: 'Erreur',         cls: 's-error'       },
};

// ── State ─────────────────────────────────────────────────────────────────────

let tasks = [];

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '–';
    const units = ['o', 'Ko', 'Mo', 'Go', 'To'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + '\u00a0' + units[i];
}

function formatSpeed(bps) {
    if (!bps || bps <= 0) return '–';
    return formatBytes(bps) + '/s';
}

function getProgress(task) {
    const size = task.size || 0;
    const done = task.additional?.transfer?.size_downloaded || 0;
    if (!size) return 0;
    return Math.min(100, Math.round((done / size) * 100));
}

function esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function toast(msg, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), 4500);
}

// ── Render ────────────────────────────────────────────────────────────────────

function showState(name) {
    ['loading', 'empty', 'error'].forEach(s => {
        document.getElementById(`state-${s}`).hidden = (s !== name);
    });
    document.getElementById('tasks-table').hidden = (name !== null);
}

function setOnline(online) {
    document.getElementById('status-dot').className  = 'dot ' + (online ? 'online' : 'offline');
    document.getElementById('status-text').textContent = online ? 'Connecté' : 'Hors ligne';
}

function renderTasks(list) {
    document.getElementById('task-count').textContent = list.length;

    if (!list.length) {
        showState('empty');
        return;
    }

    document.getElementById('state-loading').hidden = true;
    document.getElementById('state-empty').hidden   = true;
    document.getElementById('state-error').hidden   = true;
    document.getElementById('tasks-table').hidden   = false;

    document.getElementById('tasks-body').innerHTML = list.map(task => {
        const st       = STATUS[task.status] ?? { label: task.status, cls: 's-default' };
        const progress = getProgress(task);
        const speed    = task.additional?.transfer?.speed_download ?? 0;
        const isFinished = task.status === 'finished';

        return `
        <tr data-id="${esc(task.id)}">
            <td><div class="task-name" title="${esc(task.title)}">${esc(task.title)}</div></td>
            <td class="col-size"><span class="task-size">${formatBytes(task.size)}</span></td>
            <td><span class="status-badge ${st.cls}">${st.label}</span></td>
            <td class="col-speed-td"><span class="speed">${task.status === 'downloading' ? formatSpeed(speed) : '–'}</span></td>
            <td>
                <div class="progress-wrap">
                    <div class="progress-bar">
                        <div class="progress-fill ${isFinished ? 'done' : ''}" style="width:${progress}%"></div>
                    </div>
                    <span class="progress-pct">${progress}%</span>
                </div>
            </td>
            <td>
                <button
                    class="btn-ghost"
                    data-action="delete"
                    data-id="${esc(task.id)}"
                    title="Supprimer"
                    aria-label="Supprimer ${esc(task.title)}"
                >✕</button>
            </td>
        </tr>`;
    }).join('');
}

// ── API ───────────────────────────────────────────────────────────────────────

async function fetchTasks() {
    try {
        const res  = await fetch('api/list');
        const data = await res.json();
        if (!data.success) throw new Error(data.error ?? 'Erreur inconnue');
        tasks = data.tasks ?? [];
        renderTasks(tasks);
        setOnline(true);
    } catch (err) {
        setOnline(false);
        document.getElementById('state-loading').hidden = true;
        document.getElementById('state-error').hidden   = false;
        document.getElementById('tasks-table').hidden   = true;
        document.getElementById('state-empty').hidden   = true;
        document.getElementById('state-error-msg').textContent = err.message;
        console.error('[fetchTasks]', err);
    }
}

async function deleteTask(id) {
    try {
        const res  = await fetch('api/delete', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ ids: [id] }),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        toast('Tâche supprimée', 'success');
        await fetchTasks();
    } catch (err) {
        toast('Erreur : ' + err.message, 'error');
    }
}

async function deleteFinished() {
    const ids = tasks.filter(t => t.status === 'finished').map(t => t.id);
    if (!ids.length) {
        toast('Aucune tâche terminée à supprimer', 'info');
        return;
    }
    try {
        const res  = await fetch('api/delete', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ ids }),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        toast(`${ids.length} tâche(s) supprimée(s)`, 'success');
        await fetchTasks();
    } catch (err) {
        toast('Erreur : ' + err.message, 'error');
    }
}

async function addTorrents() {
    const btn        = document.getElementById('add-btn');
    const feedback   = document.getElementById('add-feedback');
    const loaderMsg  = document.getElementById('loader-msg');
    const destination = document.getElementById('destination-select').value;
    const total      = selectedFiles.length;

    btn.disabled = true;
    btn.querySelector('.btn-text').hidden   = true;
    btn.querySelector('.btn-loader').hidden = false;
    feedback.hidden = true;

    let succeeded = 0;
    let failed    = 0;

    for (let i = 0; i < total; i++) {
        const file     = selectedFiles[i];
        const statusEl = document.getElementById(`file-status-${i}`);
        const itemEl   = document.getElementById(`file-item-${i}`);

        loaderMsg.textContent = `${i + 1} / ${total}`;
        statusEl.textContent  = '⏳';
        itemEl.className      = 'file-item processing';

        try {
            const formData = new FormData();
            formData.append('torrent', file);
            formData.append('destination', destination);

            const res  = await fetch('api/add', { method: 'POST', body: formData });
            const data = await res.json();
            if (!data.success) throw new Error(data.error);

            statusEl.textContent = '✓';
            itemEl.className     = 'file-item done';
            succeeded++;
        } catch (err) {
            statusEl.textContent = '✕';
            statusEl.title       = err.message;
            itemEl.className     = 'file-item failed';
            failed++;
            console.error(`[addTorrents] ${file.name}:`, err);
        }
    }

    // Résumé
    if (failed === 0) {
        feedback.className   = 'feedback success';
        feedback.textContent = `${succeeded} torrent(s) ajouté(s) au NAS avec succès !`;
    } else if (succeeded === 0) {
        feedback.className   = 'feedback error';
        feedback.textContent = `Échec pour tous les torrents (${failed}/${total}). Voir la console pour les détails.`;
    } else {
        feedback.className   = 'feedback success';
        feedback.textContent = `${succeeded}/${total} réussi(s) — ${failed} erreur(s).`;
    }
    feedback.hidden = false;

    btn.disabled = false;
    btn.querySelector('.btn-text').hidden   = false;
    btn.querySelector('.btn-loader').hidden = true;

    if (succeeded) await fetchTasks();
}

// ── Events ────────────────────────────────────────────────────────────────────

// ── File zone ─────────────────────────────────────────────────────────────────

let selectedFiles = [];

function clearFile() {
    document.getElementById('torrent-input').value = '';
    document.getElementById('add-row').hidden       = true;
    document.getElementById('file-zone').hidden     = false;
    document.getElementById('add-feedback').hidden  = true;
    selectedFiles = [];
}

function renderFileList() {
    document.getElementById('file-list').innerHTML = selectedFiles.map((f, i) => `
        <div class="file-item" id="file-item-${i}">
            <span class="file-item-icon">📄</span>
            <span class="file-item-name" title="${esc(f.name)}">${esc(f.name)}</span>
            <span class="file-item-status" id="file-status-${i}"></span>
        </div>
    `).join('');
}

function selectFiles(fileList) {
    const files = Array.from(fileList).filter(f => f.name.toLowerCase().endsWith('.torrent'));
    if (!files.length) {
        toast('Aucun fichier .torrent sélectionné', 'error');
        return;
    }
    const rejected = Array.from(fileList).length - files.length;
    if (rejected) toast(`${rejected} fichier(s) ignoré(s) (pas .torrent)`, 'info');

    selectedFiles = files;
    renderFileList();
    document.getElementById('add-row').hidden      = false;
    document.getElementById('file-zone').hidden    = true;
    document.getElementById('add-feedback').hidden = true;
}

document.getElementById('file-zone').addEventListener('click', () => {
    document.getElementById('torrent-input').click();
});

document.getElementById('torrent-input').addEventListener('change', e => {
    selectFiles(e.target.files);
});

document.getElementById('file-zone').addEventListener('dragover', e => {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
});

document.getElementById('file-zone').addEventListener('dragleave', e => {
    e.currentTarget.classList.remove('drag-over');
});

document.getElementById('file-zone').addEventListener('drop', e => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    selectFiles(e.dataTransfer.files);
});

document.getElementById('clear-btn').addEventListener('click', clearFile);

document.getElementById('add-form').addEventListener('submit', async e => {
    e.preventDefault();
    if (selectedFiles.length) await addTorrents();
});

document.getElementById('refresh-btn').addEventListener('click', () => fetchTasks());

document.getElementById('delete-finished-btn').addEventListener('click', () => deleteFinished());

document.getElementById('tasks-body').addEventListener('click', e => {
    const btn = e.target.closest('[data-action="delete"]');
    if (btn) deleteTask(btn.dataset.id);
});

// ── Destinations ─────────────────────────────────────────────────────────────

async function loadDestinations() {
    const sel = document.getElementById('destination-select');
    try {
        const res  = await fetch('api/destinations');
        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        if (!data.destinations.length) {
            sel.innerHTML = '<option value="">Aucune destination configurée</option>';
            return;
        }

        sel.innerHTML = data.destinations
            .map(d => `<option value="${esc(d.path)}">${esc(d.name)}</option>`)
            .join('');
    } catch (err) {
        sel.innerHTML = '<option value="">Erreur chargement destinations</option>';
        console.error('[loadDestinations]', err);
    }
}

// ── Init ──────────────────────────────────────────────────────────────────────

loadDestinations();
fetchTasks();
setInterval(fetchTasks, REFRESH_INTERVAL);
