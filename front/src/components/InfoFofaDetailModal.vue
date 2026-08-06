<template>
  <a-modal
    :open="open"
    :title="item ? `FOFA 详情 · ${item.ip}` : 'FOFA 详情'"
    :footer="null"
    width="860px"
    class="fofa-detail-modal"
    @cancel="emit('close')"
  >
    <div class="fofa-detail-shell ds-modal-shell">
      <StateBlock
        v-if="!item"
        type="empty"
        title="暂无详情内容"
        description="当前资产尚未返回更多 FOFA 详情。"
      />

      <template v-else>
        <div class="fofa-detail-summary ds-panel-card">
          <div class="fofa-detail-summary__meta">
            <span class="ds-badge ds-badge-info">{{ item.ip }}</span>
            <span class="ds-badge">{{ item.port || '未知端口' }}</span>
            <span class="ds-badge ds-badge-success">{{ item.protocol || '未知协议' }}</span>
          </div>
          <p class="fofa-detail-summary__description">
            {{ item.country_name || '未知国家' }} / {{ item.region || '未知地区' }} / {{ item.city || '未知城市' }}
          </p>
        </div>

        <div class="fofa-detail-grid">
          <div class="fofa-detail-section ds-panel-card">
            <div class="ds-section-title">
              <div>
                <h3 class="ds-section-title__text">基础信息</h3>
                <p class="ds-section-title__hint">查看网络位置、服务指纹与资产归属信息。</p>
              </div>
            </div>
            <a-descriptions bordered :column="1" size="small" class="fofa-descriptions">
              <a-descriptions-item label="IP 地址">{{ item.ip }}</a-descriptions-item>
              <a-descriptions-item label="端口">{{ item.port || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="协议">{{ item.protocol || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="国家">{{ item.country_name || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="地区">{{ item.region || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="城市">{{ item.city || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="经纬度">
                {{ item.longitude || '0' }}, {{ item.latitude || '0' }}
              </a-descriptions-item>
              <a-descriptions-item label="AS 编号">{{ item.as_number || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="AS 组织">{{ item.as_organization || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="主机名">{{ item.host || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="域名">{{ item.domain || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="操作系统">{{ item.os || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="服务">{{ item.server || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="ICP 备案">{{ item.icp || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="网页标题">{{ item.title || '无标题' }}</a-descriptions-item>
              <a-descriptions-item label="JARM 指纹">{{ item.jarm || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="基础协议">{{ item.base_protocol || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="链接">
                <a v-if="isSafeExternalLink(item.link)" :href="item.link" target="_blank" rel="noopener noreferrer">{{ item.link }}</a>
                <span v-else-if="item.link">{{ item.link }}</span>
                <span v-else>无链接</span>
              </a-descriptions-item>
            </a-descriptions>
          </div>

          <div class="fofa-detail-section ds-panel-card">
            <div class="ds-section-title">
              <div>
                <h3 class="ds-section-title__text">证书与 TLS</h3>
                <p class="ds-section-title__hint">汇总证书主体、签发方与 TLS 指纹信息。</p>
              </div>
            </div>
            <a-descriptions bordered :column="1" size="small" class="fofa-descriptions">
              <a-descriptions-item label="证书颁发机构">{{ item.certs_issuer_org || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="证书颁发人">{{ item.certs_issuer_cn || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="证书主体机构">{{ item.certs_subject_org || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="证书主体名称">{{ item.certs_subject_cn || '未知' }}</a-descriptions-item>
              <a-descriptions-item label="TLS JA3S">
                {{ item.tls_ja3s && item.tls_ja3s.trim() ? item.tls_ja3s : '未知' }}
              </a-descriptions-item>
              <a-descriptions-item label="TLS 版本">
                {{ item.tls_version && item.tls_version.trim() ? item.tls_version : '未知' }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </div>

        <div class="fofa-detail-footer ds-page-toolbar">
          <span class="fofa-detail-footer__hint">外部链接将在新窗口打开，建议结合扫描报告继续分析。</span>
          <button type="button" class="ds-btn-secondary" @click="emit('close')">关闭</button>
        </div>
      </template>
    </div>
  </a-modal>
</template>

<script setup>
import {
  Descriptions as ADescriptions,
  Modal as AModal,
} from 'ant-design-vue';
import StateBlock from './ui/StateBlock.vue';

defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  item: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['close']);
const ADescriptionsItem = ADescriptions.Item;

// 第三方 CSV 中的 link 可能是 javascript: 等危险协议，只允许 http/https 渲染为链接
const isSafeExternalLink = (link) => /^https?:\/\//i.test(String(link || '').trim());
</script>

<style scoped>
.fofa-detail-modal :deep(.ant-modal-content) {
  padding: 0;
  overflow: hidden;
  border-radius: var(--ds-radius-xl);
  border: 1px solid var(--ds-card-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.92)),
    #ffffff;
  box-shadow: var(--ds-shadow-lg);
}

.fofa-detail-modal :deep(.ant-modal-header) {
  padding: 22px 24px 0;
  border-bottom: none;
  background: transparent;
}

.fofa-detail-modal :deep(.ant-modal-title) {
  color: var(--ds-text-strong);
  font-size: 22px;
  font-weight: 700;
}

.fofa-detail-modal :deep(.ant-modal-body) {
  padding: 20px 24px 24px;
}

.fofa-detail-modal :deep(.ant-modal-close) {
  inset-inline-end: 18px;
  top: 18px;
}

.fofa-detail-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: transparent;
  box-shadow: none;
  border: none;
}

.fofa-detail-summary {
  padding: 20px;
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.6), rgba(255, 255, 255, 0.94));
}

.fofa-detail-summary__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fofa-detail-summary__description {
  margin: 12px 0 0;
  color: var(--ds-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.fofa-detail-grid {
  display: grid;
  gap: 18px;
}

.fofa-detail-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fofa-descriptions :deep(.ant-descriptions-view) {
  border-radius: var(--ds-radius-md);
  overflow: hidden;
  border: 1px solid var(--ds-border-soft);
}

.fofa-descriptions :deep(.ant-descriptions-item-label) {
  width: 180px;
  background: #f8fbff;
  color: var(--ds-text-primary);
  font-weight: 700;
}

.fofa-descriptions :deep(.ant-descriptions-item-content) {
  color: var(--ds-text-primary);
  line-height: 1.7;
}

.fofa-detail-footer {
  padding-inline: 0;
  border: none;
  background: transparent;
  box-shadow: none;
}

.fofa-detail-footer__hint {
  color: var(--ds-text-secondary);
  font-size: 13px;
}

@media (max-width: 768px) {
  .fofa-detail-modal :deep(.ant-modal-body) {
    padding: 16px;
  }

  .fofa-detail-summary,
  .fofa-detail-section {
    padding: 16px;
  }

  .fofa-descriptions :deep(.ant-descriptions-item-label) {
    width: 128px;
  }
}
</style>
