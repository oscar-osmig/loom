/**
 * Instance store — tracks which Loom instance is active.
 *
 * "loom" = General (community knowledge, default)
 * "user:<email>" = personal instance
 */

import { triggerGraphReset } from './ui.svelte.js';

function readInstance() {
    try { return sessionStorage.getItem('loom_instance') || 'loom'; } catch { return 'loom'; }
}

function readInstanceName() {
    try { return sessionStorage.getItem('loom_instance_name') || 'General'; } catch { return 'General'; }
}

export const instance = $state({
    current: readInstance(),
    currentName: readInstanceName(),
    list: [],
    dropdownOpen: false,
});

export function setInstance(instanceName, displayName) {
    instance.current = instanceName;
    instance.currentName = displayName;
    instance.dropdownOpen = false;
    try {
        sessionStorage.setItem('loom_instance', instanceName);
        sessionStorage.setItem('loom_instance_name', displayName);
    } catch {}
    triggerGraphReset();
}

export function setDropdownOpen(value) {
    instance.dropdownOpen = value;
}

export function setInstanceList(list) {
    instance.list = list;
}
