<template>
  <a-modal
    :open="open"
    :title="`漏洞扫描报告 · ${selectedIpSegment}`"
    width="95%"
    :footer="null"
    class="scan-report-modal"
    @cancel="emit('close')"
  >
    <div class="scan-report-shell ds-modal-shell">
      <StateBlock
        v-if="loading"
        type="loading"
        title="报告加载中"
        description="正在准备当前网段的漏洞扫描结果，请稍候。"
      >
        <template #action>
          <a-spin size="large" />
        </template>
      </StateBlock>

      <template v-else-if="scanReportData && scanReportData.length > 0">
        <div class="scan-summary-grid ds-stat-grid">
          <button
            type="button"
            class="scan-summary-card scan-summary-card--critical ds-stat-card"
            @click="emit('filterByThreatLevel', 'Critical')"
          >
            <div class="scan-summary-card__value">{{ riskCounts.Critical }}</div>
            <div class="scan-summary-card__label">Critical</div>
          </button>
          <button
            type="button"
            class="scan-summary-card scan-summary-card--high ds-stat-card"
            @click="emit('filterByThreatLevel', 'High')"
          >
            <div class="scan-summary-card__value">{{ riskCounts.High }}</div>
            <div class="scan-summary-card__label">High</div>
          </button>
          <button
            type="button"
            class="scan-summary-card scan-summary-card--medium ds-stat-card"
            @click="emit('filterByThreatLevel', 'Medium')"
          >
            <div class="scan-summary-card__value">{{ riskCounts.Medium }}</div>
            <div class="scan-summary-card__label">Medium</div>
          </button>
          <button
            type="button"
            class="scan-summary-card scan-summary-card--low ds-stat-card"
            @click="emit('filterByThreatLevel', 'Low')"
          >
            <div class="scan-summary-card__value">{{ riskCounts.Low }}</div>
            <div class="scan-summary-card__label">Low</div>
          </button>
          <button
            type="button"
            class="scan-summary-card scan-summary-card--info ds-stat-card"
            @click="emit('filterByThreatLevel', 'None')"
          >
            <div class="scan-summary-card__value">{{ riskCounts.None }}</div>
            <div class="scan-summary-card__label">Info</div>
          </button>
        </div>

        <PageToolbar class="scan-report-toolbar">
          <div class="scan-report-toolbar__summary">
            <span class="ds-status-pill ds-badge-info">网段：{{ selectedIpSegment }}</span>
            <span class="ds-status-pill">结果 {{ filteredScanReportData.length }} / {{ scanReportData.length }}</span>
          </div>
          <template #actions>
            <button type="button" class="ds-btn-primary" @click="emit('resetFilter')">显示全部</button>
          </template>
        </PageToolbar>

        <div class="scan-report-table-shell ds-panel-card ds-table-shell">
          <div class="ds-section-title">
            <div>
              <h3 class="ds-section-title__text">漏洞明细</h3>
              <p class="ds-section-title__hint">按风险级别筛选查看漏洞、端口与服务信息。</p>
            </div>
          </div>

          <a-table
            :data-source="filteredScanReportData"
            :columns="scanReportColumns"
            :pagination="{
              pageSize: 10,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
            }"
            :scroll="{ x: 1500 }"
            size="small"
            class="vulnerability-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'risk'">
                <a-tag :color="getRiskColor(record.Risk)" class="risk-tag">
                  {{ record.Risk || 'None' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'port'">
                <div>
                  <a-tag v-if="record.Port || record.port || record['Port(s)'] || record['Port/Service']" color="blue">
                    {{ record.Port || record.port || record['Port(s)'] || record['Port/Service'] }}
                  </a-tag>
                  <span v-else-if="record.Host && /:\d+/.test(record.Host)">
                    {{ (record.Host.match(/:(\d+)$/) || [])[1] }}
                  </span>
                  <span v-else>-</span>
                </div>
              </template>
            </template>
          </a-table>
        </div>
      </template>

      <StateBlock
        v-else
        type="empty"
        title="暂无扫描报告"
        description="当前网段暂时没有可展示的扫描结果。"
      />
    </div>
  </a-modal>
</template>

<script setup>
import { computed } from 'vue';
import {
  Modal as AModal,
  Spin as ASpin,
  Table as ATable,
  Tag as ATag,
} from 'ant-design-vue';
import PageToolbar from './ui/PageToolbar.vue';
import StateBlock from './ui/StateBlock.vue';

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedIpSegment: {
    type: String,
    default: '',
  },
  scanReportData: {
    type: Array,
    default: () => [],
  },
  filteredScanReportData: {
    type: Array,
    default: () => [],
  },
  scanReportColumns: {
    type: Array,
    default: () => [],
  },
  getRiskColor: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(['close', 'filterByThreatLevel', 'resetFilter']);

const riskCounts = computed(() => {
  const counts = {
    Critical: 0,
    High: 0,
    Medium: 0,
    Low: 0,
    None: 0,
  };

  for (const item of props.scanReportData || []) {
    const risk = item?.Risk;
    if (risk === 'Critical') counts.Critical += 1;
    else if (risk === 'High') counts.High += 1;
    else if (risk === 'Medium') counts.Medium += 1;
    else if (risk === 'Low') counts.Low += 1;
    else counts.None += 1;
  }

  return counts;
});
</script>

<style scoped>
.scan-report-modal :deep(.ant-modal-content) {
  padding: 0;
  overflow: hidden;
  border-radius: var(--ds-radius-xl);
  border: 1px solid var(--ds-card-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.92)),
    #ffffff;
  box-shadow: var(--ds-shadow-lg);
}

.scan-report-modal :deep(.ant-modal-header) {
  padding: 22px 24px 0;
  border-bottom: none;
  background: transparent;
}

.scan-report-modal :deep(.ant-modal-title) {
  color: var(--ds-text-strong);
  font-size: 22px;
  font-weight: 700;
}

.scan-report-modal :deep(.ant-modal-body) {
  padding: 20px 24px 24px;
}

.scan-report-modal :deep(.ant-modal-close) {
  inset-inline-end: 18px;
  top: 18px;
}

.scan-report-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: transparent;
  border: none;
  box-shadow: none;
}

.scan-summary-grid {
  gap: 16px;
}

.scan-summary-card {
  position: relative;
  overflow: hidden;
  appearance: none;
  border: 1px solid var(--ds-card-border);
  border-radius: var(--ds-radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.9));
  cursor: pointer;
  box-shadow: var(--ds-shadow-sm);
  transition:
    transform var(--ds-duration-base) var(--ds-ease-standard),
    box-shadow var(--ds-duration-base) var(--ds-ease-standard),
    border-color var(--ds-duration-fast) var(--ds-ease-standard),
    background var(--ds-duration-fast) var(--ds-ease-standard);
}

.scan-summary-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0));
  opacity: 0;
  transition: opacity var(--ds-duration-fast) var(--ds-ease-standard);
  pointer-events: none;
}

.scan-summary-card:hover {
  transform: translateY(-4px) scale(1.02);
}

.scan-summary-card:hover::after,
.scan-summary-card:focus-visible::after {
  opacity: 1;
}

.scan-summary-card:focus-visible {
  outline: 2px solid rgba(96, 165, 250, 0.55);
  outline-offset: 3px;
}

.scan-summary-card:active {
  transform: translateY(-1px) scale(0.995);
}

.scan-summary-card__value {
  color: var(--ds-text-strong);
  font-size: 28px;
  font-weight: 800;
}

.scan-summary-card__label {
  margin-top: 8px;
  color: var(--ds-text-primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.scan-summary-card--critical {
  border-color: rgba(239, 68, 68, 0.3);
  background: linear-gradient(180deg, rgba(254, 226, 226, 0.98), rgba(254, 242, 242, 0.94));
}

.scan-summary-card--critical:hover {
  border-color: rgba(220, 38, 38, 0.46);
  box-shadow: 0 18px 32px rgba(220, 38, 38, 0.18);
}

.scan-summary-card--high {
  border-color: rgba(249, 115, 22, 0.28);
  background: linear-gradient(180deg, rgba(255, 237, 213, 0.98), rgba(255, 247, 237, 0.94));
}

.scan-summary-card--high:hover {
  border-color: rgba(234, 88, 12, 0.44);
  box-shadow: 0 18px 32px rgba(234, 88, 12, 0.18);
}

.scan-summary-card--medium {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(180deg, rgba(254, 243, 199, 0.98), rgba(255, 251, 235, 0.94));
}

.scan-summary-card--medium:hover {
  border-color: rgba(217, 119, 6, 0.44);
  box-shadow: 0 18px 32px rgba(217, 119, 6, 0.18);
}

.scan-summary-card--low {
  border-color: rgba(250, 204, 21, 0.28);
  background: linear-gradient(180deg, rgba(254, 249, 195, 0.98), rgba(254, 252, 232, 0.94));
}

.scan-summary-card--low:hover {
  border-color: rgba(202, 138, 4, 0.4);
  box-shadow: 0 18px 32px rgba(202, 138, 4, 0.18);
}

.scan-summary-card--info {
  border-color: rgba(96, 165, 250, 0.32);
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.98), rgba(239, 246, 255, 0.94));
}

.scan-summary-card--info:hover {
  border-color: rgba(37, 99, 235, 0.44);
  box-shadow: 0 18px 32px rgba(37, 99, 235, 0.18);
}

.scan-report-toolbar {
  margin-bottom: 0;
}

.scan-report-toolbar__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scan-report-table-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vulnerability-table :deep(.ant-table) {
  border-radius: var(--ds-radius-md);
  overflow: hidden;
}

.vulnerability-table :deep(.ant-table-thead > tr > th) {
  background: #f8fbff;
  color: var(--ds-text-primary);
  font-weight: 700;
}

.vulnerability-table :deep(.ant-table-tbody > tr:hover > td) {
  background: #f6f9fd;
}

.vulnerability-table :deep(.ant-table-tbody > tr > td) {
  color: var(--ds-text-primary);
}

.risk-tag {
  border-radius: 999px;
  font-weight: 700;
}

@media (max-width: 1200px) {
  .scan-summary-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .scan-report-modal :deep(.ant-modal-body) {
    padding: 16px;
  }

  .scan-summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
