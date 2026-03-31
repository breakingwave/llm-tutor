<script>
  import { push } from 'svelte-spa-router';
  import { createSession, logout, getMe } from '../lib/api.js';
  import { currentUser } from '../lib/stores.js';
  import { onMount } from 'svelte';

  onMount(async () => {
    try {
      const me = await getMe();
      currentUser.set(me);
    } catch {}
  });

  let background = $state('');
  let goalTopic = $state('');
  let goalDepth = $state('introductory');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!goalTopic.trim()) return;
    loading = true;
    error = '';
    try {
      const res = await createSession({
        background,
        goal_topic: goalTopic,
        goal_depth: goalDepth,
      });
      const id = res.redirect?.split('/').pop() || res.session_id;
      push(`/dashboard/${id}`);
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="navbar bg-base-100 shadow-sm">
  <div class="flex-1">
    <span class="text-xl font-semibold px-4">LLM Tutor</span>
  </div>
  <div class="flex-none px-4 flex gap-2 items-center">
    {#if $currentUser}
      <span class="text-sm text-base-content/60">{$currentUser.email}</span>
    {/if}
    <a href="#/openstax" class="btn btn-ghost btn-sm">OpenStax Library</a>
    <button class="btn btn-ghost btn-sm" onclick={logout}>Logout</button>
  </div>
</div>

<div class="flex justify-center items-center min-h-[80vh]">
  <div class="card bg-base-100 shadow-md w-full max-w-2xl">
    <div class="card-body">
      <h2 class="card-title text-2xl">Welcome to LLM Tutor</h2>
      <p class="text-base-content/60 mb-4">Tell us about yourself and what you'd like to learn.</p>

      <form onsubmit={handleSubmit}>
        <div class="form-control mb-4">
          <label class="label" for="background">
            <span class="label-text font-medium">Your Background</span>
          </label>
          <textarea
            id="background"
            class="textarea textarea-bordered h-24"
            placeholder="Briefly describe your educational background, experience, and knowledge..."
            bind:value={background}
          ></textarea>
          <label class="label">
            <span class="label-text-alt text-base-content/50">Free-form - include anything you think is relevant</span>
          </label>
        </div>

        <div class="divider">What would you like to learn?</div>

        <div class="form-control mb-4">
          <label class="label" for="topic">
            <span class="label-text font-medium">Learning Topic</span>
          </label>
          <input
            id="topic"
            type="text"
            class="input input-bordered"
            placeholder="e.g., Cell biology, Organic chemistry, Quantum mechanics..."
            bind:value={goalTopic}
            required
          />
        </div>

        <div class="form-control mb-6">
          <label class="label" for="depth">
            <span class="label-text font-medium">Desired Depth</span>
          </label>
          <select id="depth" class="select select-bordered" bind:value={goalDepth}>
            <option value="introductory">Introductory</option>
            <option value="comprehensive">Comprehensive</option>
            <option value="expert">Expert</option>
          </select>
        </div>

        {#if error}
          <div class="alert alert-error mb-4">
            <span>{error}</span>
          </div>
        {/if}

        <div class="card-actions justify-center">
          <button type="submit" class="btn btn-primary btn-lg" disabled={loading}>
            {#if loading}
              <span class="loading loading-spinner"></span>
            {/if}
            Start Learning
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
