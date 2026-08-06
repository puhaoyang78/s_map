<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: {
    type: String,
    default: 'info',
    validator(value) {
      return ['loading', 'empty', 'error', 'info'].includes(value)
    },
  },
  title: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
})

const typeClass = computed(() => `ds-state-${props.type}`)
</script>

<template>
  <div class="ds-state-block" :class="typeClass">
    <div class="ds-state-block__body">
      <h3 v-if="title" class="ds-state-block__title">{{ title }}</h3>
      <p v-if="description" class="ds-state-block__description">{{ description }}</p>
      <slot />
    </div>
    <div v-if="$slots.action" class="ds-state-block__action">
      <slot name="action" />
    </div>
  </div>
</template>
