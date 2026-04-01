<script>
  import { onMount } from 'svelte';
  import { createSession, getMe, getSession, listLearningTopics, logout, updateMyBackground } from '../lib/api.js';
  import { currentUser, session } from '../lib/stores.js';

  import Dashboard from './Dashboard.svelte';
  import Sidebar from './Sidebar.svelte';
  import Library from './Library.svelte';
  import OpenStaxBrowser from './OpenStaxBrowser.svelte';
  import AdminUsers from './AdminUsers.svelte';

  const TAB = {
    BACKGROUND: 'background',
    LEARNING: 'learning',
    MATERIALS: 'materials',
    OPENSTAX: 'openstax',
    USERS: 'users',
  };

  let activeTab = $state(TAB.LEARNING);
  let loading = $state(true);
  let error = $state('');

  let topics = $state([]);
  let selectedSessionId = $state(localStorage.getItem('active_session_id') || '');
  let showCreateTopic = $state(false);

  let selectedTopic = $derived(topics.find((t) => t.session_id === selectedSessionId));

  // Background tab state
  let bgText = $state('');
  let savingBg = $state(false);

  let goalTopic = $state('');
  let goalDepth = $state('introductory');
  let creating = $state(false);

  function setSession(id) {
    selectedSessionId = id;
    if (id) localStorage.setItem('active_session_id', id);
  }

  function openNewTopicFlow() {
    showCreateTopic = true;
    requestAnimationFrame(() => {
      document.getElementById('workspace-new-topic')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  async function refreshMe() {
    const me = await getMe();
    currentUser.set(me);
    bgText = me.background || '';
  }

  async function refreshTopics() {
    const res = await listLearningTopics();
    topics = res.topics || [];
    const ids = topics.map((t) => t.session_id);
    if (selectedSessionId && ids.length && !ids.includes(selectedSessionId)) {
      setSession(ids[0] || '');
    } else if (!selectedSessionId && ids.length) {
      setSession(ids[0]);
    }
  }

  async function refreshSidebarSession() {
    if (!selectedSessionId) return;
    try {
      const data = await getSession(selectedSessionId);
      session.set(data);
    } catch (err) {
      error = err.message;
    }
  }

  async function handleSaveBackground() {
    savingBg = true;
    error = '';
    try {
      await updateMyBackground(bgText);
      await refreshMe();
    } catch (err) {
      error = err.message;
    } finally {
      savingBg = false;
    }
  }

  async function handleCreateSession(e) {
    e?.preventDefault?.();
    if (!goalTopic.trim()) return;
    creating = true;
    error = '';
    try {
      const res = await createSession({
        background: '',
        goal_topic: goalTopic,
        goal_depth: goalDepth,
      });
      const id = res.session_id;
      goalTopic = '';
      goalDepth = 'introductory';
      await refreshMe();
      await refreshTopics();
      setSession(id);
      showCreateTopic = false;
    } catch (err) {
      error = err.message;
    } finally {
      creating = false;
    }
  }

  onMount(async () => {
    loading = true;
    try {
      await refreshMe();
      await refreshTopics();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  });
</script>

<div class="navbar bg-base-100 shadow-sm">
  <div class="flex-1">
    <span class="text-xl font-semibold px-4">LLM Tutor</span>
  </div>

  <div class="flex-none px-4 flex gap-2 items-center">
    {#if $currentUser}
      <span class="text-sm text-base-content/60">{$currentUser.email}</span>
    {/if}
    <button class="btn btn-ghost btn-sm" onclick={logout}>Logout</button>
  </div>
</div>

<div class="p-4">
  <div class="tabs tabs-boxed">
    <button class="tab {activeTab === TAB.BACKGROUND ? 'tab-active' : ''}" onclick={() => activeTab = TAB.BACKGROUND}>
      Background
    </button>
    <button class="tab {activeTab === TAB.LEARNING ? 'tab-active' : ''}" onclick={() => activeTab = TAB.LEARNING}>
      Learning
    </button>
    <button class="tab {activeTab === TAB.MATERIALS ? 'tab-active' : ''}" onclick={() => activeTab = TAB.MATERIALS}>
      Materials
    </button>
    <button class="tab {activeTab === TAB.OPENSTAX ? 'tab-active' : ''}" onclick={() => activeTab = TAB.OPENSTAX}>
      OpenStax
    </button>
    {#if $currentUser?.role === 'admin'}
      <button class="tab {activeTab === TAB.USERS ? 'tab-active' : ''}" onclick={() => activeTab = TAB.USERS}>
        User Management
      </button>
    {/if}
  </div>

  {#if error}
    <div class="alert alert-error mt-4"><span>{error}</span></div>
  {/if}

  {#if loading}
    <div class="flex justify-center items-center h-[70vh]">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  {:else}
    {#if activeTab === TAB.BACKGROUND}
      <div class="card bg-base-100 shadow-sm mt-4 max-w-4xl">
        <div class="card-body">
          <h2 class="card-title">Your Background</h2>
          <p class="text-sm text-base-content/60">
            This is saved per account and used to seed new learning sessions.
          </p>
          <textarea
            class="textarea textarea-bordered min-h-40 mt-2"
            placeholder="Describe your background, experience, and prior knowledge..."
            bind:value={bgText}
          ></textarea>
          <div class="card-actions justify-end mt-3">
            <button class="btn btn-primary" onclick={handleSaveBackground} disabled={savingBg}>
              {#if savingBg}<span class="loading loading-spinner"></span>{/if}
              Save
            </button>
          </div>
        </div>
      </div>
    {:else if activeTab === TAB.LEARNING}
      {#if topics.length === 0}
        <div class="card bg-base-100 shadow-sm mt-4 max-w-2xl mx-auto">
          <div class="card-body">
            <h2 class="card-title">Start your first topic</h2>
            <p class="text-sm text-base-content/60 mb-2">Each topic has its own materials, syllabus, and chat.</p>
            <form onsubmit={handleCreateSession}>
              <div class="form-control mb-4">
                <label class="label" for="topic-first"><span class="label-text">Learning Topic</span></label>
                <input id="topic-first" class="input input-bordered" bind:value={goalTopic} required />
              </div>
              <div class="form-control mb-5">
                <label class="label" for="depth-first"><span class="label-text">Desired Depth</span></label>
                <select id="depth-first" class="select select-bordered" bind:value={goalDepth}>
                  <option value="introductory">Introductory</option>
                  <option value="comprehensive">Comprehensive</option>
                  <option value="expert">Expert</option>
                </select>
              </div>
              <button class="btn btn-primary w-full" type="submit" disabled={creating}>
                {#if creating}<span class="loading loading-spinner"></span>{/if}
                Create topic
              </button>
            </form>
          </div>
        </div>
      {:else}
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-3 mt-4 min-h-[calc(100vh-12rem)]">
          <aside
            class="lg:col-span-3 flex flex-col gap-3 min-h-0 overflow-y-auto lg:max-h-[calc(100vh-8rem)]"
          >
            <div class="flex flex-col gap-2 shrink-0">
              <h3 class="text-sm font-semibold text-base-content/70 px-1">Your topics</h3>
              <div class="flex flex-col gap-1 max-h-48 overflow-y-auto">
                {#each topics as t}
                  <button
                    type="button"
                    class="btn btn-sm w-full justify-start gap-2 h-auto min-h-10 py-2 {selectedSessionId === t.session_id ? 'btn-primary' : 'btn-ghost'}"
                    onclick={() => setSession(t.session_id)}
                  >
                    <span class="truncate text-left flex-1">{t.topic}</span>
                    {#if t.extra_goals_count > 0}
                      <span class="text-[10px] opacity-60 shrink-0" title="Legacy: multiple goals in one session">+{t.extra_goals_count}</span>
                    {/if}
                    <span class="badge badge-sm shrink-0">{t.depth}</span>
                  </button>
                {/each}
              </div>
            </div>
            <div id="workspace-new-topic" class="card bg-base-200/50 border border-base-300 shrink-0">
              <div class="card-body p-3 gap-2">
                {#if !showCreateTopic}
                  <button type="button" class="btn btn-outline btn-sm w-full" onclick={() => (showCreateTopic = true)}>
                    + New topic
                  </button>
                {:else}
                  <span class="text-xs font-medium text-base-content/70">New topic</span>
                  <form onsubmit={handleCreateSession} class="flex flex-col gap-2">
                    <input class="input input-bordered input-sm" placeholder="Topic" bind:value={goalTopic} required />
                    <select class="select select-bordered select-sm" bind:value={goalDepth}>
                      <option value="introductory">Introductory</option>
                      <option value="comprehensive">Comprehensive</option>
                      <option value="expert">Expert</option>
                    </select>
                    <div class="flex gap-2">
                      <button type="button" class="btn btn-ghost btn-sm flex-1" onclick={() => (showCreateTopic = false)}>
                        Cancel
                      </button>
                      <button type="submit" class="btn btn-primary btn-sm flex-1" disabled={creating}>
                        {#if creating}<span class="loading loading-spinner loading-xs"></span>{/if}
                        Create
                      </button>
                    </div>
                  </form>
                {/if}
              </div>
            </div>
            {#if selectedSessionId}
              <div class="flex flex-col flex-1 min-h-0 overflow-y-auto border-t border-base-300 pt-3 mt-1">
                <Sidebar onrefresh={refreshSidebarSession} onNewTopic={openNewTopicFlow} />
              </div>
            {/if}
          </aside>
          <div class="lg:col-span-9 min-h-0 flex flex-col min-w-0">
            {#if selectedSessionId}
              <Dashboard embedded={true} hideSidebar={true} sessionId={selectedSessionId} />
            {/if}
          </div>
        </div>
      {/if}
    {:else if activeTab === TAB.MATERIALS}
      {#if !selectedSessionId}
        <div class="text-base-content/60 mt-6">Create or select a topic first (Learning tab).</div>
      {:else}
        {#if selectedTopic}
          <p class="text-sm text-base-content/60 mt-4 mb-1">
            Materials for <strong>{selectedTopic.topic}</strong>
          </p>
        {/if}
        <Library embedded={true} sessionId={selectedSessionId} excludeSources={['openstax']} />
      {/if}
    {:else if activeTab === TAB.OPENSTAX}
      <OpenStaxBrowser embedded={true} />
    {:else if activeTab === TAB.USERS}
      <AdminUsers embedded={true} />
    {/if}
  {/if}
</div>
