<template>
  <div class="fofa-panel">
    <div class="fofa-panel__header ds-section-title">
      <div>
        <h3 class="ds-section-title__text">FOFA 探测结果</h3>
        <p class="ds-section-title__hint">按资产基础信息快速浏览暴露面，并进入详情查看。</p>
      </div>
      <span class="ds-status-pill ds-badge-info">共 {{ pagination.total || 0 }} 条</span>
    </div>

    <PageToolbar class="fofa-toolbar">
      <label class="u-sr-only" for="fofa-search-input">搜索 FOFA 资产</label>
      <a-input-search
        id="fofa-search-input"
        :value="searchKeyword"
        name="fofa_search"
        size="large"
        autocomplete="off"
        aria-label="搜索 FOFA 资产"
        placeholder="搜索 IP、端口、协议或组织"
        @update:value="(value) => emit('update:searchKeyword', value)"
        @search="(value) => emit('search', value)"
      />
      <template #actions>
        <span class="fofa-toolbar__hint">支持关键字检索，便于快速收敛结果范围。</span>
      </template>
    </PageToolbar>

    <div class="fofa-content-shell">
      <StateBlock
        v-if="loading && !displayedData.length"
        type="loading"
        title="FOFA 结果加载中"
        description="正在同步当前查询条件下的 FOFA 资产信息。"
      >
        <template #action>
          <a-spin />
        </template>
      </StateBlock>

      <StateBlock
        v-else-if="!displayedData.length"
        type="empty"
        title="暂无 FOFA 数据"
        description="当前筛选条件下没有匹配结果，请调整关键字后重试。"
      />

      <template v-else>
        <div class="fofa-card-container">
          <a-card v-for="item in displayedData" :key="item.key" class="fofa-card ds-surface-card" hoverable>
            <div class="fofa-card-header">
              <div class="fofa-card-tags">
                <span class="ds-badge ds-badge-info">{{ item.ip }}</span>
                <span class="ds-badge">{{ item.port }}</span>
                <span class="ds-badge ds-badge-success">{{ item.protocol || '未知协议' }}</span>
              </div>

              <div class="fofa-card-location">
                <span class="fofa-card-location__icon">
                  <EnvironmentOutlined />
                </span>
                <div class="fofa-card-location__copy">
                  <span class="fofa-card-location__label">位置信息</span>
                  <strong>{{ item.country_name || '未知国家 / 地区' }}</strong>
                  <span>{{ item.city || '未知城市' }}</span>
                </div>
              </div>
            </div>

            <div class="fofa-card-content">
              <div class="fofa-info-row">
                <span class="info-label">AS 组织</span>
                <span class="info-value">{{ item.as_organization || '未知' }}</span>
              </div>

              <div class="fofa-info-row">
                <span class="info-label">主机名</span>
                <span class="info-value">{{ item.host || '未知' }}</span>
              </div>

              <div class="fofa-info-row">
                <span class="info-label">网页标题</span>
                <span class="info-value title-text">{{ item.title || '无标题' }}</span>
              </div>

              <div class="fofa-info-row">
                <span class="info-label">服务</span>
                <span class="info-value">{{ item.server || '未知' }}</span>
              </div>
            </div>

            <div class="fofa-card-footer">
              <button type="button" class="ds-btn-primary" @click="emit('viewDetail', item)">
                查看详情
              </button>
            </div>
          </a-card>
        </div>
      </template>
    </div>

    <div class="fofa-pagination-shell ds-page-toolbar">
      <div class="fofa-pagination-info">
        显示 {{ displayedData.length }} 条，本页第 {{ pagination.current }} 页
      </div>
      <a-pagination
        class="fofa-pagination"
        :current="pagination.current"
        :total="pagination.total"
        :page-size="pagination.pageSize"
        :page-size-options="pagination.pageSizeOptions"
        :show-size-changer="true"
        @change="(page, pageSize) => emit('pageChange', page, pageSize)"
        @show-size-change="(current, size) => emit('pageSizeChange', current, size)"
      />
    </div>
  </div>
</template>

<script setup>
import {
  Card as ACard,
  Input as AInput,
  Pagination as APagination,
  Spin as ASpin,
} from 'ant-design-vue';
import { EnvironmentOutlined } from '@ant-design/icons-vue';
import PageToolbar from './ui/PageToolbar.vue';
import StateBlock from './ui/StateBlock.vue';

defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  searchKeyword: {
    type: String,
    default: '',
  },
  displayedData: {
    type: Array,
    default: () => [],
  },
  pagination: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits([
  'update:searchKeyword',
  'search',
  'viewDetail',
  'pageChange',
  'pageSizeChange',
]);

const AInputSearch = AInput.Search;
</script>

<style scoped>
.fofa-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.fofa-panel__header {
  margin-bottom: 0;
}

.fofa-toolbar {
  margin-bottom: 0;
}

.fofa-toolbar__hint {
  color: var(--ds-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.fofa-toolbar :deep(.ant-input-search) {
  width: min(100%, 420px);
}

.fofa-content-shell {
  min-height: 220px;
}

.fofa-card-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.fofa-card {
  padding: 20px;
  border-radius: var(--ds-radius-lg);
  border-color: var(--ds-card-border);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.9));
  box-shadow: var(--ds-shadow-sm);
}

.fofa-card :deep(.ant-card-body) {
  padding: 0;
}

.fofa-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--ds-shadow-md);
}

.fofa-card-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.fofa-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fofa-card-location {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border-radius: var(--ds-radius-md);
  border: 1px solid rgba(96, 165, 250, 0.28);
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.98), rgba(239, 246, 255, 0.94));
  color: var(--ds-primary-600);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 10px 24px rgba(37, 99, 235, 0.08);
}

.fofa-card-location__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  color: var(--ds-primary-600);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.12);
}

.fofa-card-location__icon :deep(svg) {
  font-size: 18px;
}

.fofa-card-location__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.fofa-card-location__label {
  color: var(--ds-primary-600);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.fofa-card-location__copy strong {
  color: var(--ds-text-strong);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}

.fofa-card-location__copy span:last-child {
  color: var(--ds-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.fofa-card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fofa-info-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.info-label {
  color: var(--ds-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.info-value {
  color: var(--ds-text-primary);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.title-text {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.fofa-card-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.fofa-pagination-shell {
  margin-top: 4px;
}

.fofa-pagination-info {
  color: var(--ds-text-secondary);
  font-size: 13px;
}

.fofa-pagination {
  margin-left: auto;
}

.fofa-pagination :deep(.ant-pagination-options) {
  margin-inline-start: 12px;
}

@media (max-width: 960px) {
  .fofa-toolbar :deep(.ant-input-search) {
    width: 100%;
  }

  .fofa-pagination-shell {
    align-items: stretch;
  }

  .fofa-pagination {
    margin-left: 0;
  }
}
</style>
