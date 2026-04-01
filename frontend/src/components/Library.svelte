<script>
  import { onMount } from 'svelte';
  import { getSession, deleteMaterial, addManualMaterial } from '../lib/api.js';
  import Modal from './Modal.svelte';

  let { params, embedded = false, sessionId: sessionIdProp = null, excludeSources = [] } = $props();
  let sessionData = $state(null);
  let loading = $state(true);
  let addOpen = $state(false);
  let newTitle = $state('');
  let newContent = $state('');
  let newUrl = $state('');
  let resolvedSessionId = $derived(sessionIdProp || params?.sessionId);
  let filteredMaterials = $derived(
    (sessionData?.materials || []).filter((m) => !excludeSources?.includes(m.source))
  );

  onMount(async () => {
    await refresh();
  });

  async function refresh() {
    loading = true;
    try {
      sessionData = await getSession(resolvedSessionId);
    } finally {
      loading = false;
    }
  }

  async function handleDelete(materialId) {
    await deleteMaterial(resolvedSessionId, materialId);
    await refresh();
  }

  async function handleAdd() {
    if (!newTitle.trim() || !newContent.trim()) return;
    await addManualMaterial({
      session_id: resolvedSessionId,
      title: newTitle,
      content: newContent,
      url: newUrl || null,
    });
    newTitle = '';
    newContent = '';
    newUrl = '';
    addOpen = false;
    await refresh();
  }

  function sourceBadge(source) {
    const map = {
      tavily: 'badge-info',
      openstax: 'badge-success',
      pdf_upload: 'badge-neutral',
      user_upload: 'badge-warning',
    };
    return map[source] || 'badge-ghost';
  }
</script>

{#if !embedded}
  <div class="navbar bg-base-100 shadow-sm">
    <div class="flex-1">
      <a href="#/" class="text-xl font-semibold px-4">LLM Tutor</a>
    </div>
    <div class="flex-none px-4">
      <a href="#/dashboard/{resolvedSessionId}" class="btn btn-ghost btn-sm">Back to Dashboard</a>
    </div>
  </div>
{/if}

<div class="container mx-auto p-4">
  <div class="flex justify-between items-center mb-4">
    <h1 class="text-2xl font-bold">Content Library</h1>
    <button class="btn btn-primary btn-sm" onclick={() => addOpen = true}>+ Add Material</button>
  </div>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  {:else if filteredMaterials.length}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each filteredMaterials as material}
        <div class="card bg-base-100 shadow-sm">
          <div class="card-body p-4">
            <div class="flex justify-between items-start">
              <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-sm truncate">{material.title}</h3>
                <span class="badge badge-sm {sourceBadge(material.source)} mt-1">{material.source}</span>
              </div>
              <button
                class="btn btn-ghost btn-xs text-base-content/30 hover:text-error ml-2"
                onclick={() => handleDelete(material.id)}
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
            {#if material.summary}
              <p class="text-xs text-base-content/60 mt-2 line-clamp-3">{material.summary}</p>
            {/if}
            {#if material.relevance_score}
              <div class="flex gap-0.5 mt-2">
                {#each Array(5) as _, i}
                  <span class="text-xs {i < material.relevance_score ? 'text-warning' : 'text-base-content/20'}">&#9733;</span>
                {/each}
              </div>
            {/if}
            {#if material.url}
              <a href={material.url} target="_blank" rel="noopener" class="link link-primary text-xs mt-1">Source</a>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="text-center py-12 text-base-content/40">
      <p>No materials gathered yet.</p>
    </div>
  {/if}
</div>

<Modal bind:open={addOpen} title="Add Material">
  <div class="form-control mb-3">
    <label class="label"><span class="label-text">Title</span></label>
    <input type="text" class="input input-bordered" placeholder="Material title" bind:value={newTitle} />
  </div>
  <div class="form-control mb-3">
    <label class="label"><span class="label-text">Content</span></label>
    <textarea class="textarea textarea-bordered h-32" placeholder="Material content..." bind:value={newContent}></textarea>
  </div>
  <div class="form-control mb-4">
    <label class="label"><span class="label-text">URL (optional)</span></label>
    <input type="url" class="input input-bordered" placeholder="https://..." bind:value={newUrl} />
  </div>
  <div class="modal-action">
    <button class="btn btn-ghost" onclick={() => addOpen = false}>Cancel</button>
    <button class="btn btn-primary" onclick={handleAdd}>Add</button>
  </div>
</Modal>
