<template>
  <Teleport to="body">
    <div class="st-outer" aria-live="polite">
      <Transition name="card-pop">
        <div v-if="state !== null" class="st-card ds-glass-card" :class="cardStateClass">
          <Transition name="inner-swap" mode="out-in">
            <div v-if="state === 'loading'" key="loading" class="st-inner">
              <div class="st-spinner">
                <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="30" cy="30" r="24" stroke="rgba(37,99,235,0.14)" stroke-width="4" />
                  <circle
                    class="spin-arc"
                    cx="30"
                    cy="30"
                    r="24"
                    stroke-width="4"
                    stroke-linecap="round"
                    stroke="url(#spinGrad)"
                    stroke-dasharray="75.4 75.4"
                  />
                  <defs>
                    <linearGradient id="spinGrad" x1="0" y1="0" x2="60" y2="60" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stop-color="#2563eb" />
                      <stop offset="100%" stop-color="#60a5fa" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
              <div class="st-copy">
                <span class="ds-status-pill ds-badge-info">数据快照</span>
                <p class="st-title">数据切换中</p>
                <p class="st-sub">{{ snapshotLabel }}</p>
              </div>
            </div>

            <div v-else-if="state === 'success'" key="success" class="st-inner">
              <div class="st-check">
                <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle class="check-ring" cx="30" cy="30" r="24" stroke="#10b981" stroke-width="3.5" />
                  <path
                    class="check-tick"
                    stroke="#10b981"
                    stroke-width="4"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M18 31l9 9 15-16"
                  />
                </svg>
              </div>
              <div class="st-copy">
                <span class="ds-status-pill ds-badge-success">切换完成</span>
                <p class="st-title success">已切换到目标快照</p>
                <p class="st-sub">{{ snapshotLabel }}</p>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, inject, ref } from 'vue'

const state = inject('snapshotTransitionState', ref(null))
const activeSnapshot = inject('snapshot', ref(null))

const snapshotLabel = computed(() => {
  const snapshot = activeSnapshot.value
  if (!snapshot) return '最新数据'
  if (snapshot.length === 8) {
    return `${snapshot.slice(0, 4)}-${snapshot.slice(4, 6)}-${snapshot.slice(6, 8)}`
  }
  return snapshot
})

const cardStateClass = computed(() => (
  state.value === 'loading' ? 'ds-state-loading' : 'ds-state-info'
))
</script>

<style scoped>
.st-outer {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  pointer-events: none;
  padding: 0 20px;
}

.st-card {
  width: min(420px, calc(100vw - 160px));
  min-width: 260px;
  max-width: min(420px, calc(100vw - 32px));
  padding: 18px 22px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-pop-enter-active {
  transition: opacity 0.28s ease, transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.card-pop-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.card-pop-enter-from {
  opacity: 0;
  transform: scale(0.72);
}

.card-pop-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.inner-swap-enter-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.inner-swap-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.inner-swap-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.94);
}

.inner-swap-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
}

.st-inner {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
}

.st-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.st-spinner,
.st-check {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
}

.st-spinner svg,
.st-check svg {
  width: 100%;
  height: 100%;
}

.spin-arc {
  animation: spin-rotate 0.9s linear infinite;
  transform-origin: 30px 30px;
}

@keyframes spin-rotate {
  to {
    transform: rotate(360deg);
  }
}

.check-ring {
  stroke-dasharray: 150.8;
  stroke-dashoffset: 150.8;
  animation: ring-draw 0.42s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.check-tick {
  stroke-dasharray: 34;
  stroke-dashoffset: 34;
  animation: tick-draw 0.28s 0.38s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes ring-draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes tick-draw {
  to {
    stroke-dashoffset: 0;
  }
}

.st-title {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
}

.st-title.success {
  color: #047857;
}

.st-sub {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  letter-spacing: 0.03em;
}

@media (max-width: 640px) {
  .st-outer {
    padding: 0 16px;
  }

  .st-card {
    width: min(calc(100vw - 32px), 100%);
    padding: 16px 18px;
    border-radius: 20px;
  }

  .st-inner {
    gap: 12px;
  }

  .st-copy {
    gap: 6px;
  }
}
</style>
