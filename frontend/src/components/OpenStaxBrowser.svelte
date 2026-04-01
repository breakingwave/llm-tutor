<script>
  import { onMount } from 'svelte';
  import { listOpenStaxBooks, uploadOpenStaxBook, deleteOpenStaxBook, reindexOpenStaxBook, getMe, logout } from '../lib/api.js';
  import { currentUser } from '../lib/stores.js';

  let { embedded = false } = $props();
  let books = $state([]);
  let loading = $state(true);
  let uploading = $state(false);
  let reindexing = $state({});

  onMount(async () => {
    try {
      const me = await getMe();
      currentUser.set(me);
    } catch {}
    await refresh();
  });

  async function refresh() {
    loading = true;
    try {
      const res = await listOpenStaxBooks();
      books = res.books || [];
    } catch {
      books = [];
    } finally {
      loading = false;
    }
  }

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    uploading = true;
    try {
      const fd = new FormData();
      fd.append('file', file);
      await uploadOpenStaxBook(fd);
      await refresh();
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      uploading = false;
      e.target.value = '';
    }
  }

  async function handleDelete(bookId) {
    await deleteOpenStaxBook(bookId);
    await refresh();
  }

  async function handleReindex(bookId) {
    reindexing[bookId] = true;
    try {
      await reindexOpenStaxBook(bookId);
      await refresh();
    } catch (err) {
      alert(`Re-index failed: ${err.message}`);
    } finally {
      reindexing[bookId] = false;
    }
  }

</script>

{#if !embedded}
  <div class="navbar bg-base-100 shadow-sm">
    <div class="flex-1">
      <a href="#/" class="text-xl font-semibold px-4">LLM Tutor</a>
    </div>
    <div class="flex-none px-4 flex gap-2 items-center">
      <a href="#/" class="btn btn-ghost btn-sm">Home</a>
      <button class="btn btn-ghost btn-sm" onclick={logout}>Logout</button>
    </div>
  </div>
{/if}

<div class="container mx-auto p-4">
  <div class="flex justify-between items-center mb-6">
    <div>
      <h1 class="text-2xl font-bold">OpenStax Library</h1>
      <p class="text-sm text-base-content/60">Shared textbooks available to all users</p>
    </div>
    {#if $currentUser?.role === 'admin'}
      <label class="btn btn-primary btn-sm {uploading ? 'loading' : ''}" for="openstax-upload">
        {uploading ? 'Uploading...' : 'Upload Book'}
      </label>
      <input
        id="openstax-upload"
        type="file"
        accept=".pdf"
        class="hidden"
        onchange={handleUpload}
        disabled={uploading}
      />
    {/if}
  </div>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  {:else if books.length}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each books as book}
        <div class="card bg-base-100 shadow-sm">
          <div class="card-body p-4">
            <div class="flex justify-between items-start">
              <div class="flex-1 min-w-0">
                <h3 class="font-semibold truncate">{book.title}</h3>
                <p class="text-xs text-base-content/50 mt-1">{book.file_name}</p>
              </div>
              {#if $currentUser?.role === 'admin'}
                <div class="flex gap-1 ml-2">
                  <button
                    class="btn btn-ghost btn-xs text-base-content/30 hover:text-info"
                    onclick={() => handleReindex(book.id)}
                    disabled={reindexing[book.id]}
                    title="Re-index"
                  >
                    {#if reindexing[book.id]}
                      <span class="loading loading-spinner loading-xs"></span>
                    {:else}
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    {/if}
                  </button>
                  <button
                    class="btn btn-ghost btn-xs text-base-content/30 hover:text-error"
                    onclick={() => handleDelete(book.id)}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              {/if}
            </div>
            <div class="flex gap-2 mt-2">
              <span class="badge badge-sm badge-success">OpenStax</span>
              <span class="badge badge-sm badge-ghost">{book.chunk_count} chunks</span>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="text-center py-12 text-base-content/40">
      <p>No OpenStax books uploaded yet.</p>
      <p class="text-sm mt-1">Upload a book to make it available for all users.</p>
    </div>
  {/if}
</div>
