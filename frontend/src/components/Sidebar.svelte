<script>
  import { session, sessionId } from '../lib/stores.js';
  import { startGathering, getGatheringStatus, generateCurriculum, uploadPdf } from '../lib/api.js';

  let { onrefresh, onNewTopic } = $props();

  let gatheringStatus = $state('');
  let curriculumStatus = $state('');

  let primaryGoal = $derived($session?.user_profile?.goals?.[0] ?? null);
  let extraGoals = $derived(Math.max(0, ($session?.user_profile?.goals?.length || 0) - 1));

  async function handleGathering() {
    const goal = primaryGoal;
    if (!goal) return;
    gatheringStatus = 'Starting...';
    try {
      const { task_id } = await startGathering({
        session_id: $sessionId,
        goal_topic: goal.topic,
        depth: goal.depth,
      });
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
    const goal = primaryGoal;
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
    <div class="flex justify-between items-center mb-2">
      <h3 class="font-semibold text-sm">Topic</h3>
      {#if onNewTopic}
        <button type="button" class="btn btn-ghost btn-xs" onclick={() => onNewTopic()}>New topic</button>
      {/if}
    </div>
    {#if primaryGoal}
      <p class="text-sm mb-4">
        <strong>{primaryGoal.topic}</strong>
        <span class="badge badge-sm badge-ghost ml-1">{primaryGoal.depth}</span>
        {#if extraGoals > 0}
          <span class="text-xs text-base-content/50 ml-1">(+{extraGoals} more goals, legacy)</span>
        {/if}
      </p>
    {:else}
      <p class="text-sm text-base-content/50 italic mb-4">No topic on this session.</p>
    {/if}

    <div class="divider my-1"></div>

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

    <button class="btn btn-outline btn-sm btn-primary w-full mb-2" onclick={handleGathering}>
      Search for Materials
    </button>
    {#if gatheringStatus}
      <p class="text-xs text-base-content/60 mb-2">{gatheringStatus}</p>
    {/if}

    <button class="btn btn-outline btn-sm btn-secondary w-full" onclick={handleCurriculum}>
      Generate Syllabus
    </button>
    {#if curriculumStatus}
      <p class="text-xs text-base-content/60 mt-1">{curriculumStatus}</p>
    {/if}
  </div>
</div>
