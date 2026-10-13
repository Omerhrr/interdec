// Tracks whether a form differs from the moment it was opened, so closing it can
// ask before throwing typed work away.
export const useDirty = (source: () => unknown) => {
  const base = ref("");
  const snap = () => { base.value = JSON.stringify(source() ?? null); };
  const dirty = computed(() => base.value !== "" && JSON.stringify(source() ?? null) !== base.value);
  return { snap, dirty };
};
