/**
 * File store — manages training files saved in browser localStorage.
 */

const STORAGE_KEY = 'loom_training_files';

function load() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
}

function persist(items) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch {}
}

export const fileStore = $state({
    items: load(),       // [{ name, content, uploadedAt }]
    activeFile: null,    // name of file being viewed
    editing: false,
    listOpen: true,      // whether file sidebar is visible
});

export function addFile(name, content) {
    const idx = fileStore.items.findIndex(f => f.name === name);
    if (idx >= 0) {
        fileStore.items[idx].content = content;
        fileStore.items[idx].uploadedAt = Date.now();
    } else {
        fileStore.items.push({ name, content, uploadedAt: Date.now() });
    }
    persist(fileStore.items);
}

export function removeFile(name) {
    fileStore.items = fileStore.items.filter(f => f.name !== name);
    if (fileStore.activeFile === name) {
        fileStore.activeFile = null;
        fileStore.editing = false;
    }
    persist(fileStore.items);
}

export function updateFileContent(name, content) {
    const file = fileStore.items.find(f => f.name === name);
    if (file) {
        file.content = content;
        persist(fileStore.items);
    }
}

export function getFile(name) {
    return fileStore.items.find(f => f.name === name) || null;
}

export function selectFile(name) {
    fileStore.activeFile = name;
    fileStore.editing = false;
}

export function deselectFile() {
    fileStore.activeFile = null;
    fileStore.editing = false;
}

export function setEditing(value) {
    fileStore.editing = value;
}

export function toggleFileList() {
    fileStore.listOpen = !fileStore.listOpen;
}

export function closeFileList() {
    fileStore.listOpen = false;
}

export function clearAllFiles() {
    fileStore.items = [];
    fileStore.activeFile = null;
    fileStore.editing = false;
    persist(fileStore.items);
}
