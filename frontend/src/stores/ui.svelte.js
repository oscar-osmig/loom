/**
 * UI store — general interface state (Svelte 5 runes).
 * State is wrapped in an object since Svelte 5 modules can't export reassigned $state.
 */

function isLoggedIn() {
    try { return !!localStorage.getItem('loom_user'); } catch { return false; }
}

function wasVizOpen() {
    try { return sessionStorage.getItem('loom_viz_open') === 'true'; } catch { return false; }
}

export const ui = $state({
    infoPanelOpen: false,
    infoPanelTitle: '',
    infoPanelContent: '',
    vizOpen: wasVizOpen(),
    trainInfoOpen: false,
    aboutOpen: false,
    settingsOpen: false,
    stylePageOpen: false,
    loadResultsOpen: false,
    leaderboardOpen: false,
    loadResultsData: null,
    headerLocked: !isLoggedIn(),
    graphVersion: 0,
});

export function showInfoPanel(title, content) {
    ui.infoPanelTitle = title;
    ui.infoPanelContent = content;
    ui.infoPanelOpen = true;
}

export function closeInfoPanel() {
    ui.infoPanelOpen = false;
    ui.infoPanelTitle = '';
    ui.infoPanelContent = '';
}

export function setVizOpen(value) {
    ui.vizOpen = value;
    try { sessionStorage.setItem('loom_viz_open', value ? 'true' : 'false'); } catch {}
}
export function setTrainInfoOpen(value) { ui.trainInfoOpen = value; }
export function setAboutOpen(value) { ui.aboutOpen = value; if (value) { ui.settingsOpen = false; ui.stylePageOpen = false; } }
export function setSettingsOpen(value) { ui.settingsOpen = value; if (value) { ui.aboutOpen = false; ui.stylePageOpen = false; } }
export function setStylePageOpen(value) { ui.stylePageOpen = value; if (value) { ui.aboutOpen = false; ui.settingsOpen = false; ui.loadResultsOpen = false; } }
export function setLeaderboardOpen(value) { ui.leaderboardOpen = value; if (value) { ui.aboutOpen = false; ui.settingsOpen = false; ui.stylePageOpen = false; ui.loadResultsOpen = false; } }
export function showLoadResults(data) { ui.loadResultsData = data; ui.loadResultsOpen = true; ui.aboutOpen = false; ui.settingsOpen = false; ui.stylePageOpen = false; ui.leaderboardOpen = false; }
export function closeLoadResults() { ui.loadResultsOpen = false; ui.loadResultsData = null; }
export function setHeaderLocked(value) { ui.headerLocked = value; }
export function triggerGraphReset() {
    ui.graphVersion++;
    try { sessionStorage.removeItem('loom_graph_layout'); } catch {}
}
