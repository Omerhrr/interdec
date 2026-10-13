<script setup lang="ts">
// Login page - exact replica of the original Interdec Platform sign-in
const { login, user } = useAuth();
const route = useRoute();
// only ever return to an in-app path (never an external URL)
const nextPath = () => {
  const n = String(route.query.next || "");
  return n.startsWith("/platform") && !n.startsWith("//") ? n : "/platform";
};
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

onMounted(async () => {
  // already signed in? go to platform
  const u = await useAuth().fetchMe();
  if (u) navigateTo(nextPath());
});

const doLogin = async () => {
  error.value = "";
  if (!email.value.trim() || !password.value) {
    error.value = !email.value.trim() ? "Enter your email address" : "Enter your password";
    return;
  }
  loading.value = true;
  try {
    await login(email.value.trim(), password.value);
    navigateTo(nextPath());
  } catch (e: any) {
    // keep the email so only the password needs retyping
    password.value = "";
    error.value = e?.message || "Email or password is incorrect";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <main class="login-wrap">
    <div class="login-brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
      <h1>Interdec Platform</h1>
      <p class="brand-sub">UNIFIED ACCESS PORTAL</p>
    </div>

    <form class="login-card" novalidate aria-labelledby="signin-h" @submit.prevent="doLogin">
      <h2 id="signin-h">Sign in</h2>
      <p class="sub">Enter your credentials to access the platform</p>

      <label class="lbl" for="login-email">Email</label>
      <input id="login-email" v-model="email" class="inp" type="email" placeholder="you@interdecng.com" autocomplete="email"
        :aria-invalid="!!error || undefined" aria-describedby="login-err" />

      <label class="lbl" for="login-pw" style="margin-top:14px">Password</label>
      <UiPasswordInput id="login-pw" v-model="password" :invalid="!!error" describedby="login-err" />

      <div id="login-err" class="login-err" role="alert" :hidden="!error">{{ error }}</div>

      <button class="btn btn-accent login-btn" type="submit" :disabled="loading">
        {{ loading ? "Signing in…" : "Sign in" }}
      </button>
    </form>

    <p class="login-foot">© {{ new Date().getFullYear() }} Interdec Group · All Rights Reserved</p>
  </main>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 30px; padding: 20px;
  background: #f8fafc;
}
.login-brand { text-align: center; }
.brand-icon {
  width: 52px; height: 52px; margin: 0 auto 16px; border-radius: 14px;
  background: linear-gradient(135deg, #1e293b, #0f172a);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 20px rgba(15, 23, 42, .25);
}
.login-brand h1 { font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -.5px; }
.brand-sub { font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 3px; margin-top: 6px; }
.login-card {
  width: 100%; max-width: 370px; background: #fff; border-radius: 16px;
  padding: 26px 26px 30px; border: 1px solid #f1f5f9;
  box-shadow: 0 10px 40px rgba(15, 23, 42, .06);
}
.login-card h2 { font-size: 18px; font-weight: 800; margin-bottom: 4px; }
.login-card .sub { font-size: 13px; color: #64748b; margin-bottom: 22px; }
.login-err {
  margin-top: 14px; padding: 9px 12px; border-radius: 8px; background: #fef2f2;
  border: 1px solid #fecaca; color: #dc2626; font-size: 12.5px; font-weight: 600;
}
.login-btn { width: 100%; margin-top: 18px; padding: 12px; font-size: 14px; border-radius: 9px; }
.login-foot { font-size: 12px; color: #64748b; }
</style>
