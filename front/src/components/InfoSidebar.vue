<template>
  <transition :name="position === 'left' ? 'slide-right' : 'slide-left'">
    <div
      v-if="visible"
      class="info-sidebar"
      :class="position"
      :style="{ [position]: 0 }"
    >
      <div class="sidebar-header">
        <div class="sidebar-title-wrap">
          <h3>{{ title }}</h3>
          <div v-if="contextTags.length > 0" class="sidebar-context-tags">
            <span v-for="tag in contextTags" :key="`${tag.label}-${tag.value}`" class="sidebar-context-tag">
              <span class="sidebar-context-tag-label">{{ tag.label }}</span>
              <strong class="sidebar-context-tag-value">{{ tag.value }}</strong>
            </span>
          </div>
        </div>
        <button class="close-btn" type="button" aria-label="关闭详情" @click="close">×</button>
      </div>

      <div class="sidebar-content">
        <div v-html="sanitizedContent"></div>

        <div v-if="networkSegments.length > 0" class="network-segment-section">
          <div class="segment-header">
            <span class="segment-icon">📗</span>
            <span class="segment-label">IP 网段</span>
            <a-tag color="cyan">{{ networkSegments.length }}</a-tag>
          </div>
          <a-table
            :columns="segmentColumns"
            :data-source="segmentDataSource"
            :pagination="segmentPagination"
            size="small"
            :scroll="{ y: 200 }"
            class="segment-table"
          >
            <template #bodyCell="{ column, text, record }">
              <template v-if="column.key === 'index'">
                <span class="index-cell">{{ record.index }}</span>
              </template>
              <template v-else-if="column.key === 'segment'">
                <code class="segment-code">{{ text }}</code>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue';
import { Table as ATable, Tag as ATag } from 'ant-design-vue';
import { sanitizeHtml } from '../utils/sanitizeHtml.js';

const props = defineProps({
  visible: Boolean,
  position: {
    type: String,
    default: 'right',
    validator: (value) => ['left', 'right'].includes(value),
  },
  title: {
    type: String,
    default: '',
  },
  content: {
    type: String,
    default: '',
  },
  networkSegments: {
    type: Array,
    default: () => [],
  },
  contextTags: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['close']);

const close = () => {
  emit('close');
};

const sanitizedContent = computed(() => sanitizeHtml(props.content || ''));

const segmentColumns = [
  {
    title: '#',
    dataIndex: 'index',
    key: 'index',
    width: 50,
    align: 'center',
  },
  {
    title: 'IP 网段',
    dataIndex: 'segment',
    key: 'segment',
  },
];

const segmentDataSource = computed(() => {
  return props.networkSegments.map((segment, idx) => ({
    key: idx,
    index: idx + 1,
    segment,
  }));
});

const segmentPagination = computed(() => ({
  pageSize: 5,
  size: 'small',
  showSizeChanger: false,
  showTotal: (total) => `共 ${total} 个网段`,
}));
</script>

<style scoped>
.info-sidebar {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 360px;
  height: 60vh;
  max-height: 700px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  color: #1a1a1a;
  border: 1px solid #e5e7eb;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.1);
  z-index: 2800;
  overflow-y: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  font-family: 'Plus Jakarta Sans', 'Segoe UI', 'PingFang SC', sans-serif;
  transition: all 0.3s ease;
}

.info-sidebar.left {
  left: 20px;
}

.info-sidebar.right {
  right: 20px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #eef2f7;
  background: #f8f9fa;
}

.sidebar-title-wrap {
  min-width: 0;
  flex: 1;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  word-break: break-word;
}

.sidebar-context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.sidebar-context-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(191, 219, 254, 0.9);
}

.sidebar-context-tag-label {
  font-size: 11px;
  color: #64748b;
}

.sidebar-context-tag-value {
  font-size: 11px;
  color: #1d4ed8;
  word-break: break-word;
}

.close-btn {
  background: #f1f5f9;
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: inherit;
  transition: all 0.3s ease;
  padding: 0;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  transform: translateY(-1px);
}

.sidebar-content {
  padding: 16px 20px;
  flex: 1;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.6;
}

.network-segment-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #edf2f7;
}

.segment-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  gap: 8px;
}

.segment-label {
  font-weight: 600;
  font-size: 13px;
  color: #4a4a4a;
}

.segment-icon {
  font-size: 16px;
}

.segment-code {
  font-family: ui-monospace, SFMono-Regular, monospace;
  background-color: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.index-cell {
  color: #9ca3af;
  font-size: 12px;
}

.slide-right-enter-active,
.slide-right-leave-active,
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translate(-100%, -50%);
  opacity: 0;
}

.slide-left-enter-from,
.slide-left-leave-to {
  transform: translate(100%, -50%);
  opacity: 0;
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
