export async function streamChat(sessionId, message, itemId, onToken, onDone, onError) {
  try {
    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch('/api/chat/send', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_id: sessionId,
        message,
        curriculum_item_id: itemId || null,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      onError(err.detail || 'Request failed');
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          const event = line.slice(7).trim();
          if (event === 'done') {
            onDone();
            return;
          }
          if (event === 'error') {
            onError('Stream error');
            return;
          }
        }
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            if (data.error) onError(data.error);
          } catch { /* skip malformed */ }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err.message);
  }
}
