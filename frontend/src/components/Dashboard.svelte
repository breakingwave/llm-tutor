<script>
  import { onMount } from 'svelte';
  import { getSession } from '../lib/api.js';
  import { session, sessionId, activeItemId } from '../lib/stores.js';
  import Sidebar from './Sidebar.svelte';
  import Syllabus from './Syllabus.svelte';
  import ContentView from './ContentView.svelte';
  import Chat from './Chat.svelte';

  let { params } = $props();
  let loading = $state(true);
  let error = $state('');

  onMount(async () => {
    try {
      sessionId.set(params.sessionId);
      const data = await getSession(params.sessionId);
      session.set(data);
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  });

  async function refreshSession() {
    try {
      const data = await getSession(params.sessionId);
      session.set(data);
    } catch (err) {
      error = err.message;
    }
  }
</script>

<div class="navbar bg-base-100 shadow-sm">
  <div class="flex-1">
    <a href="#/" class="text-xl font-semibold px-4">LLM Tutor</a>
  </div>
  <div class="flex-none gap-2 px-4">
    <a href="#/library/{params.sessionId}" class="btn btn-ghost btn-sm">Content Library</a>
    <a href="#/openstax" class="btn btn-ghost btn-sm">OpenStax</a>
  </div>
</div>

{#if loading}
  <div class="flex justify-center items-center h-[80vh]">
    <span class="loading loading-spinner loading-lg"></span>
  </div>
{:else if error}
  <div class="alert alert-error m-4"><span>{error}</span></div>
{:else}
  <div class="grid grid-cols-12 gap-3 p-3 h-[calc(100vh-4rem)]">
    <!-- Left: Sidebar -->
    <div class="col-span-3 overflow-y-auto">
      <Sidebar onrefresh={refreshSession} />
    </div>

    <!-- Middle: Syllabus -->
    <div class="col-span-3 overflow-y-auto">
      <Syllabus onrefresh={refreshSession} />
    </div>

    <!-- Right: Content + Chat -->
    <div class="col-span-6 flex flex-col gap-3 overflow-hidden">
      <div class="flex-1 overflow-y-auto">
        <ContentView />
      </div>
      <div class="h-[45%] min-h-0">
        <Chat />
      </div>
    </div>
  </div>
{/if}
