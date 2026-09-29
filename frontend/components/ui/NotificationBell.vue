<script setup lang="ts">
// Notification bell with unread badge and dropdown feed
const { notifications, unread, loadNotifications, markAllRead, timeAgo } = useData();
const open = ref(false);
const wrap = ref<HTMLElement | null>(null);
let timer: any = null;

const toggle = () => {
  open.value = !open.value;
  if (open.value) loadNotifications();
};

const onDocClick = (e: MouseEvent) => {
  if (wrap.value && !wrap.value.contains(e.target as Node)) open.value = false;
};

onMounted(() => {
  loadNotifications();
  document.addEventListener("click", onDocClick);
  timer = setInterval(loadNotifications, 30000);
});
onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  clearInterval(timer);
});

const kindColor = (k: string) =>
  k === "success" ? "#10b981" : k === "warning" ? "#f59e0b" : "#3b82f6";
</script>

<template>
  <div ref="wrap" class="bell-wrap">
    <button class="bell-btn" title="Notifications" @click.stop="toggle">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>
        <path d="M13.7 21a2 2 0 0 1-3.4 0"/>
      </svg>
      <span v-if="unread > 0" class="badge">{{ unread > 9 ? "9+" : unread }}</span>
    </button>

    <div v-if="open" class="panel">
      <div class="panel-head">
        <span>Notifications</span>
        <button v-if="unread > 0" class="mark-btn" @click="markAllRead">Mark all read</button>
      </div>
      <div v-if="!notifications.length" class="empty">No notifications yet</div>
      <div v-else class="list">
        <div v-for="n in notifications.slice(0, 12)" :key="n.id" class="item" :class="{ unread: !n.read }">
          <span class="ic">{{ n.icon }}</span>
          <div style="flex: 1; min-width: 0">
            <div class="msg">{{ n.message }}</div>
            <div class="meta">
              <span :style="{ color: kindColor(n.kind) }">{{ timeAgo(n.ts) }}</span>
            </div>
          </div>
          <span v-if="!n.read" class="dot" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bell-wrap { position: relative; }
.bell-btn {
  position: relative; width: 36px; height: 36px; border-radius: 10px; border: 1.5px solid #e2e8f0;
  background: #fff; color: #475569; cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.bell-btn:hover { border-color: #93c5fd; color: #2563eb; }
.badge {
  position: absolute; top: -6px; right: -6px; min-width: 17px; height: 17px; padding: 0 4px;
  background: #ef4444; color: #fff; font-size: 9.5px; font-weight: 800; border-radius: 9px;
  display: flex; align-items: center; justify-content: center; border: 2px solid #fff;
}
.panel {
  position: absolute; right: 0; top: 44px; width: 330px; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 14px; box-shadow: 0 18px 48px rgba(15,23,42,.16); z-index: 90; overflow: hidden;
  animation: dropIn .18s ease;
}
@keyframes dropIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.panel-head {
  display: flex; justify-content: space-between; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9; font-size: 13px; font-weight: 800; color: #0f172a;
}
.mark-btn {
  background: none; border: none; color: #2563eb; font-size: 11px; font-weight: 700;
  cursor: pointer; font-family: inherit; padding: 0;
}
.empty { padding: 28px 16px; text-align: center; font-size: 12px; color: #94a3b8; }
.list { max-height: 360px; overflow-y: auto; }
.item {
  display: flex; gap: 10px; align-items: flex-start; padding: 11px 16px;
  border-bottom: 1px solid #f8fafc; background: #fff;
}
.item.unread { background: #eff6ff33; }
.ic { font-size: 15px; line-height: 1.3; }
.msg { font-size: 12.3px; color: #334155; line-height: 1.45; }
.meta { font-size: 10.5px; font-weight: 700; margin-top: 2px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #3b82f6; margin-top: 5px; flex-shrink: 0; }
@media (max-width: 640px) {
  .panel { position: fixed; left: 10px; right: 10px; top: 66px; width: auto; }
}
</style>
