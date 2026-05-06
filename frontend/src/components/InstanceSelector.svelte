<script>
    import { instance, setInstance, setDropdownOpen, setInstanceList } from '../stores/instance.svelte.js';
    import { auth, isAuthenticated, isGoogleUser } from '../stores/auth.svelte.js';
    import { triggerGraphReset } from '../stores/ui.svelte.js';
    import { fetchInstances, createInstance, deleteInstance } from '../lib/api.js';

    let wrapperEl = $state(null);
    let creating = $state(false);
    let deleting = $state(null);
    let showNameInput = $state(false);
    let nameValue = $state('');
    let nameInputEl = $state(null);

    function toggle() {
        setDropdownOpen(!instance.dropdownOpen);
        showNameInput = false;
        nameValue = '';
    }

    function handleClickOutside(e) {
        if (wrapperEl && !wrapperEl.contains(e.target) && document.documentElement.contains(e.target)) {
            setDropdownOpen(false);
            showNameInput = false;
            nameValue = '';
        }
    }

    function selectInstance(inst) {
        if (inst.instance_name === instance.current) {
            setDropdownOpen(false);
            return;
        }
        setInstance(inst.instance_name, inst.display_name);
    }

    function handleCreateClick() {
        showNameInput = true;
        nameValue = '';
        setTimeout(() => nameInputEl?.focus(), 0);
    }

    function handleNameKeydown(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitCreate();
        } else if (e.key === 'Escape') {
            showNameInput = false;
            nameValue = '';
        }
    }

    async function submitCreate() {
        const name = nameValue.trim();
        if (!name || creating || !auth.email) return;
        creating = true;
        const data = await createInstance(auth.email, name);
        creating = false;
        if (!data.error) {
            const newInst = {
                instance_name: data.instance_name,
                display_name: data.display_name,
                is_personal: true,
            };
            instance.list = [...instance.list, newInst];
            setInstance(data.instance_name, data.display_name);
            showNameInput = false;
            nameValue = '';
        }
    }

    async function handleDelete(e, inst) {
        e.stopPropagation();
        if (deleting || !auth.email) return;
        deleting = inst.instance_name;
        const data = await deleteInstance(auth.email, inst.instance_name);
        deleting = null;
        if (!data.error) {
            instance.list = instance.list.filter(i => i.instance_name !== inst.instance_name);
            if (instance.current === inst.instance_name) {
                setInstance('loom', 'General');
            }
        }
    }

    // Load instances when user is authenticated
    $effect(() => {
        const email = auth.email;
        if (email) {
            fetchInstances(email).then(data => {
                if (data.instances) {
                    setInstanceList(data.instances);
                }
            });
        }
    });

    const canCreate = $derived(isGoogleUser());
</script>

<svelte:window onclick={handleClickOutside} />

<div class="instance-selector" bind:this={wrapperEl}>
    <button class="instance-btn" onclick={toggle} title="Switch Loom instance">
        <svg class="shield-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <span class="instance-name">{instance.currentName}</span>
        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
        </svg>
    </button>

    {#if instance.dropdownOpen}
        <div class="instance-dropdown">
            <div class="instance-list">
                {#each instance.list as inst (inst.instance_name)}
                    <div class="instance-row">
                        <button
                            class="instance-option"
                            class:active={inst.instance_name === instance.current}
                            onclick={() => selectInstance(inst)}
                        >
                            {#if inst.is_personal}
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                            {:else}
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="10"/>
                                </svg>
                            {/if}
                            <span>{inst.display_name}</span>
                            {#if inst.instance_name === instance.current}
                                <svg class="check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="20 6 9 17 4 12"/>
                                </svg>
                            {/if}
                        </button>
                        {#if inst.is_personal}
                            <button
                                class="delete-btn"
                                onclick={(e) => handleDelete(e, inst)}
                                disabled={deleting === inst.instance_name}
                                title="Delete instance"
                            >
                                {#if deleting === inst.instance_name}
                                    <span class="deleting-dot">...</span>
                                {:else}
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                                    </svg>
                                {/if}
                            </button>
                        {/if}
                    </div>
                {/each}
            </div>

            {#if canCreate}
                <div class="dropdown-divider"></div>
                {#if showNameInput}
                    <div class="name-input-row">
                        <input
                            class="name-input"
                            type="text"
                            placeholder="Instance name..."
                            maxlength="30"
                            bind:this={nameInputEl}
                            bind:value={nameValue}
                            onkeydown={handleNameKeydown}
                            disabled={creating}
                        />
                        <button class="name-submit" onclick={submitCreate} disabled={creating || !nameValue.trim()}>
                            {#if creating}
                                ...
                            {:else}
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="20 6 9 17 4 12"/>
                                </svg>
                            {/if}
                        </button>
                    </div>
                {:else}
                    <button class="instance-option create" onclick={handleCreateClick}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="12" y1="5" x2="12" y2="19"/>
                            <line x1="5" y1="12" x2="19" y2="12"/>
                        </svg>
                        <span>Create</span>
                    </button>
                {/if}
            {/if}
        </div>
    {/if}
</div>

<style>
    .instance-selector {
        position: relative;
    }

    .instance-btn {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        color: var(--text-secondary);
        padding: 0.375rem 0.625rem;
        border-radius: 8px;
        font-size: 0.8125rem;
        font-weight: 500;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.2s;
    }

    .instance-btn:hover {
        border-color: var(--accent);
        color: var(--text-primary);
    }

    .shield-icon {
        flex-shrink: 0;
        color: var(--accent);
    }

    .instance-name {
        max-width: 100px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .chevron {
        flex-shrink: 0;
        opacity: 0.5;
    }

    .instance-dropdown {
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        z-index: 100;
        min-width: 210px;
        overflow: hidden;
        animation: ddIn 0.15s ease;
        padding: 0.25rem;
    }

    .instance-list {
        max-height: calc(4 * 2.25rem);
        overflow-y: auto;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }

    .instance-list::-webkit-scrollbar {
        display: none;
    }

    .instance-row {
        display: flex;
        align-items: center;
    }

    @keyframes ddIn {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .instance-option {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        padding: 0.5rem 0.75rem;
        background: none;
        border: none;
        border-radius: 8px;
        color: var(--text-secondary);
        font-size: 0.8125rem;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.15s;
    }

    .instance-option:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .instance-option.active {
        color: var(--accent-hover);
    }

    .instance-option .check {
        margin-left: auto;
        color: var(--accent);
    }

    .instance-option.create {
        color: var(--accent);
    }

    .instance-option.create:hover {
        background: rgba(99, 102, 241, 0.1);
    }

    .instance-option:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .instance-option svg {
        flex-shrink: 0;
    }

    .instance-row .instance-option {
        flex: 1;
        min-width: 0;
    }

    .delete-btn {
        flex-shrink: 0;
        background: none;
        border: none;
        color: var(--text-muted);
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        transition: all 0.15s;
    }

    .instance-row:hover .delete-btn {
        opacity: 1;
    }

    .delete-btn:hover {
        color: var(--error);
        background: rgba(239, 68, 68, 0.1);
    }

    .delete-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    .deleting-dot {
        font-size: 0.625rem;
        color: var(--text-muted);
    }

    .dropdown-divider {
        height: 1px;
        background: var(--border);
        margin: 0.25rem 0;
    }

    .name-input-row {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem;
    }

    .name-input {
        flex: 1;
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 6px;
        color: var(--text-primary);
        font-size: 0.8125rem;
        font-family: inherit;
        padding: 0.375rem 0.5rem;
        outline: none;
        min-width: 0;
    }

    .name-input:focus {
        border-color: var(--accent);
    }

    .name-input::placeholder {
        color: var(--text-muted);
    }

    .name-submit {
        background: var(--accent);
        border: none;
        border-radius: 6px;
        color: white;
        cursor: pointer;
        padding: 0.375rem 0.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.15s;
        font-size: 0.75rem;
    }

    .name-submit:hover {
        opacity: 0.85;
    }

    .name-submit:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }
</style>
