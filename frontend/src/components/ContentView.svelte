<script>
  import { session, activeItemId } from '../lib/stores.js';

  let curriculum = $derived($session?.curricula?.[0] || null);
  let activeItem = $derived(
    curriculum?.items?.find(i => i.id === $activeItemId) || null
  );
</script>

<div class="card bg-base-100 shadow-sm h-full">
  <div class="card-body p-4 overflow-y-auto">
    {#if activeItem}
      <h2 class="card-title text-lg">{activeItem.title}</h2>
      <div class="prose prose-sm max-w-none mt-2 text-base-content">
        {#each (activeItem.content_outline || '').split('\n') as line}
          <p>{line}</p>
        {/each}
      </div>
    {:else if curriculum}
      <div class="flex flex-col items-center justify-center h-full text-base-content/40">
        <p class="text-sm">Select a section from the syllabus</p>
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-base-content/40">
        <p class="text-sm">No content yet</p>
        <p class="text-xs">Start by gathering materials and generating a curriculum</p>
      </div>
    {/if}
  </div>
</div>
