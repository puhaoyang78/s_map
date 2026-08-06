import {
  CLLI_TO_COUNTRY,
  POP_COUNTRY_MAPPING,
} from '../constants/infoViewConstants.js';
import { getChinesePopName } from './popNameMapping.js';
import { loadStarlinkData } from './starlinkGatewayData.js';

export const loadPopDetailData = async () => {
  try {
    const response = await fetch('/data/pop.json');
    return await response.json();
  } catch (error) {
    console.error('加载 PoP 详细信息数据失败:', error);
    return null;
  }
};

export const loadNetworkSegmentData = async () => {
  try {
    const response = await fetch('/data/pops.txt');
    const text = await response.text();

    const lines = text.trim().split('\n');
    const networkMap = {};

    lines.forEach((line) => {
      const parts = line.trim().split(',');
      if (parts.length < 2) return;

      const cidr = parts[0];
      const cllicode = parts[1].toLowerCase();
      if (!networkMap[cllicode]) {
        networkMap[cllicode] = [];
      }
      networkMap[cllicode].push(cidr);
    });

    return networkMap;
  } catch (error) {
    console.error('加载网段信息数据失败:', error);
    return {};
  }
};

const classifyFeature = (feature) => {
  const name = feature.properties?.Name || '';
  const description = feature.properties?.Description || '';

  const popPattern = /^[A-Z]{2,3}(?:\/[A-Z]{2,3})?\s*-\s*([A-Z]{4,8}\d?)$/;
  const popMatch = name.match(popPattern);

  if (popMatch) {
    return {
      type: 'pop',
      cllicode: popMatch[1].toLowerCase(),
    };
  }

  const isGateway =
    description.includes('Ka Antenna') ||
    description.includes('Ka Operational') ||
    description.includes('E Operational') ||
    description.includes('Status:');

  if (isGateway) {
    return {
      type: 'gateway',
      cllicode: null,
    };
  }

  const altPopPattern = /([A-Z]{4,8}\d?)\s*$/;
  const altMatch = name.replace(/\n/g, '').match(altPopPattern);

  if (altMatch && !isGateway) {
    const hasIXInfo =
      description.includes('IX') ||
      description.includes('100G') ||
      description.includes('200G') ||
      description.includes('400G');

    if (hasIXInfo) {
      return {
        type: 'pop',
        cllicode: altMatch[1].toLowerCase(),
      };
    }
  }

  return {
    type: 'unknown',
    cllicode: null,
  };
};

const parsePopDescription = (description) => {
  const result = {
    datacenter: '',
    ixConnections: [],
  };

  if (!description) return result;

  const lines = description.split('<br>').filter((line) => line.trim());

  if (lines.length > 0) {
    result.datacenter = lines[0].replace(/<[^>]*>/g, '').trim();
  }

  lines.forEach((line) => {
    const cleanLine = line.replace(/<[^>]*>/g, '').trim();
    if (
      cleanLine.includes('G')
      && (
        cleanLine.includes('IX')
        || cleanLine.includes('100')
        || cleanLine.includes('200')
        || cleanLine.includes('400')
      )
    ) {
      result.ixConnections.push(cleanLine);
    }
  });

  return result;
};

const normalizeName = (name) => String(name || '').replace(/\s+/g, ' ').trim();

const MANUAL_POPS = [
  {
    name: 'HNL',
    chineseName: '檀香山PoP点',
    coordinates: [-156.917106, 21.7055614, 0.0],
    description: 'Honolulu PoP',
    countryCode: 'US',
  },
  {
    name: 'Guam',
    chineseName: '塞班岛PoP点',
    coordinates: [144.8051944, 13.5028056, 0.0],
    description: 'Saipan PoP',
    countryCode: 'GU',
  },
  {
    name: 'Suva',
    chineseName: '斐济PoP点',
    coordinates: [178.4419, -18.1416, 0.0],
    description: 'Fiji PoP',
    countryCode: 'FJ',
  },
];

// 仅用于 pops.txt 网段查找，不影响 GeoJSON 原始 cllicode 与展示名称。
const networkCllicodeAlias = {
  aklnzl1: 'acklnzl1',
  prthau1: 'prthaus1',
  jtnaidn1: 'jtnaidn2',
  mnlaph1: 'mnlaphl1',
};

const resolvePopCountryCode = ({ name, cllicode }) => {
  if (cllicode) {
    const fromClli = CLLI_TO_COUNTRY[String(cllicode).toUpperCase()];
    if (fromClli) return fromClli;
  }

  const normalizedName = normalizeName(name);
  const fromNameClli = normalizedName.match(/([A-Z]{4,8}\d?)$/i);
  if (fromNameClli) {
    const matchedClli = fromNameClli[1].toUpperCase();
    const fromClli = CLLI_TO_COUNTRY[matchedClli];
    if (fromClli) return fromClli;
  }

  if (normalizedName === 'HNL') return 'US';
  if (normalizedName === 'Guam') return 'GU';
  if (normalizedName === 'Suva') return 'FJ';

  return '其他';
};

const resolvePopCountryName = (countryCode) => {
  if (!countryCode || countryCode === '其他') return '其他';
  return POP_COUNTRY_MAPPING[countryCode] || countryCode;
};

export const buildRenderedPopFeatures = async ({
  starlinkData,
  popDetailData,
  networkSegmentData,
  skipSLC2 = true,
} = {}) => {
  const [resolvedStarlinkData, resolvedPopDetailData, resolvedNetworkSegmentData] = await Promise.all([
    starlinkData ? Promise.resolve(starlinkData) : loadStarlinkData(),
    popDetailData ? Promise.resolve(popDetailData) : loadPopDetailData(),
    networkSegmentData ? Promise.resolve(networkSegmentData) : loadNetworkSegmentData(),
  ]);

  if (!resolvedStarlinkData) {
    return {
      features: [],
      summary: {
        total: 0,
        skipped: [],
      },
    };
  }

  const popDetailByCllicode = {};
  if (resolvedPopDetailData) {
    resolvedPopDetailData.forEach((pop) => {
      if (!pop.cllicode) return;
      popDetailByCllicode[pop.cllicode.toLowerCase()] = pop;
    });
  }

  const pointFeatures = (resolvedStarlinkData.features || []).filter((feature) => feature.geometry?.type === 'Point');
  const popFeatures = [];
  const skippedNames = [];

  pointFeatures.forEach((feature) => {
    const name = feature.properties?.Name || '';
    const description = feature.properties?.Description || '';
    const normalizedName = normalizeName(name);

    if (skipSLC2 && normalizedName === 'SLC2 - SLTYUTX1') {
      skippedNames.push(normalizedName);
      return;
    }

    const classification = classifyFeature(feature);

    if (classification.type === 'gateway') {
      return;
    }

    if (classification.type === 'pop') {
      const cllicode = classification.cllicode;
      const popDetail = cllicode ? popDetailByCllicode[cllicode] : null;
      const networkLookupCllicode = cllicode
        ? networkCllicodeAlias[cllicode] || cllicode
        : '';
      const networkSegments = networkLookupCllicode
        ? resolvedNetworkSegmentData[networkLookupCllicode] || []
        : [];
      const parsedDescription = parsePopDescription(description);

      const countryCode = resolvePopCountryCode({ name, cllicode });
      const countryName = resolvePopCountryName(countryCode);

      popFeatures.push({
        type: 'Feature',
        properties: {
          ...feature.properties,
          featureType: 'pop',
          cllicode,
          ChineseName: popDetail?.title?.split(' (')[0] || getChinesePopName(name),
          datacenter: parsedDescription.datacenter,
          ixConnections: JSON.stringify(parsedDescription.ixConnections),
          dnsname: popDetail?.dnsname || '',
          location: popDetail?.location || '',
          coveragecity: JSON.stringify(popDetail?.coveragecity || []),
          networkLookupCllicode,
          networkSegments: JSON.stringify(networkSegments),
          networkSegmentCount: networkSegments.length,
          countryCode,
          countryName,
        },
        geometry: feature.geometry,
      });
      return;
    }

    const countryCode = resolvePopCountryCode({ name, cllicode: null });
    const countryName = resolvePopCountryName(countryCode);

    popFeatures.push({
      type: 'Feature',
      properties: {
        ...feature.properties,
        featureType: 'pop',
        ChineseName: getChinesePopName(name),
        countryCode,
        countryName,
      },
      geometry: feature.geometry,
    });
  });

  MANUAL_POPS.forEach((pop) => {
    popFeatures.push({
      type: 'Feature',
      properties: {
        Name: pop.name,
        Description: pop.description,
        featureType: 'pop',
        ChineseName: pop.chineseName,
        networkLookupCllicode: '',
        networkSegments: '[]',
        networkSegmentCount: 0,
        countryCode: pop.countryCode,
        countryName: resolvePopCountryName(pop.countryCode),
      },
      geometry: {
        type: 'Point',
        coordinates: pop.coordinates,
      },
    });
  });

  return {
    features: popFeatures,
    summary: {
      total: popFeatures.length,
      skipped: Array.from(new Set(skippedNames)),
    },
  };
};

export const computeRenderedPopCountryStats = (features = []) => {
  const countryStats = {};

  features.forEach((feature) => {
    const countryName = feature.properties?.countryName || '其他';
    countryStats[countryName] = (countryStats[countryName] || 0) + 1;
  });

  return countryStats;
};
