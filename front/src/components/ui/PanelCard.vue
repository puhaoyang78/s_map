<script setup>
defineProps({
  as: {
    type: String,
    default: 'section',
  },
})
</script>

<template>
  <component :is="as" class="ds-panel-card">
    <div v-if="$slots.header" class="panel-card__header">
      <slot name="header" />
    </div>
    <div class="panel-card__body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="panel-card__footer">
      <slot name="footer" />
    </div>
  </component>
</template>

<style scoped>
.panel-card__header,
.panel-card__footer {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
}

.panel-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}

.panel-card__header + .panel-card__body {
  margin-top: var(--ds-space-5);
}

.panel-card__body + .panel-card__footer {
  margin-top: var(--ds-space-5);
}
</style>
