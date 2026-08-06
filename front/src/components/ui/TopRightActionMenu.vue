<template>
  <div
    ref="rootRef"
    class="top-right-action-menu"
    :class="[`top-right-action-menu--${variant}`, { 'is-open': isOpen }]"
  >
    <button
      type="button"
      class="top-right-action-menu__trigger ds-icon-btn ds-floating-panel"
      :class="{ 'is-open': isOpen }"
      :title="isOpen ? closeTitle : mainTitle"
      :aria-label="isOpen ? closeLabel : mainLabel"
      @click="toggleMenu"
    >
      <span class="u-sr-only">{{ isOpen ? closeLabel : mainLabel }}</span>
      <svg
        v-if="!isOpen"
        class="top-right-action-menu__trigger-icon"
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect x="4" y="4" width="6" height="6" rx="1.5" fill="currentColor" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" fill="currentColor" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" fill="currentColor" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" fill="currentColor" />
      </svg>
      <svg
        v-else
        class="top-right-action-menu__trigger-icon"
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M6 6L18 18M18 6L6 18"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
      </svg>
    </button>

    <Transition name="top-right-action-menu-panel">
      <div
        v-if="isOpen"
        class="top-right-action-menu__panel ds-floating-panel ds-glass-card"
        role="menu"
        aria-label="页面功能"
      >
        <TransitionGroup name="top-right-action-menu-item" tag="div" class="top-right-action-menu__list">
          <button
            v-for="action in actions"
            :key="action.key"
            type="button"
            class="top-right-action-menu__action ds-icon-btn ds-floating-panel"
            :class="{
              'is-active': action.active,
              'is-danger': action.danger,
            }"
            :disabled="action.disabled"
            :title="action.title || action.label"
            :aria-label="action.label"
            @click="handleAction(action)"
          >
            <span class="u-sr-only">{{ action.label }}</span>
            <span class="top-right-action-menu__action-icon">
              <slot :name="`icon-${action.key}`" :action="action">
                <span class="top-right-action-menu__fallback">
                  {{ action.label.slice(0, 1) }}
                </span>
              </slot>
            </span>
          </button>
        </TransitionGroup>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  actions: {
    type: Array,
    default: () => [],
  },
  contextKey: {
    type: [String, Number],
    default: '',
  },
  variant: {
    type: String,
    default: 'map',
  },
  autoCollapseOnAction: {
    type: Boolean,
    default: true,
  },
  mainLabel: {
    type: String,
    default: '展开快捷功能',
  },
  mainTitle: {
    type: String,
    default: '展开快捷功能',
  },
  closeLabel: {
    type: String,
    default: '收起快捷功能',
  },
  closeTitle: {
    type: String,
    default: '收起快捷功能',
  },
})

const emit = defineEmits(['toggle', 'action-click'])

const rootRef = ref(null)
const isOpen = ref(false)

const closeMenu = () => {
  if (!isOpen.value) return
  isOpen.value = false
  emit('toggle', false)
}

const openMenu = () => {
  if (isOpen.value) return
  isOpen.value = true
  emit('toggle', true)
}

const toggleMenu = () => {
  if (isOpen.value) {
    closeMenu()
    return
  }
  openMenu()
}

const handleAction = (action) => {
  if (action.disabled) return
  emit('action-click', action.key, action)
  if (props.autoCollapseOnAction && !action.keepOpen) {
    closeMenu()
  }
}

const handlePointerDown = (event) => {
  if (!rootRef.value || rootRef.value.contains(event.target)) {
    return
  }
  closeMenu()
}

watch(
  () => props.contextKey,
  () => {
    closeMenu()
  },
)

onMounted(() => {
  document.addEventListener('pointerdown', handlePointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handlePointerDown)
})

defineExpose({
  closeMenu,
  openMenu,
  toggleMenu,
})
</script>

<style scoped>
.top-right-action-menu {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.top-right-action-menu__trigger,
.top-right-action-menu__action {
  width: 52px;
  height: 52px;
  color: var(--ds-text-primary);
  border-color: rgba(255, 255, 255, 0.54);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.84));
}

.top-right-action-menu__trigger {
  position: relative;
  z-index: 1;
}

.top-right-action-menu__trigger:hover,
.top-right-action-menu__action:hover {
  transform: translateY(-2px);
  color: var(--ds-text-strong);
  box-shadow: var(--ds-shadow-md);
}

.top-right-action-menu__trigger.is-open,
.top-right-action-menu__action.is-active {
  color: #ffffff;
  border-color: rgba(191, 219, 254, 0.78);
  background: linear-gradient(135deg, var(--ds-primary-500), var(--ds-primary-400));
  box-shadow: 0 16px 32px rgba(37, 99, 235, 0.3);
}

.top-right-action-menu__action.is-danger {
  color: var(--ds-danger-500);
}

.top-right-action-menu__action.is-danger:hover,
.top-right-action-menu__action.is-danger.is-active {
  color: #ffffff;
  border-color: rgba(252, 165, 165, 0.76);
  background: linear-gradient(135deg, #ef4444, #f87171);
  box-shadow: 0 16px 32px rgba(239, 68, 68, 0.25);
}

.top-right-action-menu__trigger:focus-visible,
.top-right-action-menu__action:focus-visible {
  outline: 2px solid rgba(96, 165, 250, 0.55);
  outline-offset: 3px;
}

.top-right-action-menu__trigger-icon,
.top-right-action-menu__action-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.top-right-action-menu__panel {
  margin-top: 12px;
  padding: 10px;
}

.top-right-action-menu__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.top-right-action-menu__fallback {
  font-size: 14px;
  font-weight: 700;
}

.top-right-action-menu-panel-enter-active,
.top-right-action-menu-panel-leave-active {
  transition:
    opacity 0.22s var(--ds-ease-standard),
    transform 0.22s var(--ds-ease-standard);
  transform-origin: top right;
}

.top-right-action-menu-panel-enter-from,
.top-right-action-menu-panel-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}

.top-right-action-menu-item-enter-active,
.top-right-action-menu-item-leave-active {
  transition:
    opacity 0.2s var(--ds-ease-standard),
    transform 0.2s var(--ds-ease-standard);
}

.top-right-action-menu-item-enter-from,
.top-right-action-menu-item-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.94);
}

@media (max-width: 768px) {
  .top-right-action-menu__trigger,
  .top-right-action-menu__action {
    width: 48px;
    height: 48px;
  }

  .top-right-action-menu__panel {
    margin-top: 10px;
    padding: 8px;
  }

  .top-right-action-menu__list {
    gap: 8px;
  }
}
</style>
