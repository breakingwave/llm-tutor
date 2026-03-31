<script>
  let { open = $bindable(false), title = '', children } = $props();
  let dialog = $state(null);

  $effect(() => {
    if (dialog) {
      if (open) dialog.showModal();
      else dialog.close();
    }
  });
</script>

<dialog bind:this={dialog} class="modal" onclose={() => open = false}>
  <div class="modal-box">
    {#if title}
      <h3 class="font-bold text-lg mb-4">{title}</h3>
    {/if}
    {@render children()}
  </div>
  <form method="dialog" class="modal-backdrop">
    <button>close</button>
  </form>
</dialog>
