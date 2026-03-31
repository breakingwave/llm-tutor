<script>
  import { session, sessionId, activeItemId } from '../lib/stores.js';
  import { addCurriculumItem, deleteCurriculumItem } from '../lib/api.js';
  import Modal from './Modal.svelte';

  let { onrefresh } = $props();
  let addItemOpen = $state(false);
  let newTitle = $state('');
  let newOutline = $state('');

  let curriculum = $derived($session?.curricula?.[0] || null);

  function selectItem(itemId) {
    activeItemId.set(itemId);
  }

  async function handleDeleteItem(itemId) {
    if (!curriculum) return;
    await deleteCurriculumItem(curriculum.id, itemId, $sessionId);
    if ($activeItemId === itemId) activeItemId.set(null);
    await onrefresh();
  }

  async function handleAddItem() {
    if (!curriculum || !newTitle.trim()) return;
    await addCurriculumItem(curriculum.id, {
      session_id: $sessionId,
      title: newTitle,
      content_outline: newOutline,
    });
    newTitle = '';
    newOutline = '';
    addItemOpen = false;
    await onrefresh();
  }
</script>

<div class="card bg-base-100 shadow-sm h-full">
  <div class="card-body p-4">
    {#if curriculum}
      <div class="flex justify-between items-center mb-3">
        <div>
          <h3 class="font-semibold text-sm">{curriculum.goal_topic || 'Syllabus'}</h3>
          <p class="text-xs text-base-content/50">{curriculum.items?.length || 0} sections</p>
        </div>
        <button class="btn btn-ghost btn-xs" onclick={() => addItemOpen = true}>+ Add</button>
      </div>

      <ul class="menu menu-sm bg-base-200 rounded-lg p-1">
        {#each (curriculum.items || []).sort((a, b) => a.order - b.order) as item, idx}
          <li>
            <div
              class="flex items-center justify-between w-full cursor-pointer rounded-lg px-2 py-1.5 hover:bg-base-300 {$activeItemId === item.id ? 'bg-primary/10' : ''}"
              role="button"
              tabindex="0"
              onclick={() => selectItem(item.id)}
              onkeydown={(e) => { if (e.key === 'Enter') selectItem(item.id); }}
            >
              <span class="flex items-center gap-2">
                {#if item.completed}
                  <span class="text-success text-sm">&#10003;</span>
                {:else}
                  <span class="text-base-content/40 text-xs font-mono">{idx + 1}</span>
                {/if}
                <span class="truncate text-sm">{item.title}</span>
              </span>
              <button
                class="btn btn-ghost btn-xs text-base-content/30 hover:text-error"
                aria-label="Delete section"
                onclick={(e) => { e.stopPropagation(); handleDeleteItem(item.id); }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </li>
        {/each}
      </ul>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-base-content/40">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        <p class="text-sm">No syllabus yet</p>
        <p class="text-xs">Generate a curriculum to get started</p>
      </div>
    {/if}
  </div>
</div>

<Modal bind:open={addItemOpen} title="Add Section">
  <div class="form-control mb-3">
    <label class="label"><span class="label-text">Title</span></label>
    <input type="text" class="input input-bordered" placeholder="Section title" bind:value={newTitle} />
  </div>
  <div class="form-control mb-4">
    <label class="label"><span class="label-text">Outline</span></label>
    <textarea class="textarea textarea-bordered h-24" placeholder="Section content outline..." bind:value={newOutline}></textarea>
  </div>
  <div class="modal-action">
    <button class="btn btn-ghost" onclick={() => addItemOpen = false}>Cancel</button>
    <button class="btn btn-primary" onclick={handleAddItem}>Add</button>
  </div>
</Modal>
