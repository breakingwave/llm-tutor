<script>
  import { session, sessionId } from '../lib/stores.js';
  import { updateBackground, addGoal, removeGoal, startGathering, getGatheringStatus, generateCurriculum, uploadPdf } from '../lib/api.js';
  import Modal from './Modal.svelte';

  let { onrefresh } = $props();

  let editBgOpen = $state(false);
  let addTopicOpen = $state(false);
  let bgText = $state('');
  let newTopic = $state('');
  let newDepth = $state('introductory');
  let gatheringStatus = $state('');
  let curriculumStatus = $state('');

  function openEditBg() {
    bgText = $session?.user_profile?.background || '';
    editBgOpen = true;
  }

  async function saveBg() {
    await updateBackground($sessionId, bgText);
    editBgOpen = false;
    await onrefresh();
  }

  async function handleAddTopic() {
    if (!newTopic.trim()) return;
    await addGoal($sessionId, newTopic, newDepth);
    newTopic = '';
    addTopicOpen = false;
    await onrefresh();
  }

  async function handleRemoveGoal(idx) {
    await removeGoal($sessionId, idx);
    await onrefresh();
  }

  async function handleGathering() {
    const goal = $session?.user_profile?.goals?.[0];
    if (!goal) return;
    gatheringStatus = 'Starting...';
    try {
      const { task_id } = await startGathering({
        session_id: $sessionId,
        goal_topic: goal.topic,
        depth: goal.depth,
      });
      // Poll status
      const poll = setInterval(async () => {
        try {
          const status = await getGatheringStatus(task_id, $sessionId);
          gatheringStatus = `Found ${status.materials_count} materials...`;
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(poll);
            gatheringStatus = status.status === 'completed'
              ? `Done! ${status.materials_count} materials gathered.`
              : 'Gathering failed.';
            await onrefresh();
          }
        } catch { clearInterval(poll); gatheringStatus = 'Error polling status.'; }
      }, 3000);
    } catch (err) {
      gatheringStatus = `Error: ${err.message}`;
    }
  }

  async function handleCurriculum() {
    const goal = $session?.user_profile?.goals?.[0];
    if (!goal) return;
    curriculumStatus = 'Generating...';
    try {
      await generateCurriculum({
        session_id: $sessionId,
        goal_topic: goal.topic,
        depth: goal.depth,
      });
      curriculumStatus = 'Done!';
      await onrefresh();
    } catch (err) {
      curriculumStatus = `Error: ${err.message}`;
    }
  }
</script>

<div class="card bg-base-100 shadow-sm">
  <div class="card-body p-4">
    <!-- Background -->
    <div class="flex justify-between items-center mb-2">
      <h3 class="font-semibold text-sm">Your Background</h3>
      <button class="btn btn-ghost btn-xs" onclick={openEditBg}>Edit</button>
    </div>
    <p class="text-sm text-base-content/70 whitespace-pre-line mb-4">
      {$session?.user_profile?.background || 'No background provided yet.'}
    </p>

    <!-- Learning Topics -->
    <div class="flex justify-between items-center mb-2">
      <h3 class="font-semibold text-sm">Learning Topics</h3>
      <button class="btn btn-ghost btn-xs" onclick={() => addTopicOpen = true}>+ Add</button>
    </div>
    {#if $session?.user_profile?.goals?.length}
      <ul class="space-y-1 mb-4">
        {#each $session.user_profile.goals as goal, idx}
          <li class="flex items-center justify-between text-sm">
            <span>
              <strong>{goal.topic}</strong>
              <span class="badge badge-sm badge-ghost ml-1">{goal.depth}</span>
            </span>
            <button class="btn btn-ghost btn-xs text-error" onclick={() => handleRemoveGoal(idx)}>X</button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm text-base-content/50 italic mb-4">No topics yet.</p>
    {/if}

    <div class="divider my-1"></div>

    <!-- PDF Upload -->
    <div class="mb-3">
      <label class="btn btn-outline btn-sm btn-primary w-full" for="pdf-upload">
        Upload PDF
      </label>
      <input
        id="pdf-upload"
        type="file"
        accept=".pdf"
        class="hidden"
        onchange={async (e) => {
          const file = e.target.files[0];
          if (!file) return;
          const fd = new FormData();
          fd.append('file', file);
          fd.append('session_id', $sessionId);
          try {
              await uploadPdf(fd);
            await onrefresh();
          } catch (err) {
            alert(err.message);
          }
        }}
      />
    </div>

    <!-- Gathering -->
    <button class="btn btn-outline btn-sm btn-primary w-full mb-2" onclick={handleGathering}>
      Search for Materials
    </button>
    {#if gatheringStatus}
      <p class="text-xs text-base-content/60 mb-2">{gatheringStatus}</p>
    {/if}

    <!-- Curriculum -->
    <button class="btn btn-outline btn-sm btn-secondary w-full" onclick={handleCurriculum}>
      Generate Syllabus
    </button>
    {#if curriculumStatus}
      <p class="text-xs text-base-content/60 mt-1">{curriculumStatus}</p>
    {/if}
  </div>
</div>

<!-- Edit Background Modal -->
<Modal bind:open={editBgOpen} title="Edit Background">
  <textarea class="textarea textarea-bordered w-full h-32" bind:value={bgText}></textarea>
  <div class="modal-action">
    <button class="btn btn-ghost" onclick={() => editBgOpen = false}>Cancel</button>
    <button class="btn btn-primary" onclick={saveBg}>Save</button>
  </div>
</Modal>

<!-- Add Topic Modal -->
<Modal bind:open={addTopicOpen} title="Add Learning Topic">
  <div class="form-control mb-3">
    <input type="text" class="input input-bordered" placeholder="Topic" bind:value={newTopic} />
  </div>
  <div class="form-control mb-4">
    <select class="select select-bordered" bind:value={newDepth}>
      <option value="introductory">Introductory</option>
      <option value="comprehensive">Comprehensive</option>
      <option value="expert">Expert</option>
    </select>
  </div>
  <div class="modal-action">
    <button class="btn btn-ghost" onclick={() => addTopicOpen = false}>Cancel</button>
    <button class="btn btn-primary" onclick={handleAddTopic}>Add</button>
  </div>
</Modal>
