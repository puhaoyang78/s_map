import { getChinesePopName } from './popNameMapping'
import { getChineseGatewayName } from './gatewayNameMapping'

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;')

const toSafeNumber = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

const normalizeDateValue = (value) => {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const text = String(value).trim()
  if (!text) return null

  const hasTimezone = /(?:[zZ]|[+-]\d{2}:\d{2})$/.test(text)
  const candidate = hasTimezone ? text : `${text}Z`
  const parsed = new Date(candidate)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const formatDisplayTime = (value) => {
  const parsed = normalizeDateValue(value)
  if (!parsed) {
    return value ? escapeHtml(value) : '-'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(parsed)
}

const formatCoordinate = (value) => {
  const number = toSafeNumber(value)
  return number === null ? '-' : number.toFixed(5)
}

const formatMetric = (value, digits = 2, unit = '') => {
  const number = toSafeNumber(value)
  if (number === null) {
    return '-'
  }
  return `${number.toFixed(digits)}${unit}`
}

const renderCode = (value, tone = '#1d4ed8') => (
  `<code style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;background:rgba(37,99,235,0.08);border:1px solid rgba(147,197,253,0.45);font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;color:${tone};">${escapeHtml(value)}</code>`
)

const renderPill = (value, tone = 'info') => {
  const themes = {
    info: {
      background: 'rgba(37,99,235,0.08)',
      border: 'rgba(147,197,253,0.5)',
      color: '#1d4ed8',
    },
    success: {
      background: 'rgba(16,185,129,0.12)',
      border: 'rgba(52,211,153,0.42)',
      color: '#047857',
    },
    warning: {
      background: 'rgba(245,158,11,0.12)',
      border: 'rgba(251,191,36,0.45)',
      color: '#b45309',
    },
    danger: {
      background: 'rgba(239,68,68,0.12)',
      border: 'rgba(252,165,165,0.46)',
      color: '#b91c1c',
    },
  }

  const theme = themes[tone] || themes.info
  return `<span style="display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;background:${theme.background};border:1px solid ${theme.border};font-size:12px;font-weight:600;color:${theme.color};">${escapeHtml(value)}</span>`
}

const renderTagList = (items = [], tone = 'info') => {
  if (!items.length) {
    return '<span style="color:#94a3b8;font-size:13px;">暂无数据</span>'
  }

  const themeMap = {
    info: 'rgba(37,99,235,0.08)',
    success: 'rgba(16,185,129,0.12)',
    warning: 'rgba(245,158,11,0.12)',
  }

  const borderMap = {
    info: 'rgba(147,197,253,0.5)',
    success: 'rgba(110,231,183,0.45)',
    warning: 'rgba(251,191,36,0.45)',
  }

  const colorMap = {
    info: '#1d4ed8',
    success: '#047857',
    warning: '#b45309',
  }

  return `
    <div style="display:flex;flex-wrap:wrap;gap:8px;">
      ${items.map((item) => `
        <span style="display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;background:${themeMap[tone] || themeMap.info};border:1px solid ${borderMap[tone] || borderMap.info};font-size:12px;font-weight:600;color:${colorMap[tone] || colorMap.info};">
          ${escapeHtml(item)}
        </span>
      `).join('')}
    </div>
  `
}

const renderRow = (label, value) => `
  <div style="display:grid;grid-template-columns:minmax(88px, 108px) minmax(0, 1fr);gap:12px;align-items:start;">
    <div style="font-size:12px;font-weight:600;color:#64748b;line-height:1.6;">${escapeHtml(label)}</div>
    <div style="font-size:13px;line-height:1.7;color:#0f172a;word-break:break-word;overflow-wrap:anywhere;">${value}</div>
  </div>
`

const renderSection = (title, rows, accent = 'primary') => {
  const accentStyles = {
    primary: {
      background: 'linear-gradient(180deg, rgba(248,251,255,0.96), rgba(255,255,255,0.92))',
      border: 'rgba(191,219,254,0.72)',
      titleColor: '#1d4ed8',
    },
    success: {
      background: 'linear-gradient(180deg, rgba(240,253,250,0.95), rgba(255,255,255,0.92))',
      border: 'rgba(167,243,208,0.76)',
      titleColor: '#059669',
    },
    warning: {
      background: 'linear-gradient(180deg, rgba(255,251,235,0.96), rgba(255,255,255,0.92))',
      border: 'rgba(253,230,138,0.8)',
      titleColor: '#d97706',
    },
  }

  const theme = accentStyles[accent] || accentStyles.primary
  return `
    <section style="padding:16px 18px;border-radius:18px;border:1px solid ${theme.border};background:${theme.background};box-shadow:0 12px 28px rgba(15,23,42,0.05);">
      <div style="font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:${theme.titleColor};margin-bottom:14px;">
        ${escapeHtml(title)}
      </div>
      <div style="display:flex;flex-direction:column;gap:12px;">
        ${rows.join('')}
      </div>
    </section>
  `
}

const buildDetailRoot = (sections) => `
  <div style="display:flex;flex-direction:column;gap:14px;font-family:'Plus Jakarta Sans','Segoe UI','PingFang SC',sans-serif;color:#0f172a;">
    ${sections.join('')}
  </div>
`

/**
 * Build a safe heatmap popup content node using DOM APIs.
 * @param {string} countryZh
 * @param {string} regionZh
 * @param {number} count
 * @returns {HTMLDivElement}
 */
export const buildHeatmapPopupElement = (countryZh, regionZh, count) => {
  const root = document.createElement('div')
  root.className = 'heatmap-info'

  const createRow = (labelText, valueText, highlight = false, countMode = false) => {
    const row = document.createElement('div')
    row.className = highlight ? 'info-row highlight' : 'info-row'

    const label = document.createElement('span')
    label.className = 'info-label'
    label.textContent = labelText

    const value = document.createElement('span')
    value.className = countMode ? 'info-value count' : 'info-value'
    value.textContent = valueText

    row.appendChild(label)
    row.appendChild(value)
    return row
  }

  root.appendChild(createRow('国家/地区', String(countryZh || '未知国家/地区')))
  root.appendChild(createRow('省份/州', String(regionZh || '未知省份/州')))
  root.appendChild(createRow('终端设备数', Number(count || 0).toLocaleString(), true, true))

  return root
}

/**
 * Format PoP detail HTML for sidebar rendering.
 * @param {Record<string, any>} properties
 * @returns {string}
 */
export function formatStarlinkPopDetails(properties) {
  if (!properties) return ''

  const parseArrayProp = (prop) => {
    if (!prop) return []
    if (Array.isArray(prop)) return prop
    if (typeof prop === 'string') {
      try {
        const parsed = JSON.parse(prop)
        return Array.isArray(parsed) ? parsed : []
      } catch {
        return []
      }
    }
    return []
  }

  const coordinates = properties._geometry?.coordinates || []
  const ixConnections = parseArrayProp(properties.ixConnections)
  const coveragecity = parseArrayProp(properties.coveragecity)
  const cities = []
  const normalizedCoverage = coveragecity.filter((item) => item !== "'")
  for (let i = 0; i < normalizedCoverage.length; i += 3) {
    if (i + 2 < normalizedCoverage.length) {
      const cityName = String(normalizedCoverage[i + 2]).replace(/['[\]]/g, '').trim()
      if (cityName) {
        cities.push(cityName)
      }
    }
  }

  const displayName = properties.ChineseName || getChinesePopName(properties.Name)
  const sections = [
    renderSection('节点概览', [
      renderRow('PoP 名称', `<strong style="font-size:15px;color:#0f172a;">${escapeHtml(displayName)}</strong>`),
      ...(properties.Name && properties.Name !== displayName
        ? [renderRow('原始标识', renderCode(properties.Name))]
        : []),
      ...(properties.datacenter
        ? [renderRow('数据中心', escapeHtml(properties.datacenter))]
        : []),
    ], 'primary'),
    renderSection('地理与网络', [
      renderRow('地理坐标', coordinates.length === 2
        ? `<span style="font-family:ui-monospace,SFMono-Regular,monospace;">${formatCoordinate(coordinates[1])}, ${formatCoordinate(coordinates[0])}</span>`
        : '-'),
      ...(properties.location
        ? [renderRow('物理位置', escapeHtml(properties.location))]
        : []),
      ...(properties.cllicode
        ? [renderRow('CLLI 编码', renderCode(String(properties.cllicode).toUpperCase(), '#0f766e'))]
        : []),
      ...(properties.dnsname
        ? [renderRow('DNS 服务', renderCode(properties.dnsname, '#334155'))]
        : []),
    ], 'success'),
  ]

  if (ixConnections.length > 0 || cities.length > 0) {
    sections.push(
      renderSection('覆盖能力', [
        ...(ixConnections.length > 0
          ? [renderRow('IX 互联', renderTagList(ixConnections, 'success'))]
          : []),
        ...(cities.length > 0
          ? [renderRow(`覆盖城市（${cities.length}）`, renderTagList(cities.slice(0, 16), 'info'))]
          : []),
      ], 'warning'),
    )
  }

  return buildDetailRoot(sections)
}

/**
 * Format gateway detail HTML for sidebar rendering.
 * @param {Record<string, any>} properties
 * @returns {string}
 */
export function formatStarlinkGatewayDetails(properties) {
  if (!properties) return ''

  const coordinates = properties._geometry?.coordinates || []
  const displayName = getChineseGatewayName(properties.Name)
  const originalName = properties.Name || '未知地面站'
  const sections = [
    renderSection('地面站概览', [
      renderRow('地面站名称', `<strong style="font-size:15px;color:#0f172a;">${escapeHtml(displayName)}</strong>`),
      ...(displayName !== originalName
        ? [renderRow('原始标识', renderCode(originalName, '#c2410c'))]
        : []),
      ...(properties.gatewayLocation
        ? [renderRow('详细位置', escapeHtml(properties.gatewayLocation))]
        : []),
      ...(properties.status
        ? [renderRow('建设状态', renderPill(properties.status, 'warning'))]
        : []),
    ], 'primary'),
    renderSection('运行信息', [
      renderRow(
        '运营状态',
        `
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            ${renderPill(properties.kaOperational ? 'Ka 频段运营中' : 'Ka 频段未运营', properties.kaOperational ? 'success' : 'danger')}
            ${renderPill(properties.eOperational ? 'E 频段运营中' : 'E 频段未运营', properties.eOperational ? 'success' : 'danger')}
          </div>
        `,
      ),
      ...(properties.kaAntennaCount || properties.eAntennaCount
        ? [renderRow(
          '天线数量',
          `
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
              ${properties.kaAntennaCount ? renderPill(`Ka × ${properties.kaAntennaCount}`, 'info') : ''}
              ${properties.eAntennaCount ? renderPill(`E × ${properties.eAntennaCount}`, 'info') : ''}
            </div>
          `,
        )]
        : []),
      ...(properties.freq
        ? [renderRow('工作频率', renderCode(properties.freq, '#c2410c'))]
        : []),
    ], 'success'),
    renderSection('地理信息', [
      renderRow('地理坐标', coordinates.length === 2
        ? `<span style="font-family:ui-monospace,SFMono-Regular,monospace;">${formatCoordinate(coordinates[1])}, ${formatCoordinate(coordinates[0])}</span>`
        : '-'),
      ...(properties.notes
        ? [renderRow('备注信息', escapeHtml(properties.notes))]
        : []),
    ], 'warning'),
  ]

  return buildDetailRoot(sections)
}

export const buildStarlinkSatelliteTooltipElement = (satellite) => {
  const root = document.createElement('div')
  root.className = 'heatmap-info'

  const lat = toSafeNumber(satellite?.latitude)
  const lng = toSafeNumber(satellite?.longitude)
  const hasPosition = lat !== null && lng !== null

  const row = (labelText, valueText, highlight = false, countMode = false) => {
    const item = document.createElement('div')
    item.className = highlight ? 'info-row highlight' : 'info-row'

    const label = document.createElement('span')
    label.className = 'info-label'
    label.textContent = labelText

    const value = document.createElement('span')
    value.className = countMode ? 'info-value count' : 'info-value'
    value.textContent = valueText

    item.appendChild(label)
    item.appendChild(value)
    return item
  }

  root.appendChild(row('卫星名称', satellite?.name || 'UNKNOWN', true))
  root.appendChild(row('NORAD', String(satellite?.norad_cat_id || '-')))
  root.appendChild(row('当前坐标', hasPosition ? `${lat.toFixed(2)}, ${lng.toFixed(2)}` : '-, -'))
  root.appendChild(row('速度', satellite?.velocity_kms == null ? '-' : `${Number(satellite.velocity_kms).toFixed(2)} km/s`))
  root.appendChild(row('更新时间', formatDisplayTime(satellite?.metadata_fetched_at), false, false))

  return root
}

export const formatStarlinkSatelliteDetails = (satellite) => {
  if (!satellite) return ''

  const hasPosition = toSafeNumber(satellite.latitude) !== null && toSafeNumber(satellite.longitude) !== null
  const sections = [
    renderSection('卫星概览', [
      renderRow('卫星名称', `<strong style="font-size:15px;color:#0f172a;">${escapeHtml(satellite.name || satellite.object_name || '未知卫星')}</strong>`),
      renderRow('NORAD', renderCode(satellite.norad_cat_id || '-', '#1d4ed8')),
      ...(satellite.object_name
        ? [renderRow('对象名称', escapeHtml(satellite.object_name))]
        : []),
      ...(satellite.launch
        ? [renderRow('发射批次', escapeHtml(satellite.launch))]
        : []),
      ...(satellite.version
        ? [renderRow('版本信息', escapeHtml(satellite.version))]
        : []),
    ], 'primary'),
    renderSection('轨道状态', [
      renderRow('轨道高度', formatMetric(satellite.height_km, 2, ' km')),
      renderRow('运行速度', formatMetric(satellite.velocity_kms, 4, ' km/s')),
      renderRow(
        '当前坐标',
        hasPosition
          ? `<span style="font-family:ui-monospace,SFMono-Regular,monospace;">${formatCoordinate(satellite.latitude)}, ${formatCoordinate(satellite.longitude)}</span>`
          : '-',
      ),
      renderRow('位置状态', renderPill(hasPosition ? '可定位' : '位置缺失', hasPosition ? 'success' : 'warning')),
    ], 'success'),
    renderSection('数据来源', [
      renderRow('元数据来源', escapeHtml(satellite.metadata_source || '-')),
      renderRow('轨道来源', escapeHtml(satellite.orbit_source || '-')),
      renderRow('更新时间', formatDisplayTime(satellite.metadata_fetched_at)),
    ], 'warning'),
  ]

  return buildDetailRoot(sections)
}
