<script>
  import { onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { createUser, deleteUser, getMe, listUsers } from '../lib/api.js';
  import { currentUser } from '../lib/stores.js';

  let { embedded = false } = $props();
  let users = $state([]);
  let loading = $state(true);
  let submitting = $state(false);
  let error = $state('');

  let email = $state('');
  let password = $state('');
  let role = $state('user');

  async function loadUsers() {
    loading = true;
    error = '';
    try {
      const me = await getMe();
      currentUser.set(me);
      if (me.role !== 'admin') {
        push('/');
        return;
      }
      const res = await listUsers();
      users = res.users || [];
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    submitting = true;
    error = '';
    try {
      await createUser({ email, password, role });
      email = '';
      password = '';
      role = 'user';
      await loadUsers();
    } catch (err) {
      error = err.message;
    } finally {
      submitting = false;
    }
  }

  async function handleDelete(user) {
    const message = `Delete ${user.email}? This also deletes all of their sessions and materials.`;
    if (!confirm(message)) return;
    error = '';
    try {
      await deleteUser(user.id);
      await loadUsers();
    } catch (err) {
      error = err.message;
    }
  }

  onMount(loadUsers);
</script>

{#if !embedded}
  <div class="navbar bg-base-100 shadow-sm">
    <div class="flex-1">
      <span class="text-xl font-semibold px-4">Admin Users</span>
    </div>
    <div class="flex-none px-4">
      <button class="btn btn-ghost btn-sm" onclick={() => push('/')}>Back</button>
    </div>
  </div>
{/if}

<div class="p-6 grid gap-6 md:grid-cols-2">
  <div class="card bg-base-100 shadow-md">
    <div class="card-body">
      <h2 class="card-title">Create User</h2>
      <form onsubmit={handleCreate}>
        <div class="form-control mb-3">
          <label class="label" for="email"><span class="label-text">Email</span></label>
          <input id="email" type="email" class="input input-bordered" bind:value={email} required />
        </div>
        <div class="form-control mb-3">
          <label class="label" for="password"><span class="label-text">Password</span></label>
          <input id="password" type="password" class="input input-bordered" bind:value={password} minlength="8" required />
        </div>
        <div class="form-control mb-5">
          <label class="label" for="role"><span class="label-text">Role</span></label>
          <select id="role" class="select select-bordered" bind:value={role}>
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <button type="submit" class="btn btn-primary w-full" disabled={submitting}>
          {#if submitting}<span class="loading loading-spinner"></span>{/if}
          Create User
        </button>
      </form>
    </div>
  </div>

  <div class="card bg-base-100 shadow-md">
    <div class="card-body">
      <h2 class="card-title">Users</h2>
      {#if loading}
        <div class="py-6 text-center"><span class="loading loading-spinner loading-lg"></span></div>
      {:else if users.length === 0}
        <p class="text-base-content/60">No users found.</p>
      {:else}
        <div class="overflow-x-auto">
          <table class="table table-zebra">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Sessions</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each users as user}
                <tr>
                  <td>{user.email}</td>
                  <td><span class="badge badge-outline">{user.role}</span></td>
                  <td>{user.session_ids?.length || 0}</td>
                  <td class="text-right">
                    <button class="btn btn-xs btn-error btn-outline" onclick={() => handleDelete(user)}>
                      Delete
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </div>
</div>

{#if error}
  <div class="toast toast-end">
    <div class="alert alert-error">
      <span>{error}</span>
    </div>
  </div>
{/if}
