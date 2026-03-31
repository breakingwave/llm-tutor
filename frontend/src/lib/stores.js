import { writable } from 'svelte/store';

export const authToken = writable(localStorage.getItem('token'));
export const currentUser = writable(null);

// Persist token to localStorage
authToken.subscribe((val) => {
  if (val) {
    localStorage.setItem('token', val);
  } else {
    localStorage.removeItem('token');
  }
});

export const sessionId = writable(null);
export const session = writable(null);
export const activeItemId = writable(null);
export const chatMessages = writable([]);
