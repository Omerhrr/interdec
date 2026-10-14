<script setup lang="ts">
// ImportFlow → Import data: bring existing records in from Excel/CSV.
const { importflowRole } = useAuth();
const canEdit = computed(() => ["admin", "user"].includes(importflowRole.value));
const { loadAll } = useData();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const KINDS = [
  { k: "vendors", label: "Vendors", desc: "Suppliers with contacts and category", icon: "factory" },
  { k: "shippers", label: "Shippers", desc: "Freight forwarders and carriers", icon: "ship" },
  { k: "agents", label: "Clearing agents", desc: "Customs brokers", icon: "shield" },
  { k: "projects", label: "Projects", desc: "Jobs with client and status", icon: "clipboard" },
  { k: "shipments", label: "Shipments", desc: "Orders in progress or done, with ETA and amount paid", icon: "cycle" },
];
const onImported = async (k: string, r: any) => {
  await loadAll();
  notify(`${r.created} added, ${r.updated} updated`);
};
</script>

<template>
  <div class="page">
    <div class="head">
      <div>
        <h1 class="ph">Import data</h1>
        <p class="sub">Bring your existing spreadsheets in. Import in this order so names match: vendors, shippers and clearing agents first, then projects, then shipments.</p>
      </div>
    </div>
    <div v-if="!canEdit" class="alert" role="alert">You have read-only access to ImportFlow, so you can't import.</div>
    <ImportWizard v-else :kinds="KINDS" @imported="onImported" />
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; }
.head { margin-bottom: 16px; }
.ph { font-size: 20px; font-weight: 800; }
.sub { font-size: 12.5px; color: #64748b; margin-top: 4px; max-width: 720px; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 12px 14px; font-size: 12.5px; font-weight: 600; }
@media (max-width: 640px) { .page { padding: 16px; } }
</style>
