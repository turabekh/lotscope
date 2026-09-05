<script setup lang="ts">
defineProps<{ label: string; detail: string | null; href: string | null }>()
</script>

<template>
  <div class="file" data-test="file-card">
    <span class="file__mark" aria-hidden="true">▤</span>
    <span class="file__body">
      <span class="file__label">{{ label }}</span>
      <span v-if="detail" class="file__detail">{{ detail }}</span>
    </span>
    <a v-if="href" :href="href" class="file__action" data-test="file-download">Download</a>
    <!-- No link means the Analyst wrote it to the server but the download route is not
         wired for that kind yet. Saying so beats a button that does nothing. -->
    <span v-else class="file__detail">on the server</span>
  </div>
</template>

<style scoped>
.file {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  padding: 8px 10px;
  margin: 6px 0;
  font-size: 13px;
}
.file__body {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.file__detail {
  color: var(--ls-muted, #6b7280);
  font-size: 11.5px;
}
.file__action {
  color: var(--ls-link, #1565c0);
  min-height: 32px;
  display: inline-flex;
  align-items: center;
}
</style>
