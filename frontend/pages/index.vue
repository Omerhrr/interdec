<script setup lang="ts">
// Login page — exact replica of the original Interdec Platform sign-in
const { login, user } = useAuth();
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

onMounted(async () => {
  // already signed in? go to platform
  const u = await useAuth().fetchMe();
  if (u) navigateTo("/platform");
});

const doLogin = async () => {
  error.value = "";
  if (!email.value.trim() || !password.value) {
    error.value = "Please enter both email and password";
    return;
  }
  loading.value = true;
  try {
    await login(email.value.trim(), password.value);
    navigateTo("/platform");
  } catch (e: any) {
    error.value = e?.message || "Invalid email or password";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="login-wrap">
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

    <form class="login-card" @submit.prevent="doLogin">
      <h2>Sign In</h2>
      <p class="sub">Enter your credentials to access the platform</p>

      <label class="lbl">Email</label>
      <input v-model="email" class="inp" type="email" placeholder="you@interdecng.com" autocomplete="email" />

      <label class="lbl" style="margin-top:14px">Password</label>
      <input v-model="password" class="inp" type="password" placeholder="••••••••" autocomplete="current-password" />

      <div v-if="error" class="login-err">{{ error }}</div>

      <button class="btn btn-accent login-btn" type="submit" :disabled="loading">
        {{ loading ? "Signing In…" : "Sign In" }}
      </button>
    </form>

    <p class="login-foot">© 2026 Interdec Group · All Rights Reserved</p>
  </div>
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
.brand-sub { font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 3px; margin-top: 6px; }
.login-card {
  width: 100%; max-width: 370px; background: #fff; border-radius: 16px;
  padding: 26px 26px 30px; border: 1px solid #f1f5f9;
  box-shadow: 0 10px 40px rgba(15, 23, 42, .06);
}
.login-card h2 { font-size: 18px; font-weight: 800; margin-bottom: 4px; }
.login-card .sub { font-size: 13px; color: #94a3b8; margin-bottom: 22px; }
.login-err {
  margin-top: 14px; padding: 9px 12px; border-radius: 8px; background: #fef2f2;
  border: 1px solid #fecaca; color: #dc2626; font-size: 12.5px; font-weight: 600;
}
.login-btn { width: 100%; margin-top: 18px; padding: 12px; font-size: 14px; border-radius: 9px; }
.login-foot { font-size: 12px; color: #94a3b8; }
</style>
