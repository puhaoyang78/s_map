<template>
  <div class="ds-page-toolbar">
    <div class="ds-page-toolbar__content">
      <slot />
    </div>
    <div v-if="$slots.actions" class="ds-page-toolbar__actions">
      <slot name="actions" />
    </div>
  </div>
</template>
