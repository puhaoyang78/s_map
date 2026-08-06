// 鲁棒的地区匹配工具
// 处理多语言、别名、拼写差异等复杂情况

export class RegionMatcher {
  constructor() {
    // 国家名称别名映射表
    this.countryAliases = {
      // 阿拉伯联合酋长国
      '阿拉伯联合酋长国': ['United Arab Emirates', 'UAE', 'Emirates'],
      'United Arab Emirates': ['阿拉伯联合酋长国', 'UAE', 'Emirates'],
      'UAE': ['United Arab Emirates', '阿拉伯联合酋长国', 'Emirates'],
      
      // 美国
      '美国': ['United States', 'USA', 'US', 'United States of America'],
      'United States': ['美国', 'USA', 'US', 'United States of America'],
      'USA': ['United States', '美国', 'US', 'United States of America'],
      'US': ['United States', '美国', 'USA', 'United States of America'],
      
      // 英国
      '英国': ['United Kingdom', 'UK', 'Britain', 'Great Britain'],
      'United Kingdom': ['英国', 'UK', 'Britain', 'Great Britain'],
      'UK': ['United Kingdom', '英国', 'Britain', 'Great Britain'],
      
      // 中国
      '中国': ['China', 'People\'s Republic of China', 'PRC'],
      'China': ['中国', 'People\'s Republic of China', 'PRC'],
      
      // 俄罗斯
      '俄罗斯': ['Russia', 'Russian Federation'],
      'Russia': ['俄罗斯', 'Russian Federation'],
      'Russian Federation': ['俄罗斯', 'Russia'],
      
      // 德国
      '德国': ['Germany', 'Deutschland'],
      'Germany': ['德国', 'Deutschland'],
      
      // 法国
      '法国': ['France', 'République française'],
      'France': ['法国', 'République française'],
      
      // 意大利
      '意大利': ['Italy', 'Italia'],
      'Italy': ['意大利', 'Italia'],
      
      // 西班牙
      '西班牙': ['Spain', 'España'],
      'Spain': ['西班牙', 'España'],
      
      // 日本
      '日本': ['Japan', 'Nippon', 'Nihon'],
      'Japan': ['日本', 'Nippon', 'Nihon'],
      
      // 韩国
      '韩国': ['South Korea', 'Korea', 'Republic of Korea'],
      'South Korea': ['韩国', 'Korea', 'Republic of Korea'],
      'Korea': ['韩国', 'South Korea', 'Republic of Korea'],
      
      // 印度
      '印度': ['India', 'Bharat'],
      'India': ['印度', 'Bharat'],
      
      // 澳大利亚
      '澳大利亚': ['Australia', 'Commonwealth of Australia'],
      'Australia': ['澳大利亚', 'Commonwealth of Australia'],
      
      // 加拿大
      '加拿大': ['Canada'],
      'Canada': ['加拿大'],
      
      // 巴西
      '巴西': ['Brazil', 'Brasil'],
      'Brazil': ['巴西', 'Brasil'],
      
      // 英国（完整名称）
      '大不列颠及北爱尔兰联合王国': ['United Kingdom', 'UK', 'Britain', 'Great Britain', 'United Kingdom of Great Britain and Northern Ireland'],
      'United Kingdom of Great Britain and Northern Ireland': ['大不列颠及北爱尔兰联合王国', 'United Kingdom', 'UK'],
      
      // 哥斯达黎加
      '哥斯达黎加': ['Costa Rica', 'CostaRica'],
      'Costa Rica': ['哥斯达黎加', 'CostaRica'],
      'CostaRica': ['哥斯达黎加', 'Costa Rica'],
      
      // 捷克
      '捷克': ['Czechia', 'Czech Republic'],
      'Czechia': ['捷克', 'Czech Republic'],
      'Czech Republic': ['捷克', 'Czechia'],
      
      // 摩尔多瓦
      '摩尔多瓦': ['Moldova', 'Republic of Moldova', 'Moldova (the Republic of)'],
      'Moldova': ['摩尔多瓦', 'Republic of Moldova'],
      'Moldova (the Republic of)': ['摩尔多瓦', 'Moldova'],
      
      // 斯威士兰
      '斯威士兰': ['Eswatini', 'Swaziland'],
      'Eswatini': ['斯威士兰', 'Swaziland'],
      
      // 密克罗尼西亚
      '密克罗尼西亚': ['Micronesia', 'Federated States of Micronesia', 'Micronesia (Federated States of)'],
      'Micronesia': ['密克罗尼西亚', 'Federated States of Micronesia'],
      'Micronesia (Federated States of)': ['密克罗尼西亚', 'Micronesia'],
      
      // 巴哈马
      '巴哈马': ['Bahamas', 'The Bahamas', 'Bahamas (the)'],
      'Bahamas': ['巴哈马', 'The Bahamas'],
      'Bahamas (the)': ['巴哈马', 'Bahamas'],
      
      // 巴林
      '巴林': ['Bahrain', 'Kingdom of Bahrain'],
      'Bahrain': ['巴林', 'Kingdom of Bahrain'],
      
      // 美属维尔京群岛
      '美属维尔京群岛': ['Virgin Islands', 'U.S. Virgin Islands', 'Virgin Islands (U.S.)', 'United States Virgin Islands'],
      'Virgin Islands (U.S.)': ['美属维尔京群岛', 'Virgin Islands', 'United States Virgin Islands'],
      'United States Virgin Islands': ['美属维尔京群岛', 'Virgin Islands'],
      
      // 南苏丹
      '南苏丹': ['South Sudan', 'Republic of South Sudan'],
      'South Sudan': ['南苏丹', 'Republic of South Sudan'],
      
      // 北马其顿
      '北马其顿': ['North Macedonia', 'Macedonia'],
      'North Macedonia': ['北马其顿', 'Macedonia'],
      
      // 关岛
      '关岛': ['Guam'],
      'Guam': ['关岛'],
      
      // 冰岛
      '冰岛': ['Iceland'],
      'Iceland': ['冰岛'],
      
      // 卢旺达
      '卢旺达': ['Rwanda'],
      'Rwanda': ['卢旺达'],
      
      // 哥伦比亚
      '哥伦比亚': ['Colombia'],
      ' 哥伦比亚': ['Colombia'], // 带空格版本
      'Colombia': ['哥伦比亚', ' 哥伦比亚'],
      
      // 圣皮埃尔和密克隆
      '圣皮埃尔和密克隆': ['Saint Pierre and Miquelon'],
      'Saint Pierre and Miquelon': ['圣皮埃尔和密克隆'],
      
      // 圣马丁
      '圣马丁': ['Saint Martin', 'Saint Martin (French part)'],
      'Saint Martin (French part)': ['圣马丁', 'Saint Martin'],
      
      // 塞尔维亚
      '塞尔维亚': ['Serbia'],
      'Serbia': ['塞尔维亚'],
      
      // 塞拉利昂
      '塞拉利昂': ['Sierra Leone'],
      'Sierra Leone': ['塞拉利昂'],
      
      // 塞浦路斯
      '塞浦路斯': ['Cyprus'],
      'Cyprus': ['塞浦路斯'],
      
      // 墨西哥
      '墨西哥': ['Mexico'],
      'Mexico': ['墨西哥'],
      
      // 多米尼加
      '多米尼加': ['Dominican Republic', 'Dominica'],
      'Dominican Republic': ['多米尼加'],
      
      // 奥地利
      '奥地利': ['Austria'],
      'Austria': ['奥地利'],
      
      // 库克群岛
      '库克群岛': ['Cook Islands'],
      'Cook Islands': ['库克群岛'],
      
      // 斯洛伐克
      '斯洛伐克': ['Slovakia'],
      'Slovakia': ['斯洛伐克'],
      
      // 斯里兰卡
      '斯里兰卡': ['Sri Lanka'],
      'Sri Lanka': ['斯里兰卡'],
      
      // 新加坡
      '新加坡': ['Singapore'],
      'Singapore': ['新加坡'],
      
      // 格恩西岛
      '格恩西岛': ['Guernsey'],
      'Guernsey': ['格恩西岛'],
      
      // 法属圭亚那
      '法属圭亚那': ['French Guiana'],
      'French Guiana': ['法属圭亚那', 'France', '法国', 'Guyane'],

      // 马提尼克 / 马约特 / 法属圭亚那在 Admin-1 中通常归到 France
      '马提尼克': ['Martinique', 'France', '法国'],
      'Martinique': ['马提尼克', 'France', '法国'],
      '马提尼克/Martinique': ['马提尼克', 'Martinique', 'France', '法国'],
      '马约特': ['Mayotte', 'France', '法国'],
      'Mayotte': ['马约特', 'France', '法国'],
      '马约特/Mayotte': ['马约特', 'Mayotte', 'France', '法国'],
      'Guyane': ['法属圭亚那', 'French Guiana', 'France', '法国'],
      
      // 波兰
      '波兰': ['Poland'],
      'Poland': ['波兰'],
      
      // 波多黎各
      '波多黎各': ['Puerto Rico'],
      'Puerto Rico': ['波多黎各'],
      
      // 爱沙尼亚
      '爱沙尼亚': ['Estonia'],
      'Estonia': ['爱沙尼亚'],
      
      // 瑞典
      '瑞典': ['Sweden'],
      'Sweden': ['瑞典'],
      
      // 瑞士
      '瑞士': ['Switzerland'],
      'Switzerland': ['瑞士'],
      
      // 瓜德罗普
      '瓜德罗普': ['Guadeloupe', 'France'],
      'Guadeloupe': ['瓜德罗普', 'France'],
      
      // 皮特凯恩
      '皮特凯恩': ['Pitcairn'],
      'Pitcairn': ['皮特凯恩'],
      
      // 约旦
      '约旦': ['Jordan'],
      'Jordan': ['约旦'],
      
      // 罗马尼亚
      '罗马尼亚': ['Romania'],
      'Romania': ['罗马尼亚'],
      
      // 菲律宾
      '菲律宾': ['Philippines'],
      'Philippines': ['菲律宾'],
      
      // 贝宁
      '贝宁': ['Benin', 'Republic of Benin'],
      'Benin': ['贝宁', 'Republic of Benin'],
      
      // 阿塞拜疆
      '阿塞拜疆': ['Azerbaijan'],
      'Azerbaijan': ['阿塞拜疆'],
      
      // 阿尔巴尼亚
      '阿尔巴尼亚': ['Albania'],
      'Albania': ['阿尔巴尼亚'],
      
      // 马尔代夫
      '马尔代夫': ['Maldives'],
      'Maldives': ['马尔代夫'],
      
      // 马来西亚
      '马来西亚': ['Malaysia'],
      'Malaysia': ['马来西亚'],
      
      // 马达加斯加
      '马达加斯加': ['Madagascar'],
      'Madagascar': ['马达加斯加'],
      
      // 皮特凯恩
      'Pitcairn Islands': ['皮特凯恩'],
      
      // 巴林王国
            // 图瓦卢
      '图瓦卢': ['Tuvalu'],
      'Tuvalu': ['图瓦卢'],
      
      // 东帝汶 (GeoJSON中叫East Timor)
      '东帝汶': ['Timor-Leste', 'East Timor'],
      'Timor-Leste': ['东帝汶', 'East Timor'],
      'East Timor': ['东帝汶', 'Timor-Leste'],
      
      // 巴林王国
      '巴林王国': ['Bahrain', 'Kingdom of Bahrain'],
      
      // 密克罗尼西亚（联邦）
      '密克罗尼西亚（联邦）': ['Micronesia', 'Federated States of Micronesia'],
      
      // 圣马丁（法属部分）
      '圣马丁（法属部分）': ['Saint Martin', 'Saint Martin (French part)'],
      
      // 南苏丹 (GeoJSON中叫S. Sudan)
      'S. Sudan': ['南苏丹', 'South Sudan'],
      
      // 塞尔维亚 (GeoJSON中叫Republic of Serbia)
      'Republic of Serbia': ['塞尔维亚', 'Serbia'],
      'Kosovo': ['塞尔维亚'], // 科索沃在某些数据中归属塞尔维亚
      
      // 法属圭亚那(GeoJSON中叫Guyana或属于France)
      'Guyana': ['法属圭亚那', 'French Guiana'],
      
      // 马约特(属于法国,在GeoJSON中可能没有独立条目)
      
      // 可以继续添加更多国家...
    };

    // 地区名称别名映射表
    this.regionAliases = {
      // 加拿大省份
      '魁北克': ['Quebec', 'Québec'],
      'Quebec': ['魁北克', 'Québec'],
      
      // 英国
      '英国': ['England'],
      'England': ['英国'],
      
      // 冰岛
      '雷克雅未克': ['Reykjavíkurborg', 'Reykjavik', 'Capital Region'],
      'Reykjavíkurborg': ['雷克雅未克'],
      
      // 奥地利
      '维也纳': ['Vienna', 'Wien'],
      'Vienna': ['维也纳', 'Wien'],
      
      // 法国
      '法兰西岛': ['Île-de-France', 'Ile-de-France', 'Paris'],
      'Île-de-France': ['法兰西岛', 'Paris'],
      'Paris': ['法兰西岛', 'Île-de-France'], // 法兰西岛在GeoJSON中叫Paris

      // 法属海外地区
      '马提尼克': ['Martinique'],
      'Martinique': ['马提尼克'],
      '马提尼克/Martinique': ['Martinique', '马提尼克'],
      '马穆祖': ['Mamoudzou', 'Mayotte'],
      'Mamoudzou': ['马穆祖', 'Mayotte'],
      '马穆祖/Mamoudzou': ['Mayotte', 'Mamoudzou', '马穆祖'],
      '圭亚那': ['Guyane', 'French Guiana', 'Guyane française'],
      'Guyane': ['圭亚那', 'French Guiana'],
      'Guyane française': ['圭亚那'],
      
      // 意大利
      '罗马': ['Rome', 'Roma', 'Lazio'],
      'Rome': ['罗马', 'Roma'],
      'Lazio': ['罗马'],
      
      // 捷克
      '布拉格': ['Praha', 'Prague'],
      'Praha': ['布拉格', 'Prague'],
      'Prague': ['布拉格', 'Praha'],
      
      // 摩尔多瓦
      '基希讷乌': ['Chisinau', 'Chișinău', 'Municipiul Chișinău'],
      'Chisinau': ['基希讷乌'],
      
      // 斯洛伐克
      '布拉迪斯拉发': ['Bratislavsky kraj', 'Bratislava', 'Bratislavský'],
      'Bratislavsky kraj': ['布拉迪斯拉发'],
      'Bratislavský': ['布拉迪斯拉发'],
      
      // 波兰
      '马佐维耶茨': ['Mazowieckie', 'Masovian'],
      'Mazowieckie': ['马佐维耶茨'],
      
      // 瑞典
      '斯德哥尔摩': ['Stockholms lan', 'Stockholm'],
      'Stockholms lan': ['斯德哥尔摩'],
      
      // 瑞士
      '苏黎世': ['Zurich', 'Zürich'],
      'Zurich': ['苏黎世', 'Zürich'],
      
      // 罗马尼亚
      '布加勒斯特': ['Bucuresti', 'Bucharest'],
      'Bucuresti': ['布加勒斯特'],
      
      // 阿塞拜疆
      '巴库': ['Baku', 'Bakı'],
      'Baku': ['巴库'],
      
      // 阿尔巴尼亚
      '地拉那': ['Tirane', 'Tirana', 'Tiranë'],
      'Tirane': ['地拉那', 'Tirana'],
      'Tiranë': ['地拉那'],
      
      // 马达加斯加
      '塔那那利佛': ['Antananarivo', 'Analamanga'],
      'Antananarivo': ['塔那那利佛'],
      'Analamanga': ['塔那那利佛'],
      
      // 马来西亚
      '吉隆坡': ['Wilayah Persekutuan Kuala Lumpur', 'Kuala Lumpur'],
      'Wilayah Persekutuan Kuala Lumpur': ['吉隆坡'],
      
      // 菲律宾
      '国家首都地区': ['National Capital Region', 'Metro Manila', 'NCR', 'Manila'],
      'National Capital Region': ['国家首都地区'],
      'Manila': ['国家首都地区'],
      
      // 斯里兰卡
      '西部省': ['Western Province', 'Kŏḷamba', 'Colombo'],
      'Western Province': ['西部省'],
      'Kŏḷamba': ['西部省'],
      
      // 约旦
      '安曼省': ['Amman Governorate', 'Amman'],
      'Amman Governorate': ['安曼省'],
      
      // 塞浦路斯
      '尼科西亚': ['Lefkosia', 'Nicosia'],
      'Lefkosia': ['尼科西亚'],
      
      // 以色列
      '耶路撒冷': ['Yerushalayim', 'Jerusalem'],
      'Yerushalayim': ['耶路撒冷'],
      
      // 乌克兰
      '基辅': ['Kyiv', 'Kiev'],
      'Kyiv': ['基辅'],
      
      // 塞拉利昂
      '西部': ['Western Area', 'Western'],
      'Western Area': ['西部'],
      'Western': ['西部'],
      
      // 爱沙尼亚
      '哈尔尤县': ['Harjumaa', 'Harju'],
      'Harjumaa': ['哈尔尤县'],
      
      // 贝宁
      '韦梅省': ['Oueme', 'Ouémé'],
      'Oueme': ['韦梅省'],
      
      // 卢旺达
      '基加利市': ['Ville de Kigali', 'Kigali', 'Kigali City'],
      'Ville de Kigali': ['基加利市'],
      'Kigali City': ['基加利市'],
      
      // 巴西
      '塞阿拉州': ['Ceara', 'Ceará'],
      'Ceara': ['塞阿拉州'],
      
      // 关岛
      '哈加特尼亚': ['Hagatna', 'Hagåtña', 'Agana', 'Guam'],
      'Hagatna': ['哈加特尼亚'],
      'Guam': ['哈加特尼亚'], // 关岛的地区名和国家名相同
      
      // 图瓦卢
      '富纳富提': ['Funafuti', 'Tuvalu'],
      'Funafuti': ['富纳富提'],
      'Tuvalu': ['富纳富提'], // 图瓦卢的地区名和国家名相同
      
      // 密克罗尼西亚
      '波纳佩': ['Pohnpei'],
      'Pohnpei': ['波纳佩'],
      
      // 南苏丹
      '中赤道州': ['Central Equatoria'],
      'Central Equatoria': ['中赤道州'],
      
      // 哥伦比亚
      '波哥大首都区': ['Distrito Capital de Bogota', 'Bogotá', 'Distrito Capital', 'Bogota'],
      'Distrito Capital de Bogota': ['波哥大首都区'],
      'Bogota': ['波哥大首都区'],
      
      // 多米尼加
      '圣多明各': ['Distrito Nacional (Santo Domingo)', 'Santo Domingo', 'Distrito Nacional'],
      'Distrito Nacional (Santo Domingo)': ['圣多明各'],
      
      // 墨西哥 (墨西哥城不在GeoJSON的州级别中，使用Mexico州或Federal District)
      '墨西哥城': ['Ciudad de Mexico', 'Mexico City', 'Federal District', 'Distrito Federal'],
      'Ciudad de Mexico': ['墨西哥城'],
      
      // 波多黎各
      '圣胡安': ['San Juan', 'Puerto Rico'],
      'San Juan': ['圣胡安'],
      'Puerto Rico': ['圣胡安'], // 波多黎各的地区名和国家名相同
      
      // 塞尔维亚/科索沃
      '科索沃-米特罗瓦茨克州': ['Kosovsko-Mitrovacki okrug', 'Kosovska Mitrovica'],
      'Kosovsko-Mitrovacki okrug': ['科索沃-米特罗瓦茨克州'],
      'Kosovska Mitrovica': ['科索沃-米特罗瓦茨克州'],
      
      // 巴林
      '麦纳麦': ['Manama', 'Al Manāmah'],
      'Manama': ['麦纳麦'],
      'Al Manāmah': ['麦纳麦'],
      
      // 马尔代夫
      '马累': ['Male', 'Malé'],
      'Male': ['马累'],
      
      // 马约特
      'Mayotte': ['马穆祖'], // 马约特的地区名和国家名相同
      
      // 东帝汶
      '帝力': ['Dili'],
      'Dili': ['帝力'],
      
      // 瓜德罗普(在GeoJSON中属于France)
      '瓜德罗普': ['Guadeloupe'],
      'Guadeloupe': ['瓜德罗普'],
      
      // 皮特凯恩
      '皮特凯恩': ['Pitcairn', 'Pitcairn Islands'],
      'Pitcairn Islands': ['皮特凯恩'],
      
      // 美属维尔京群岛(GeoJSON中叫United States Virgin Islands,细分为Saint Croix等)
      '美属维尔京群岛': ['Virgin Islands', 'Virgin Islands (U.S.)', 'United States Virgin Islands', 'Saint Croix', 'Saint John', 'Saint Thomas'],
      'Virgin Islands': ['美属维尔京群岛'],
      'Virgin Islands (U.S.)': ['美属维尔京群岛'],
      'United States Virgin Islands': ['美属维尔京群岛'],
      'Saint Croix': ['美属维尔京群岛'],
      'Saint John': ['美属维尔京群岛'],
      'Saint Thomas': ['美属维尔京群岛'],
      
      // 圣马丁（法属部分）(GeoJSON中name是St. Martin)
      '圣马丁（法属部分）': ['Saint Martin', 'Saint Martin (French Part)', 'St. Martin'],
      'Saint Martin (French Part)': ['圣马丁（法属部分）'],
      'Saint Martin': ['圣马丁（法属部分）'],
      'St. Martin': ['圣马丁（法属部分）'],
      
      // 阿联酋地区
      '迪拜': ['Dubai', 'Dubayy', 'Dubay'],
      'Dubai': ['迪拜', 'Dubayy', 'Dubay'],
      'Dubay': ['迪拜', 'Dubai', 'Dubayy'],
      '阿布扎比': ['Abu Dhabi', 'Abu Zaby'],
      'Abu Dhabi': ['阿布扎比', 'Abu Zaby'],
      
      // 美国州名
      '加利福尼亚': ['California', 'CA', 'Calif.'],
      'California': ['加利福尼亚', 'CA', 'Calif.'],
      '纽约': ['New York', 'NY', 'N.Y.'],
      'New York': ['纽约', 'NY', 'N.Y.'],
      '德克萨斯': ['Texas', 'TX', 'Tex.'],
      'Texas': ['德克萨斯', 'TX', 'Tex.'],
      
      // 中国省份
      '北京': ['Beijing', 'Peking'],
      'Beijing': ['北京', 'Peking'],
      '上海': ['Shanghai'],
      'Shanghai': ['上海'],
      '广东': ['Guangdong', 'Canton'],
      'Guangdong': ['广东', 'Canton'],
      '浙江': ['Zhejiang'],
      'Zhejiang': ['浙江'],
      '江苏': ['Jiangsu'],
      'Jiangsu': ['江苏'],
      
      // 德国州名
      '巴伐利亚': ['Bavaria', 'Bayern'],
      'Bavaria': ['巴伐利亚', 'Bayern'],
      
      // 英国地区
      '英格兰': ['England'],
      '苏格兰': ['Scotland'],
      'Scotland': ['苏格兰'],
      
      // 可以继续添加更多地区...
    };

    // 城市名称别名映射表
    this.cityAliases = {
      // 阿联酋城市
      '迪拜': ['Dubai', 'Dubayy'],
      'Dubai': ['迪拜', 'Dubayy'],
      '阿布扎比': ['Abu Dhabi', 'Abu Zaby'],
      'Abu Dhabi': ['阿布扎比', 'Abu Zaby'],
      
      // 中国城市
      '北京': ['Beijing', 'Peking'],
      'Beijing': ['北京', 'Peking'],
      '上海': ['Shanghai'],
      'Shanghai': ['上海'],
      '深圳': ['Shenzhen'],
      'Shenzhen': ['深圳'],
      '广州': ['Guangzhou', 'Canton'],
      'Guangzhou': ['广州', 'Canton'],
      
      // 美国城市
      '纽约': ['New York', 'NYC', 'New York City'],
      'New York': ['纽约', 'NYC', 'New York City'],
      '洛杉矶': ['Los Angeles', 'LA', 'L.A.'],
      'Los Angeles': ['洛杉矶', 'LA', 'L.A.'],
      
      // 可以继续添加更多城市...
    };
  }

  /**
   * 规范化名称 - 移除常见的后缀和特殊字符
   */
  normalizeName(name) {
    if (!name) return '';

    return name
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '') // 去除重音符号，提升跨语言匹配稳定性
      .trim()
      .replace(/[’']/g, '') // 统一撇号差异
      .replace(/[-_]/g, ' ') // 统一连字符差异
      .replace(/[.]/g, '') // 移除句号
      .replace(/\s+/g, ' ') // 规范化空格
      .replace(/(省|州|市|县|区|特别行政区|自治区|维吾尔自治区|回族自治区|壮族自治区)$/g, '') // 移除中文后缀
      .replace(/(Province|State|Prefecture|County|District|Region|Territory|Commonwealth)$/gi, '') // 移除英文后缀
      .trim();
  }

  /**
   * 拆分双语名称 (如 "阿拉伯联合酋长国/United Arab Emirates")
   */
  splitBilingualName(name) {
    if (!name) return { primary: '', secondary: '' };
    
    const parts = name.split('/');
    if (parts.length >= 2) {
      return {
        primary: parts[0].trim(),
        secondary: parts[1].trim()
      };
    }
    
    return {
      primary: name.trim(),
      secondary: ''
    };
  }

  /**
   * 获取名称的所有可能别名
   */
  getAliases(name, type = 'country') {
    const aliases = new Set();
    
    // 添加原始名称
    aliases.add(name);
    aliases.add(this.normalizeName(name));
    
    // 根据类型选择对应的别名表
    let aliasMap;
    switch (type) {
      case 'country':
        aliasMap = this.countryAliases;
        break;
      case 'region':
        aliasMap = this.regionAliases;
        break;
      case 'city':
        aliasMap = this.cityAliases;
        break;
      default:
        aliasMap = {};
    }
    
    // 查找直接匹配的别名
    if (aliasMap[name]) {
      aliasMap[name].forEach(alias => aliases.add(alias));
    }
    
    // 查找规范化名称的别名
    const normalizedName = this.normalizeName(name);
    if (aliasMap[normalizedName]) {
      aliasMap[normalizedName].forEach(alias => aliases.add(alias));
    }
    
    // 如果是双语名称，分别处理两部分
    const { primary, secondary } = this.splitBilingualName(name);
    if (secondary) {
      if (aliasMap[primary]) {
        aliasMap[primary].forEach(alias => aliases.add(alias));
      }
      if (aliasMap[secondary]) {
        aliasMap[secondary].forEach(alias => aliases.add(alias));
      }
    }
    
    return Array.from(aliases);
  }

  /**
   * 模糊匹配两个名称
   */
  fuzzyMatch(name1, name2, threshold = 0.8) {
    if (!name1 || !name2) return false;
    
    // 计算 Levenshtein 距离
    const calculateDistance = (str1, str2) => {
      const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(null));
      
      for (let i = 0; i <= str1.length; i++) matrix[0][i] = i;
      for (let j = 0; j <= str2.length; j++) matrix[j][0] = j;
      
      for (let j = 1; j <= str2.length; j++) {
        for (let i = 1; i <= str1.length; i++) {
          const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
          matrix[j][i] = Math.min(
            matrix[j][i - 1] + 1,     // deletion
            matrix[j - 1][i] + 1,     // insertion
            matrix[j - 1][i - 1] + indicator // substitution
          );
        }
      }
      
      return matrix[str2.length][str1.length];
    };
    
    const distance = calculateDistance(name1.toLowerCase(), name2.toLowerCase());
    const maxLength = Math.max(name1.length, name2.length);
    const similarity = 1 - distance / maxLength;
    
    return similarity >= threshold;
  }

  /**
   * 智能匹配地区名称
   */
  matchRegion(dataRegion, boundaryRegions, type = 'region') {
    if (!dataRegion || !boundaryRegions) return null;
    
    // 1. 首先尝试精确匹配
    for (const boundaryRegion of boundaryRegions) {
      if (dataRegion === boundaryRegion.name) {
        return boundaryRegion;
      }
    }
    
    // 2. 尝试规范化后的精确匹配
    const normalizedDataRegion = this.normalizeName(dataRegion);
    for (const boundaryRegion of boundaryRegions) {
      const normalizedBoundaryName = this.normalizeName(boundaryRegion.name);
      if (normalizedDataRegion === normalizedBoundaryName) {
        return boundaryRegion;
      }
    }
    
    // 3. 尝试双语名称匹配
    const { primary, secondary } = this.splitBilingualName(dataRegion);
    if (secondary) {
      for (const boundaryRegion of boundaryRegions) {
        if (primary === boundaryRegion.name || secondary === boundaryRegion.name) {
          return boundaryRegion;
        }
        
        const normalizedBoundaryName = this.normalizeName(boundaryRegion.name);
        if (this.normalizeName(primary) === normalizedBoundaryName || 
            this.normalizeName(secondary) === normalizedBoundaryName) {
          return boundaryRegion;
        }
      }
    }
    
    // 4. 尝试别名匹配
    const aliases = this.getAliases(dataRegion, type);
    for (const alias of aliases) {
      for (const boundaryRegion of boundaryRegions) {
        if (alias === boundaryRegion.name || 
            this.normalizeName(alias) === this.normalizeName(boundaryRegion.name)) {
          return boundaryRegion;
        }
      }
    }
    
    // 5. 最后尝试模糊匹配
    for (const boundaryRegion of boundaryRegions) {
      if (this.fuzzyMatch(dataRegion, boundaryRegion.name, 0.85)) {
        return boundaryRegion;
      }
      
      // 对双语名称的各部分也进行模糊匹配
      if (secondary) {
        if (this.fuzzyMatch(primary, boundaryRegion.name, 0.85) || 
            this.fuzzyMatch(secondary, boundaryRegion.name, 0.85)) {
          return boundaryRegion;
        }
      }
    }
    
    return null;
  }

  /**
   * 批量匹配地区数据
   */
  batchMatchRegions(regionCounts, boundaryData) {
    const matchedData = {};
    const unmatchedRegions = [];
    
    // 验证输入数据
    if (!regionCounts || typeof regionCounts !== 'object') {
      console.error('regionCounts 数据无效');
      return { matched: {}, unmatched: [] };
    }
    
    if (!boundaryData || !boundaryData.features || !Array.isArray(boundaryData.features)) {
      console.error('boundaryData 数据无效');
      return { matched: {}, unmatched: Object.values(regionCounts) };
    }
    
    // 预处理边界数据，按国家分组
    const boundaryByCountry = {};
    boundaryData.features.forEach(feature => {
      const country = feature.properties.admin;
      const region = {
        name: feature.properties.name,
        feature: feature
      };
      
      if (!boundaryByCountry[country]) {
        boundaryByCountry[country] = [];
      }
      boundaryByCountry[country].push(region);
      
      // 也为国家的所有别名建立映射
      const countryAliases = this.getAliases(country, 'country');
      countryAliases.forEach(alias => {
        if (!boundaryByCountry[alias]) {
          boundaryByCountry[alias] = [];
        }
        if (!boundaryByCountry[alias].includes(region)) {
          boundaryByCountry[alias].push(region);
        }
      });
    });
    
    // 匹配每个地区
    Object.values(regionCounts).forEach(item => {
      const { primary: countryPrimary, secondary: countrySecondary } = this.splitBilingualName(item.country);
      const { primary: regionPrimary, secondary: regionSecondary } = this.splitBilingualName(item.region);
      
      let matchedRegion = null;
      
      // 尝试用主要国家名匹配
      const possibleCountries = [
        countryPrimary,
        countrySecondary,
        item.country,
        ...this.getAliases(item.country, 'country')
      ].filter(Boolean);
      
      for (const country of possibleCountries) {
        if (boundaryByCountry[country]) {
          const possibleRegions = [
            regionPrimary,
            regionSecondary,
            item.region,
            ...this.getAliases(item.region, 'region'),
            ...this.getAliases(regionPrimary, 'region'),
            ...this.getAliases(regionSecondary, 'region')
          ].filter(Boolean);
          
          for (const region of possibleRegions) {
            matchedRegion = this.matchRegion(region, boundaryByCountry[country], 'region');
            if (matchedRegion) break;
          }
          
          // 如果地区名等于国家名，或者地区名为空/未知，使用该国家的第一个地区
          if (!matchedRegion) {
            const normalizedRegion = this.normalizeName(regionPrimary || regionSecondary || item.region);
            const normalizedCountry = this.normalizeName(country);
            
            // 特殊情况:Virgin Islands (U.S.) 地区名等于国家名
            const regionWithoutParens = normalizedRegion.replace(/\(.*?\)/g, '').trim();
            const countryWithoutParens = normalizedCountry.replace(/\(.*?\)/g, '').trim();
            
            if (!normalizedRegion || 
                normalizedRegion === normalizedCountry || 
                regionWithoutParens === countryWithoutParens ||
                normalizedRegion === '未知' || 
                normalizedRegion === 'unknown' ||
                normalizedRegion === '-' ||
                normalizedRegion === 'england' || // 英国特殊情况
                normalizedRegion === '英国' || // 中文
                normalizedRegion === 'scotland' ||
                normalizedRegion === '苏格兰' ||
                normalizedRegion === 'wales' ||
                normalizedRegion === '威尔士' ||
                normalizedRegion === 'northern ireland' ||
                normalizedRegion === '北爱尔兰') {
              // 使用该国家的第一个可用地区
              if (boundaryByCountry[country] && boundaryByCountry[country].length > 0) {
                matchedRegion = boundaryByCountry[country][0];
              }
            }
          }
          
          if (matchedRegion) break;
        }
      }
      
      if (matchedRegion) {
        const key = `${matchedRegion.feature.properties.admin}-${matchedRegion.feature.properties.name}`;
        if (!matchedData[key]) {
          matchedData[key] = {
            count: 0,
            feature: matchedRegion.feature,
            originalData: []
          };
        }
        matchedData[key].count += item.count || 0;
        matchedData[key].originalData.push(item);
      } else {
        unmatchedRegions.push(item);
      }
    });
    
    return {
      matched: matchedData,
      unmatched: unmatchedRegions
    };
  }

  /**
   * 生成匹配报告
   */
  generateMatchReport(regionCounts, boundaryData) {
    try {
      return this.batchMatchRegions(regionCounts, boundaryData);
    } catch (error) {
      console.error('生成匹配报告时出错:', error);
      return {
        matched: {},
        unmatched: Object.values(regionCounts || {})
      };
    }
  }
}

// 导出单例实例
export const regionMatcher = new RegionMatcher();
