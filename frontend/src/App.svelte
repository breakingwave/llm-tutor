<script>
  import Router, { replace } from 'svelte-spa-router';
  import { wrap } from 'svelte-spa-router/wrap';
  import Login from './components/Login.svelte';
  import Onboarding from './components/Onboarding.svelte';
  import Dashboard from './components/Dashboard.svelte';
  import Library from './components/Library.svelte';
  import OpenStaxBrowser from './components/OpenStaxBrowser.svelte';
  import AdminUsers from './components/AdminUsers.svelte';

  function authGuard() {
    if (!localStorage.getItem('token')) {
      replace('/login');
      return false;
    }
    return true;
  }

  const routes = {
    '/login': Login,
    '/': wrap({ component: Onboarding, conditions: [authGuard] }),
    '/dashboard/:sessionId': wrap({ component: Dashboard, conditions: [authGuard] }),
    '/library/:sessionId': wrap({ component: Library, conditions: [authGuard] }),
    '/openstax': wrap({ component: OpenStaxBrowser, conditions: [authGuard] }),
    '/admin/users': wrap({ component: AdminUsers, conditions: [authGuard] }),
  };
</script>

<div class="min-h-screen bg-base-200">
  <Router {routes} />
</div>
