<script>
  import { push } from 'svelte-spa-router';
  import { login } from '../lib/api.js';
  import { authToken, currentUser } from '../lib/stores.js';

  let email = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    loading = true;
    error = '';
    try {
      const res = await login(email, password);
      authToken.set(res.token);
      currentUser.set(res.user);
      push('/');
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
</div>

<div class="flex justify-center items-center min-h-[80vh]">
  <div class="card bg-base-100 shadow-md w-full max-w-md">
    <div class="card-body">
      <h2 class="text-2xl font-semibold mb-4 text-center">Login</h2>

      <form onsubmit={handleSubmit}>
        <div class="form-control mb-4">
          <label class="label" for="email">
            <span class="label-text font-medium">Email</span>
          </label>
          <input
            id="email"
            type="email"
            class="input input-bordered"
            placeholder="you@example.com"
            bind:value={email}
            required
          />
        </div>

        <div class="form-control mb-6">
          <label class="label" for="password">
            <span class="label-text font-medium">Password</span>
          </label>
          <input
            id="password"
            type="password"
            class="input input-bordered"
            placeholder="Enter password"
            bind:value={password}
            required
          />
        </div>

        {#if error}
          <div class="alert alert-error mb-4">
            <span>{error}</span>
          </div>
        {/if}

        <div class="card-actions justify-center">
          <button type="submit" class="btn btn-primary btn-lg w-full" disabled={loading}>
            {#if loading}
              <span class="loading loading-spinner"></span>
            {/if}
            Login
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
