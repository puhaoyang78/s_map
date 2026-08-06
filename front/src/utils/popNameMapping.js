/**
 * Starlink PoP点名称中英文映射表
 * 支持多种查找方式：完整名称、CLLI Code、机场代码
 */

// CLLI Code 到中文名称的映射（小写键）
export const clliCodeToChinese = {
  'aklnzl1': '奥克兰 PoP',
  'ashnvax2': '阿什本/华盛顿特区 PoP',
  'atlagax1': '亚特兰大 PoP',
  'bgtacol1': '波哥大 PoP',
  'bnssarg1': '布宜诺斯艾利斯 PoP',
  'brsabra1': '巴西利亚 PoP',
  'brseaus1': '布里斯班 PoP',
  'chcoilx1': '芝加哥 PoP',
  'chrhnzl1': '基督城 PoP',
  'clgycan1': '卡尔加里 PoP',
  'dhkabgd1': '达卡 PoP',
  'dllstxx1': '达拉斯 PoP',
  'dnvrcox1': '丹佛 PoP',
  'dohaqat1': '多哈 PoP',
  'frntdeu1': '法兰克福 PoP',
  'frtabra1': '福塔莱萨 PoP',
  'gtmygtm1': '危地马拉城 PoP',
  'jhngzaf1': '约翰内斯堡 PoP',
  'jtnaidn1': '雅加达 PoP',
  'kscymox1': '堪萨斯城 PoP',
  'lgosnga1': '拉各斯 PoP',
  'limaper1': '利马 PoP',
  'lndngbr1': '伦敦 PoP',
  'lsancax1': '洛杉矶 PoP',
  'mdrdesp1': '马德里 PoP',
  'mlbeaus1': '墨尔本 PoP',
  'mlnnita1': '米兰 PoP',
  'mmbiind1': '孟买 PoP',
  'mmmiflx1': '迈阿密 PoP',
  'mnlaph1': '马尼拉 PoP',
  'mntlcan1': '蒙特利尔 PoP',
  'mplsmnx1': '明尼阿波利斯 PoP',
  'msctom1': '马斯喀特 PoP',
  'nrbiken1': '内罗毕 PoP',
  'nwyynyx1': '纽约 PoP',
  'prthau1': '珀斯 PoP',
  'qrtomex1': '克雷塔罗/墨西哥城 PoP',
  'sfiabgr1': '索非亚 PoP',
  'sltyutx1': '盐湖城 PoP',
  'sngesgp1': '新加坡 PoP',
  'snjecax1': '圣何塞/旧金山 PoP',
  'sntochl1': '圣地亚哥 PoP',
  'splobra1': '圣保罗 PoP',
  'srbaind2': '苏腊巴亚 PoP',
  'sttlwax1': '西雅图 PoP',
  'sydyaus1': '悉尼 PoP',
  'tkyojpn1': '东京 PoP',
  'tmpeazx1': '坦佩/凤凰城 PoP',
  'wrswpol1': '华沙 PoP'
};

// 完整名称到中文的映射（GeoJSON Name 字段）
export const popNameToChinese = {
  // 北美洲
  "SEA - STTLWAX1": "西雅图 PoP",
  "ORD/CHI - CHCOILX1": "芝加哥 PoP",
  "DEN - DNVRCOX1": "丹佛 PoP",
  "LAX - LSANCAX1": "洛杉矶 PoP",
  "LGA/NYC - NWYYNYX1": "纽约 PoP",
  "ATL - ATLAGAX1": "亚特兰大 PoP",
  "DFW/DAL - DLLSTXX1": "达拉斯 PoP",
  "MSP - MPLSMNX1": "明尼阿波利斯 PoP",
  "IAD/WAS - ASHNVAX2": "阿什本/华盛顿特区 PoP",
  "MIA - MMMIFLX1": "迈阿密 PoP",
  "PHX - TMPEAZX1": "坦佩/凤凰城 PoP",
  "SJC/SFO - SNJECAX1": "圣何塞/旧金山 PoP",
  "SLC - SLTYUTX1": "盐湖城 PoP",
  "SLC2 - SLTYUTX1": "盐湖城 PoP",
  "MCI - KSCYMOX1": "堪萨斯城 PoP",
  "YYC - CLGYCAN1": "卡尔加里 PoP",
  "MTR - MNTLCAN1": "蒙特利尔 PoP",
  
  // 拉丁美洲
  "QRO/MEX - QRTOMEX1": "克雷塔罗/墨西哥城 PoP",
  "GUA - GTMYGTM1": "危地马拉城 PoP",
  "BOG - BGTACOL1": "波哥大 PoP",
  "LIM - LIMAPER1": "利马 PoP",
  "SCL - SNTOCHL1": "圣地亚哥 PoP",
  "GRU - SPLOBRA1": "圣保罗 PoP",
  "FOR - FRTABRA1": "福塔莱萨 PoP",
  "BSB - BRSABRA1": "巴西利亚 PoP",
  "EZE - BNSSARG1": "布宜诺斯艾利斯 PoP",
  
  // 欧洲
  "FRA - FRNTDEU1": "法兰克福 PoP",
  "MAD - MDRDESP1": "马德里 PoP",
  "LON/LHR - LNDNGBR1": "伦敦 PoP",
  "SOF - SFIABGR1": "索非亚 PoP",
  "WAW - WRSWPOL1": "华沙 PoP",
  "MXP - MLNNITA1": "米兰 PoP",
  
  // 亚洲
  "TYO/NRT - TKYOJPN1": "东京 PoP",
  "SIN - SNGESGP1": "新加坡 PoP",
  "CGK - JTNAIDN1": "雅加达 PoP",
  "SUB - SRBAIND2": "苏腊巴亚 PoP",
  "MNL - MNLAPH1": "马尼拉 PoP",
  "BOM - MMBIIND1": "孟买 PoP",
  "DAC - DHKABGD1": "达卡 PoP",
  
  // 中东
  "DOH - DOHAQAT1": "多哈 PoP",
  "MCT - MSCTOM1": "马斯喀特 PoP",
  
  // 非洲
  "LOS - LGOSNGA1": "拉各斯 PoP",
  "NBO - NRBIKEN1": "内罗毕 PoP",
  "JNB - JHNGZAF1": "约翰内斯堡 PoP",
  
  // 大洋洲
  "SYD - SYDYAUS1": "悉尼 PoP",
  "MEL - MLBEAUS1": "墨尔本 PoP",
  "BNE - BRSEAUS1": "布里斯班 PoP",
  "PER - PRTHAU1": "珀斯 PoP",
  "AKL - AKLNZL1": "奥克兰 PoP",
  "CHC - CHRHNZL1": "基督城 PoP",
  
  // 特殊/计划中
  "HNL": "檀香山 PoP",
  "Guam": "关岛 PoP",
  "Suva": "斐济 PoP"
};

/**
 * 获取PoP点的中文名称
 * 支持多种输入格式：完整名称、CLLI Code
 * @param {string} name - PoP点的名称或 CLLI Code
 * @returns {string} - 对应的中文名称，如果没有映射则返回原始名称
 */
export function getChinesePopName(name) {
  if (!name) return '';
  
  // 1. 先尝试完整名称匹配
  if (popNameToChinese[name]) {
    return popNameToChinese[name];
  }
  
  // 2. 清理名称（去除换行符等）
  const cleanName = name.replace(/\n/g, '').trim();
  if (popNameToChinese[cleanName]) {
    return popNameToChinese[cleanName];
  }
  
  // 3. 尝试从名称中提取 CLLI Code 并查找
  const clliMatch = cleanName.match(/([A-Z]{4,8}\d?)$/i);
  if (clliMatch) {
    const clliCode = clliMatch[1].toLowerCase();
    if (clliCodeToChinese[clliCode]) {
      return clliCodeToChinese[clliCode];
    }
  }
  
  // 4. 如果输入本身就是 CLLI Code
  const lowerName = name.toLowerCase();
  if (clliCodeToChinese[lowerName]) {
    return clliCodeToChinese[lowerName];
  }
  
  return name;
}

/**
 * 通过 CLLI Code 获取中文名称
 * @param {string} clliCode - CLLI 编码
 * @returns {string} - 对应的中文名称
 */
export function getChineseNameByClliCode(clliCode) {
  if (!clliCode) return '';
  return clliCodeToChinese[clliCode.toLowerCase()] || clliCode;
} 