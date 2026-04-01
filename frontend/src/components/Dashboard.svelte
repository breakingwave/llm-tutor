<script>
  import { getSession } from '../lib/api.js';
  import { session, sessionId, activeItemId, chatMessages } from '../lib/stores.js';
  import Sidebar from './Sidebar.svelte';
  import Syllabus from './Syllabus.svelte';
  import ContentView from './ContentView.svelte';
  import Chat from './Chat.svelte';

  let { params, embedded = false, sessionId: sessionIdProp = null, onNewTopic, hideSidebar = false } = $props();
  let loading = $state(true);
  let error = $state('');
  let resolvedSessionId = $derived(sessionIdProp || params?.sessionId);

  // Refetch when the route or embedded topic selection changes (onMount only ran once).
  $effect(() => {
    const id = resolvedSessionId;
    if (!id) {
      loading = false;
      return;
    }
    let cancelled = false;
    loading = true;
    error = '';
    sessionId.set(id);
    activeItemId.set(null);
    chatMessages.set([]);

    (async () => {
      try {
        const data = await getSession(id);
        if (cancelled) return;
        session.set(data);
      } catch (err) {
        if (cancelled) return;
        error = err.message;
      } finally {
        if (!cancelled) loading = false;
      }
    })();

    return () => {
      cancelled = true;
    };
  });

  async function refreshSession() {
    const id = resolvedSessionId;
    if (!id) return;
    try {
      const data = await getSession(id);
      session.set(data);
    } catch (err) {
      error = err.message;
    }
  }
</script>

{#if !embedded}
  <div class="navbar bg-base-100 shadow-sm">
    <div class="flex-1">
      <a href="#/" class="text-xl font-semibold px-4">LLM Tutor</a>
    </div>
    <div class="flex-none gap-2 px-4">
      <a href="#/library/{resolvedSessionId}" class="btn btn-ghost btn-sm">Content Library</a>
      <a href="#/openstax" class="btn btn-ghost btn-sm">OpenStax</a>
    </div>
  </div>
{/if}

{#if loading}
  <div class="flex justify-center items-center h-[80vh]">
    <span class="loading loading-spinner loading-lg"></span>
  </div>
{:else if error}
  <div class="alert alert-error m-4"><span>{error}</span></div>
{:else if hideSidebar}
  <!-- Topic actions live in Workspace (stacked under topic list); syllabus + main area only -->
  <div class="grid grid-cols-12 gap-3 p-3 h-[calc(100vh-4rem)]">
    <div class="col-span-3 overflow-y-auto min-h-0">
      <Syllabus onrefresh={refreshSession} />
    </div>
    <div class="col-span-9 flex flex-col gap-3 overflow-hidden min-h-0">
      <div class="flex-1 overflow-y-auto min-h-0">
        <ContentView />
      </div>
      <div class="h-[45%] min-h-0">
        <Chat />
      </div>
    </div>
  </div>
{:else}
  <div class="grid grid-cols-12 gap-3 p-3 h-[calc(100vh-4rem)]">
    <div class="col-span-3 overflow-y-auto min-h-0">
      <Sidebar onrefresh={refreshSession} {onNewTopic} />
    </div>
    <div class="col-span-3 overflow-y-auto min-h-0">
      <Syllabus onrefresh={refreshSession} />
    </div>
    <div class="col-span-6 flex flex-col gap-3 overflow-hidden min-h-0">
      <div class="flex-1 overflow-y-auto min-h-0">
        <ContentView />
      </div>
      <div class="h-[45%] min-h-0">
        <Chat />
      </div>
    </div>
  </div>
{/if}
