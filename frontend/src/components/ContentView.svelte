<script>
  import { session, activeItemId } from '../lib/stores.js';

  let curriculum = $derived($session?.curricula?.[0] || null);
  let activeItem = $derived(
    curriculum?.items?.find(i => i.id === $activeItemId) || null
  );
  let associatedMaterials = $derived.by(() => {
    if (!activeItem?.material_ids?.length) return [];
    const materialMap = new Map(($session?.materials || []).map((material) => [material.id, material]));
    return activeItem.material_ids
      .map((materialId) => materialMap.get(materialId))
      .filter(Boolean);
  });
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
      <div class="divider my-4">Associated materials</div>
      {#if associatedMaterials.length}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {#each associatedMaterials as material}
            <div class="card bg-base-200/60 border border-base-300">
              <div class="card-body p-3">
                <div class="flex items-start justify-between gap-2">
                  <h3 class="font-semibold text-sm">{material.title}</h3>
                  <span class="badge badge-sm">{material.source}</span>
                </div>
                {#if material.summary}
                  <p class="text-xs text-base-content/70 line-clamp-3 mt-1">{material.summary}</p>
                {/if}
                {#if material.url}
                  <a href={material.url} target="_blank" rel="noopener" class="link link-primary text-xs mt-2">Source</a>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-base-content/60">No materials are linked to this section yet.</p>
      {/if}
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
