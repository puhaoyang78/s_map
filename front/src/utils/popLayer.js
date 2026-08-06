/**
 * Starlink PoP 点、Gateway（地面站）和连线渲染模块
 * 负责加载和渲染 Starlink 数据到地图上
 * 
 * 数据来源：
 * 1. GeoJSON 文件 - 主要坐标和基本信息来源
 * 2. pop.json - PoP 详细信息（中文名称、覆盖城市等）
 * 3. pops.txt - 网段信息（IP/CIDR 到 CLLI code 的映射）
 * 4. gateway.json - Gateway 地面站状态信息（来自 StarlinkInsider.com）
 */


// 加载 PoP 详细信息数据 (pop.json)
export const loadPopDetailData = async () => {
  try {
    const response = await fetch('/data/pop.json');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('加载 PoP 详细信息数据失败:', error);
    return null;
  }
};

// 加载 Gateway 状态数据 (gateway.json)
export const loadGatewayData = async () => {
  try {
    const response = await fetch('/data/gateway.json');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('加载 Gateway 数据失败:', error);
    return null;
  }
};

// 加载网段信息数据 (pops.txt)
export const loadNetworkSegmentData = async () => {
  try {
    const response = await fetch('/data/pops.txt');
    const text = await response.text();
    
    // 解析 pops.txt 文件
    // 格式: IP/CIDR,cllicode,airport_code
    const lines = text.trim().split('\n');
    const networkMap = {}; // cllicode -> [网段列表]
    
    lines.forEach(line => {
      const parts = line.trim().split(',');
      if (parts.length >= 2) {
        const cidr = parts[0];
        const cllicode = parts[1].toLowerCase();
        
        if (!networkMap[cllicode]) {
          networkMap[cllicode] = [];
        }
        networkMap[cllicode].push(cidr);
      }
    });
    
    return networkMap;
  } catch (error) {
    console.error('加载网段信息数据失败:', error);
    return {};
  }
};

// 加载 SVG 作为图像
export const loadSVGAsImage = (map, url, imageName) => {
  return fetch(url)
    .then(res => res.text())
    .then(svg => new Promise((resolve, reject) => {
      const img = new Image();
      const svg64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width; canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        map.addImage(imageName, ctx.getImageData(0, 0, img.width, img.height));
        resolve();
      };
      img.onerror = reject;
      img.src = svg64;
    }));
};

// 加载 Starlink GeoJSON 数据
export const loadStarlinkData = async () => {
  try {
    const response = await fetch('/data/Unofficial Starlink Global Gateways & PoPs.geojson');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('加载 Starlink 数据失败:', error);
    return null;
  }
};

import { buildRenderedGatewayFeatures } from './starlinkGatewayData';
import { buildRenderedPopFeatures } from './starlinkRenderedData';

// 检查连线是否跨越日期线
function crossesDateLine(coordinates) {
  for (let i = 0; i < coordinates.length - 1; i++) {
    const lng1 = coordinates[i][0];
    const lng2 = coordinates[i + 1][0];
    
    // 如果经度差超过180度，则认为跨越了日期线
    if (Math.abs(lng1 - lng2) > 180) {
      return true;
    }
  }
  return false;
}

// 检查是否为东京-西雅图线路
function isTokyoSeattleLine(feature) {
  if (feature.properties && feature.properties.Name) {
    return feature.properties.Name === "SEA <-> NRT";
  }
  return false;
}

// 处理跨越日期线的线段
function processDateLineCrossing(features) {
  const processedFeatures = [];
  
  features.forEach(feature => {
    if (feature.geometry.type !== 'LineString') {
      processedFeatures.push(feature);
      return;
    }
    
    // 特殊处理东京-西雅图线路
    if (isTokyoSeattleLine(feature)) {
      // 提取东京和西雅图的坐标（第一个和最后一个点）
      const tokyo = [139.70058130000001, 35.6409689, 0.0]; // 东京坐标
      const seattle = [-122.3386777, 47.6144489, 0.0]; // 西雅图坐标
      
      // 创建两条线段，通过太平洋连接（而非跨大陆）
      // 第一条：从东京到日期线
      const tokyoToDateLine = {
        type: 'Feature',
        properties: feature.properties,
        geometry: {
          type: 'LineString',
          coordinates: [
            tokyo,
            [180, 40, 0.0] // 日期线上的一点（调整纬度使其在太平洋中部）
          ]
        }
      };
      
      // 第二条：从日期线到西雅图
      const dateLineToSeattle = {
        type: 'Feature',
        properties: feature.properties,
        geometry: {
          type: 'LineString',
          coordinates: [
            [-180, 40, 0.0], // 日期线另一侧对应的点
            seattle
          ]
        }
      };
      
      processedFeatures.push(tokyoToDateLine);
      processedFeatures.push(dateLineToSeattle);
      return;
    }
    
    const coordinates = feature.geometry.coordinates;
    
    if (!crossesDateLine(coordinates)) {
      // 不跨越日期线，直接使用原始特征
      processedFeatures.push(feature);
      return;
    }
    
    // 跨越日期线，需要分割线段
    const newCoordinates = [];
    
    for (let i = 0; i < coordinates.length - 1; i++) {
      const start = coordinates[i];
      const end = coordinates[i + 1];
      
      // 检查这段线是否跨越日期线
      if (Math.abs(start[0] - end[0]) > 180) {
        // 确定哪个点在日期线东侧（正值大）
        let eastPoint, westPoint;
        let isStartEast = false;
        
        if (start[0] > 0 && end[0] < 0) {
          // 从东向西跨越日期线
          eastPoint = start;
          westPoint = end;
          isStartEast = true;
        } else {
          // 从西向东跨越日期线
          eastPoint = end;
          westPoint = start;
        }
        
        // 计算日期线上的交点（使用纬度的中间值）
        const crossLat = (eastPoint[1] + westPoint[1]) / 2;
        
        // 创建两个新的特征，一个从起点到日期线，一个从日期线到终点
        const crossingFeature1 = {
          type: 'Feature',
          properties: feature.properties,
          geometry: {
            type: 'LineString',
            coordinates: isStartEast ? [[start[0], start[1], start[2]], [180, crossLat, 0]] : [[start[0], start[1], start[2]], [-180, crossLat, 0]]
          }
        };
        
        const crossingFeature2 = {
          type: 'Feature',
          properties: feature.properties,
          geometry: {
            type: 'LineString',
            coordinates: isStartEast ? [[-180, crossLat, 0], [end[0], end[1], end[2]]] : [[180, crossLat, 0], [end[0], end[1], end[2]]]
          }
        };
        
        processedFeatures.push(crossingFeature1);
        processedFeatures.push(crossingFeature2);
      } else {
        // 不跨越日期线的线段正常添加
        if (newCoordinates.length === 0 || newCoordinates[newCoordinates.length - 1][0] !== start[0] || newCoordinates[newCoordinates.length - 1][1] !== start[1]) {
          newCoordinates.push(start);
        }
        if (i === coordinates.length - 2) {
          newCoordinates.push(end);
        }
      }
    }
    
    if (newCoordinates.length > 0) {
      processedFeatures.push({
        type: 'Feature',
        properties: feature.properties,
        geometry: {
          type: 'LineString',
          coordinates: newCoordinates
        }
      });
    }
  });
  
  return processedFeatures;
}

// 修改 addPopLayer 函数中的代码
export const addPopLayer = async (map, _openSidebar) => {
  try {
    // 加载图标
    await loadSVGAsImage(map, '/icons/pop.svg', 'pop-icon');
    // 尝试加载 Gateway 图标（如果存在）
    try {
      await loadSVGAsImage(map, '/icons/gateway.svg', 'gateway-icon');
    } catch {
      // Gateway 图标缺失时使用默认样式。
    }
    
    // 并行加载所有数据
    const [starlinkData, popDetailData, networkSegmentData, gatewayData] = await Promise.all([
      loadStarlinkData(),
      loadPopDetailData(),
      loadNetworkSegmentData(),
      loadGatewayData()
    ]);
    
    if (!starlinkData) {
      throw new Error('无法加载 Starlink 数据');
    }
    
    // 分离 LineString 特征
    const lineFeatures = starlinkData.features.filter((f) => f.geometry.type === 'LineString');

    const {
      gatewayFeatures,
      missingGatewayNames,
      mergedGatewayNames,
    } = await buildRenderedGatewayFeatures({
      starlinkData,
      gatewayData,
    });

    if (mergedGatewayNames.length > 0) {
      const sample = mergedGatewayNames.slice(0, 6).join(' | ');
      console.info(
        `有 ${mergedGatewayNames.length} 个 Gateway 因同名或同坐标重复被合并，已跳过渲染。示例: ${sample}`
      );
    }

    if (missingGatewayNames.length > 0) {
      const sample = missingGatewayNames.slice(0, 6).join(' | ');
      console.warn(
        `有 ${missingGatewayNames.length} 个 Gateway 在 GeoJSON 中未找到坐标，已跳过渲染。示例: ${sample}`
      );
    }

    const {
      features: popFeatures,
      summary: popSummary,
    } = await buildRenderedPopFeatures({
      starlinkData,
      popDetailData,
      networkSegmentData,
      skipSLC2: true,
    });

    if (popSummary?.skipped?.length > 0) {
      console.info(
        `PoP 构造阶段跳过 ${popSummary.skipped.length} 个特殊点: ${popSummary.skipped.join(' | ')}`
      );
    }

      // 创建坐标索引集合用于识别连线类型（基于坐标匹配）
    // 辅助函数：将坐标转换为可比较的字符串键（保留6位小数精度）
    const roundCoord = (coord) => {
      const lon = Math.round(coord[0] * 1000000) / 1000000;
      const lat = Math.round(coord[1] * 1000000) / 1000000;
      return `${lon},${lat}`;
    };
    
    // 建立 PoP 和 Gateway 坐标集合
    const popCoordsSet = new Set();
    const gatewayCoordsSet = new Set();
    
    popFeatures.forEach(f => {
      const coords = f.geometry?.coordinates;
      if (coords) {
        popCoordsSet.add(roundCoord(coords));
      }
    });
    
    gatewayFeatures.forEach(f => {
      const coords = f.geometry?.coordinates;
      if (coords) {
        gatewayCoordsSet.add(roundCoord(coords));
      }
    });
    
    // 根据坐标判断点的类型
    const getPointType = (coord) => {
      const key = roundCoord(coord);
      if (popCoordsSet.has(key)) {
        return 'PoP';
      } else if (gatewayCoordsSet.has(key)) {
        return 'Gateway';
      } else {
        return 'Unknown';
      }
    };
    
    // 处理连线，基于端点坐标匹配来添加连接类型属性
    // 过滤掉端点不在已知 PoP 或 Gateway 中的连线
    const classifiedLineFeatures = [];
    
    lineFeatures.forEach(feature => {
      const coordsList = feature.geometry?.coordinates || [];
      if (coordsList.length < 2) {
        return; // 跳过无效连线
      }
      
      // 获取起点和终点坐标
      const startCoord = coordsList[0];
      const endCoord = coordsList[coordsList.length - 1];
      
      // 判断端点类型
      const startType = getPointType(startCoord);
      const endType = getPointType(endCoord);
      
      // 如果任一端点是 Unknown（不在已知 PoP 或 Gateway 中），跳过这条连线
      if (startType === 'Unknown' || endType === 'Unknown') {
        return;
      }
      
      // 分类逻辑（排序以忽略方向）
      const pairTypes = [startType, endType].sort();
      
      let connectionType;
      if (pairTypes[0] === 'PoP' && pairTypes[1] === 'PoP') {
        connectionType = 'pop-pop';
      } else if (pairTypes.includes('Gateway') && pairTypes.includes('PoP')) {
        connectionType = 'gateway-pop';
      } else if (pairTypes[0] === 'Gateway' && pairTypes[1] === 'Gateway') {
        connectionType = 'gateway-gateway';
      } else {
        connectionType = 'pop-pop'; // 默认
      }
      
      classifiedLineFeatures.push({
        ...feature,
        properties: {
          ...feature.properties,
          connectionType: connectionType
        }
      });
    });

    // 处理跨越日期线的线段
    const processedLineFeatures = processDateLineCrossing(classifiedLineFeatures);
    
    // 创建数据源
    const popData = {
      type: 'FeatureCollection',
      features: popFeatures
    };
    
    const gatewayGeoData = {
      type: 'FeatureCollection',
      features: gatewayFeatures
    };
    
    const lineData = {
      type: 'FeatureCollection',
      features: processedLineFeatures
    };
    
    // 添加/更新数据源
    if (!map.getSource('starlink-lines')) {
      map.addSource('starlink-lines', { type: 'geojson', data: lineData });
    } else {
      map.getSource('starlink-lines').setData(lineData);
    }
    
    if (!map.getSource('starlink-points')) {
      map.addSource('starlink-points', { type: 'geojson', data: popData });
    } else {
      map.getSource('starlink-points').setData(popData);
    }
    
    if (!map.getSource('starlink-gateways')) {
      map.addSource('starlink-gateways', { type: 'geojson', data: gatewayGeoData });
    } else {
      map.getSource('starlink-gateways').setData(gatewayGeoData);
    }

    // 添加 PoP-PoP 骨干网络连线图层（红色，较粗）
    if (!map.getLayer('starlink-lines-layer')) {
      map.addLayer({
        id: 'starlink-lines-layer',
        type: 'line',
        source: 'starlink-lines',
        filter: ['==', ['get', 'connectionType'], 'pop-pop'],
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
          'visibility': 'visible'
        },
        paint: {
          'line-color': '#E13737',
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            1, 3,
            4, 5,
            8, 7
          ],
          'line-opacity': 0.8
        }
      });
    }
    
    // 添加 Gateway 相关连线图层（黄绿色，较细）
    if (!map.getLayer('starlink-gateway-lines-layer')) {
      map.addLayer({
        id: 'starlink-gateway-lines-layer',
        type: 'line',
        source: 'starlink-lines',
        filter: ['any',
          ['==', ['get', 'connectionType'], 'gateway-pop'],
          ['==', ['get', 'connectionType'], 'gateway-gateway']
        ],
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
          'visibility': 'visible'
        },
        paint: {
          'line-color': '#9ACD32',
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            1, 1,
            4, 1.5,
            8, 2
          ],
          'line-opacity': 0.8
        }
      });
    }

    // 添加 PoP 节点图层
    if (!map.getLayer('starlink-points-layer')) {
      map.addLayer({
        id: 'starlink-points-layer',
        type: 'symbol',
        source: 'starlink-points',
        layout: {
          'icon-image': 'pop-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            0, 1.0,
            2, 1.2,
            4, 1.4,
            6, 1.6,
            8, 1.8
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': false,
          'icon-padding': 0,
          'text-field': ['step', ['zoom'], '', 4, ['get', 'ChineseName']],
          'text-font': ['Open Sans Regular'],
          'text-offset': [0, 1.8],
          'text-anchor': 'top',
          'text-size': [
            'interpolate', ['linear'], ['zoom'],
            4, 11,
            6, 12,
            8, 14
          ],
          'text-optional': true
        },
        paint: {
          'text-color': '#4DD0E1',
          'text-halo-color': 'rgba(0,0,0,0.8)',
          'text-halo-width': 2
        }
      });
    }
    
    // 添加 Gateway 图层（使用图标样式）
    if (!map.getLayer('starlink-gateways-layer')) {
      map.addLayer({
        id: 'starlink-gateways-layer',
        type: 'symbol',
        source: 'starlink-gateways',
        layout: {
          'icon-image': 'gateway-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            0, 0.8,
            2, 1.0,
            4, 1.2,
            6, 1.4,
            8, 1.6
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': false,
          'icon-padding': 0,
          'text-field': ['step', ['zoom'], '', 5, ['get', 'Name']],
          'text-font': ['Open Sans Regular'],
          'text-offset': [0, 1.6],
          'text-anchor': 'top',
          'text-size': [
            'interpolate', ['linear'], ['zoom'],
            5, 10,
            7, 11,
            9, 12
          ],
          'text-optional': true,
          'visibility': 'visible'
        },
        paint: {
          'text-color': '#FFAB91',
          'text-halo-color': 'rgba(0,0,0,0.8)',
          'text-halo-width': 2
        }
      });
    }

  } catch (err) {
    console.error('添加 Starlink 图层失败:', err);
    // 向上抛出，由调用方转为用户可见的图层错误通知
    throw err;
  }
};

// 设置图层
export const setupLayers = (map, openSidebar) => {
  addPopLayer(map, openSidebar);
};

