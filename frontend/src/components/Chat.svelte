<script>
  import { sessionId, activeItemId, chatMessages } from '../lib/stores.js';
  import { streamChat } from '../lib/sse.js';

  let input = $state('');
  let sending = $state(false);
  let messagesEl = $state(null);

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function scrollToBottom() {
    if (messagesEl) {
      requestAnimationFrame(() => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      });
    }
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || sending) return;

    input = '';
    sending = true;

    chatMessages.update(msgs => [...msgs, { role: 'user', content: text }]);
    scrollToBottom();

    // Add empty assistant message for streaming
    chatMessages.update(msgs => [...msgs, { role: 'assistant', content: '', streaming: true }]);
    scrollToBottom();

    await streamChat(
      $sessionId,
      text,
      $activeItemId,
      (token) => {
        chatMessages.update(msgs => {
          const last = msgs[msgs.length - 1];
          if (last?.role === 'assistant') {
            last.content += token;
          }
          return [...msgs];
        });
        scrollToBottom();
      },
      () => {
        chatMessages.update(msgs => {
          const last = msgs[msgs.length - 1];
          if (last) last.streaming = false;
          return [...msgs];
        });
        sending = false;
      },
      (err) => {
        chatMessages.update(msgs => {
          const last = msgs[msgs.length - 1];
          if (last?.role === 'assistant') {
            last.content = `Error: ${err}`;
            last.error = true;
            last.streaming = false;
          }
          return [...msgs];
        });
        sending = false;
      }
    );
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="card bg-base-100 shadow-sm h-full flex flex-col">
  <div class="card-body p-3 flex flex-col min-h-0">
    <h3 class="font-semibold text-sm mb-2">Chat</h3>

    <!-- Messages -->
    <div bind:this={messagesEl} class="flex-1 overflow-y-auto space-y-3 mb-3">
      {#each $chatMessages as msg}
        <div class="chat {msg.role === 'user' ? 'chat-end' : 'chat-start'}">
          <div class="chat-bubble text-sm {
            msg.role === 'user'
              ? 'bg-blue-700 text-white'
              : msg.error
                ? 'bg-error/10 text-error'
                : 'bg-base-200 text-base-content'
          } {msg.streaming ? 'after:content-[\"|\"] after:animate-pulse' : ''}">
            {msg.content || '...'}
          </div>
        </div>
      {/each}
    </div>

    <!-- Input -->
    <div class="flex gap-2">
      <input
        type="text"
        class="input input-bordered input-sm flex-1"
        placeholder="Ask a question..."
        bind:value={input}
        onkeydown={handleKeydown}
        disabled={sending}
      />
      <button class="btn btn-primary btn-sm" onclick={sendMessage} disabled={sending || !input.trim()}>
        {#if sending}
          <span class="loading loading-spinner loading-xs"></span>
        {:else}
          Send
        {/if}
      </button>
    </div>
  </div>
</div>
