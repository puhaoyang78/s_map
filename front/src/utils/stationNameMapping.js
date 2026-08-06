/**
 * 地面站国家/地区代码到中文名称的映射
 */
export const countryCodeToChineseName = {
  US: '美国',
  AU: '澳大利亚',
  AR: '阿根廷',
  BR: '巴西',
  CA: '加拿大',
  CL: '智利',
  CW: '库拉索',
  DO: '多米尼加',
  FJ: '斐济',
  FR: '法国',
  DE: '德国',
  IE: '爱尔兰',
  IT: '意大利',
  JP: '日本',
  LT: '立陶宛',
  MX: '墨西哥',
  NG: '尼日利亚',
  NO: '挪威',
  NZ: '新西兰',
  OM: '阿曼',
  PH: '菲律宾',
  PL: '波兰',
  PR: '波多黎各',
  PT: '葡萄牙',
  ES: '西班牙',
  TR: '土耳其',
  UK: '英国',
  GB: '英国',
};

const countryNameToChineseName = {
  argentina: '阿根廷',
  australia: '澳大利亚',
  brazil: '巴西',
  canada: '加拿大',
  chile: '智利',
  curacao: '库拉索',
  'dominican republic': '多米尼加',
  fiji: '斐济',
  france: '法国',
  germany: '德国',
  ireland: '爱尔兰',
  italy: '意大利',
  japan: '日本',
  lithuania: '立陶宛',
  mexico: '墨西哥',
  'new zealand': '新西兰',
  nigeria: '尼日利亚',
  norway: '挪威',
  oman: '阿曼',
  philippines: '菲律宾',
  poland: '波兰',
  portugal: '葡萄牙',
  'puerto rico': '波多黎各',
  spain: '西班牙',
  turkey: '土耳其',
  'united kingdom': '英国',
  'united states': '美国',
};

const normalizeCountryKey = (value) => {
  if (!value) return '';
  return String(value)
    .trim()
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

/**
 * 将国家/地区代码或英文名称转换为中文名称
 * @param {string} codeOrName 国家/地区代码或英文名称
 * @returns {string} 中文名称，如果没有对应映射则返回原值
 */
export function getChineseCountryName(codeOrName) {
  if (!codeOrName) return '未知';

  const raw = String(codeOrName).trim();
  if (!raw) return '未知';

  const byCode = countryCodeToChineseName[raw.toUpperCase()];
  if (byCode) return byCode;

  const byName = countryNameToChineseName[normalizeCountryKey(raw)];
  if (byName) return byName;

  return raw;
}
