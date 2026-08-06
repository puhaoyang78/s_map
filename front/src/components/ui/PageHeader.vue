<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: '',
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
</script>

<template>
  <header class="ds-page-header">
    <div class="ds-page-header__body">
      <span v-if="eyebrow" class="ds-page-header__eyebrow">{{ eyebrow }}</span>
      <div v-if="title || $slots.meta" class="ds-page-header__title-row">
        <h1 v-if="title" class="ds-page-header__title">{{ title }}</h1>
        <div v-if="$slots.meta" class="ds-page-header__meta">
          <slot name="meta" />
        </div>
      </div>
      <p v-if="description" class="ds-page-header__description">{{ description }}</p>
      <slot />
    </div>
    <div v-if="$slots.extra" class="ds-page-header__extra">
      <slot name="extra" />
    </div>
  </header>
</template>
