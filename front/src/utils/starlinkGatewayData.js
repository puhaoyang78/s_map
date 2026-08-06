/**
 * 构造地图实际渲染的 Gateway 特征集合。
 * 该模块复用地图层的匹配与去重口径，供地图与信息面板共享。
 */

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

const parseGatewayDescription = (description) => {
  const result = {
    status: '',
    location: '',
    notes: '',
    kaOperational: false,
    eOperational: false,
    kaAntennaCount: '',
    eAntennaCount: '',
    freq: '',
  };

  if (!description) return result;

  const statusMatch = description.match(/Status:\s*([^<]+)/);
  if (statusMatch) result.status = statusMatch[1].trim();

  const locationMatch = description.match(/Location:\s*([^<]+)/);
  if (locationMatch) result.location = locationMatch[1].trim();

  const notesMatch = description.match(/Notes:\s*([^<]+)/);
  if (notesMatch) result.notes = notesMatch[1].trim();

  const kaOpMatch = description.match(/Ka Operational:\s*(TRUE|FALSE)/i);
  if (kaOpMatch) result.kaOperational = kaOpMatch[1].toUpperCase() === 'TRUE';

  const eOpMatch = description.match(/E Operational:\s*(TRUE|FALSE)/i);
  if (eOpMatch) result.eOperational = eOpMatch[1].toUpperCase() === 'TRUE';

  const kaCountMatch = description.match(/Ka Antenna Count:\s*(\d+)/);
  if (kaCountMatch) result.kaAntennaCount = kaCountMatch[1];

  const eCountMatch = description.match(/E Antenna Count:\s*(\d+)/);
  if (eCountMatch) result.eAntennaCount = eCountMatch[1];

  const freqMatch = description.match(/Freq:\s*([^<]+)/);
  if (freqMatch) result.freq = freqMatch[1].trim();

  return result;
};

const normalizeCityName = (name) => {
  if (!name) return null;
  return String(name)
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’']/g, '')
    .replace(/\(.*?\)/g, ' ')
    .replace(/[|]/g, ' ')
    .replace(/[\s,]+[a-z]{2,3}\s*$/i, ' ')
    .replace(/[.,]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

const normalizeToken = (value) => {
  if (!value) return '';
  return String(value)
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’']/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

const escapeRegExp = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const hasToken = (text, token) => {
  if (!text || !token) return false;
  const pattern = new RegExp(`(^|\\s)${escapeRegExp(token)}(\\s|$)`);
  return pattern.test(text);
};

const usStateCodeMap = {
  alabama: 'al', alaska: 'ak', arizona: 'az', arkansas: 'ar', california: 'ca',
  colorado: 'co', connecticut: 'ct', delaware: 'de', florida: 'fl', georgia: 'ga',
  hawaii: 'hi', idaho: 'id', illinois: 'il', indiana: 'in', iowa: 'ia',
  kansas: 'ks', kentucky: 'ky', louisiana: 'la', maine: 'me', maryland: 'md',
  massachusetts: 'ma', michigan: 'mi', minnesota: 'mn', mississippi: 'ms', missouri: 'mo',
  montana: 'mt', nebraska: 'ne', nevada: 'nv', 'new hampshire': 'nh', 'new jersey': 'nj',
  'new mexico': 'nm', 'new york': 'ny', 'north carolina': 'nc', 'north dakota': 'nd', ohio: 'oh',
  oklahoma: 'ok', oregon: 'or', pennsylvania: 'pa', 'rhode island': 'ri',
  'south carolina': 'sc', 'south dakota': 'sd', tennessee: 'tn', texas: 'tx', utah: 'ut',
  vermont: 'vt', virginia: 'va', washington: 'wa', 'west virginia': 'wv', wisconsin: 'wi',
  wyoming: 'wy', 'district of columbia': 'dc'
};

const resolveStateTokens = (state) => {
  const tokens = new Set();
  const normalized = normalizeToken(state);
  if (!normalized) return [];
  tokens.add(normalized);
  if (normalized.length === 2) {
    tokens.add(normalized);
  } else if (usStateCodeMap[normalized]) {
    tokens.add(usStateCodeMap[normalized]);
  }
  return Array.from(tokens);
};

const gatewayCityAlias = {
  'milano': 'milan',
  'coviha': 'covilha',
  'villenave dornon': 'villenave dornon',
  'usingen': 'frankfurt',
  'ballinspittle': 'garrettstown',
  'alfouvar de cima': 'covilha',
  'murayjat': 'blue city',
};

// 仅合并已确认重复的别名点，避免误伤不同站点（例如 Charleston）。
const duplicateGatewayAliasesToSkip = new Set([
  'coviha|portugal',
]);

const extractCityFromName = (name) => {
  if (!name) return null;
  const main = String(name).split(',')[0].replace(/\s*\(gsn#\d+\)$/i, '').trim();
  return normalizeCityName(main);
};

const extractLocationCity = (description) => {
  if (!description) return null;
  const match = String(description).match(/Location:\s*([^<]+)/i);
  if (!match) return null;
  const rawLocation = match[1].trim();
  const city = rawLocation.split(',')[0].trim();
  return normalizeCityName(city);
};

const extractNoteAlias = (description) => {
  if (!description) return [];
  const notesMatch = String(description).match(/Notes:\s*([^<]+)/i);
  if (!notesMatch) return [];
  const note = notesMatch[1] || '';
  const aliases = [];
  const paren = note.match(/\(([^)]+)\)/g) || [];
  paren.forEach((seg) => {
    const text = seg.replace(/[()]/g, '').trim();
    const normalized = normalizeCityName(text);
    if (normalized) aliases.push(normalized);
  });
  return aliases;
};

const extractStructuredParts = (value) => {
  if (!value) return [];
  const primary = String(value).split('|')[0].split('/')[0].trim();
  return primary
    .split(',')
    .map((part) => normalizeToken(part))
    .filter(Boolean);
};

const extractLocationParts = (description) => {
  if (!description) return [];
  const match = String(description).match(/Location:\s*([^<]+)/i);
  if (!match) return [];
  return extractStructuredParts(match[1]);
};

const makeCoordKey = (coords) => {
  if (!coords || coords.length < 2) return null;
  const lon = Math.round(coords[0] * 1000000) / 1000000;
  const lat = Math.round(coords[1] * 1000000) / 1000000;
  return `${lon},${lat}`;
};

const isGatewayPointFeature = (feature) => {
  const description = feature?.properties?.Description || '';
  return (
    feature?.geometry?.type === 'Point' &&
    description.includes('Status:') &&
    (description.includes('Ka Operational:') || description.includes('E Operational:'))
  );
};

export const buildRenderedGatewayFeatures = async ({
  starlinkData,
  gatewayData,
  enableConservativeDedupe = false,
} = {}) => {
  const [resolvedStarlinkData, resolvedGatewayData] = await Promise.all([
    starlinkData ? Promise.resolve(starlinkData) : loadStarlinkData(),
    gatewayData ? Promise.resolve(gatewayData) : loadGatewayData(),
  ]);

  if (!resolvedStarlinkData || !resolvedGatewayData?.gateways) {
    return {
      gatewayFeatures: [],
      missingGatewayNames: [],
      mergedGatewayNames: [],
    };
  }

  const pointFeatures = (resolvedStarlinkData.features || []).filter((feature) => feature.geometry?.type === 'Point');
  const countryCodeMap = resolvedGatewayData.countryCodeMap || {};

  const geojsonGatewayByCity = {};
  const geojsonGatewayEntries = [];

  pointFeatures.forEach((feature) => {
    if (!isGatewayPointFeature(feature)) return;

    const name = feature.properties?.Name || '';
    const description = feature.properties?.Description || '';

    const cityKeys = new Set();
    const cityFromName = extractCityFromName(name);
    const cityFromLocation = extractLocationCity(description);
    const cityFromNotes = extractNoteAlias(description);

    if (cityFromName) cityKeys.add(cityFromName);
    if (cityFromLocation) cityKeys.add(cityFromLocation);
    cityFromNotes.forEach((k) => cityKeys.add(k));

    const nameParts = extractStructuredParts(name);
    const locationParts = extractLocationParts(description);
    const regionTokens = new Set();
    const countryTokens = new Set();

    const collectRegionCountry = (parts) => {
      if (parts[1]) regionTokens.add(parts[1]);
      if (parts[2]) countryTokens.add(parts[2]);
      if (parts.length === 2 && parts[1].length <= 3) {
        countryTokens.add(parts[1]);
      }
    };

    collectRegionCountry(nameParts);
    collectRegionCountry(locationParts);

    const entry = {
      feature,
      keys: Array.from(cityKeys),
      regionTokens,
      countryTokens,
      searchableText: normalizeToken(`${name} ${description}`),
    };

    entry.keys.forEach((key) => {
      if (!key) return;
      if (!geojsonGatewayByCity[key]) {
        geojsonGatewayByCity[key] = [];
      }
      geojsonGatewayByCity[key].push(entry);
    });

    geojsonGatewayEntries.push(entry);
  });

  const pickGatewayEntry = (candidates, gateway) => {
    if (!candidates || candidates.length === 0) return null;

    const stateTokens = resolveStateTokens(gateway?.state);
    const countryTokens = new Set();
    const normalizedCountry = normalizeToken(gateway?.country);
    if (normalizedCountry) countryTokens.add(normalizedCountry);
    const normalizedCountryCode = normalizeToken(countryCodeMap[gateway?.country] || '');
    if (normalizedCountryCode) countryTokens.add(normalizedCountryCode);

    let scoped = candidates;

    if (stateTokens.length > 0) {
      const byState = scoped.filter((entry) =>
        stateTokens.some((token) =>
          entry.regionTokens.has(token) || hasToken(entry.searchableText, token)
        )
      );
      if (byState.length > 0) {
        scoped = byState;
      }
    }

    if (countryTokens.size > 0) {
      const tokenList = Array.from(countryTokens);
      const byCountry = scoped.filter((entry) =>
        tokenList.some((token) =>
          entry.countryTokens.has(token) ||
          entry.regionTokens.has(token) ||
          hasToken(entry.searchableText, token)
        )
      );
      if (byCountry.length > 0) {
        scoped = byCountry;
      }
    }

    return scoped[0] || null;
  };

  const findStateAwareGatewayMatch = (gateway, cityToken) => {
    if (!cityToken) return null;

    const normalizedCountry = normalizeToken(gateway?.country);
    if (normalizedCountry !== 'united states') return null;

    const stateTokens = resolveStateTokens(gateway?.state);
    if (stateTokens.length === 0) return null;

    const cityCandidates = geojsonGatewayByCity[cityToken] || [];
    const stateAwareInCity = cityCandidates.find((entry) =>
      stateTokens.some((token) =>
        entry.regionTokens.has(token) || hasToken(entry.searchableText, token)
      )
    );
    if (stateAwareInCity) {
      return stateAwareInCity;
    }

    const stateAwareFuzzy = geojsonGatewayEntries.find((entry) =>
      entry.keys.some((key) => key === cityToken) &&
      stateTokens.some((token) =>
        entry.regionTokens.has(token) || hasToken(entry.searchableText, token)
      )
    );

    return stateAwareFuzzy || null;
  };

  const resolveGatewayFeature = (gateway) => {
    const normalizedCity = normalizeCityName(gateway?.city);
    if (!normalizedCity) return null;

    const stateAwareMatch = findStateAwareGatewayMatch(gateway, normalizedCity);
    if (stateAwareMatch) {
      return stateAwareMatch.feature;
    }

    const aliasCity = gatewayCityAlias[normalizedCity] || normalizedCity;

    const directCandidates = geojsonGatewayByCity[aliasCity] || [];
    const directMatch = pickGatewayEntry(directCandidates, gateway);
    if (directMatch) {
      return directMatch.feature;
    }

    const fuzzyCandidates = geojsonGatewayEntries.filter((entry) =>
      entry.keys.some((k) => k.includes(aliasCity) || aliasCity.includes(k))
    );
    const fuzzyMatch = pickGatewayEntry(fuzzyCandidates, gateway);
    if (fuzzyMatch) {
      return fuzzyMatch.feature;
    }

    return null;
  };

  const gatewayFeatures = [];
  const missingGatewayNames = [];
  const mergedGatewayNames = [];

  const seenGatewayByName = new Set();
  const seenGatewayByCoordCountry = new Set();

  resolvedGatewayData.gateways.forEach((gw, index) => {
    const normalizedGatewayCity = normalizeCityName(gw.city) || '';
    const normalizedGatewayCountry = normalizeToken(gw.country);
    const gatewayAliasSkipKey = `${normalizedGatewayCity}|${normalizedGatewayCountry}`;

    if (duplicateGatewayAliasesToSkip.has(gatewayAliasSkipKey)) {
      mergedGatewayNames.push(`${gw.city}, ${gw.country}`);
      return;
    }

    const geojsonFeature = resolveGatewayFeature(gw);
    if (!geojsonFeature) {
      missingGatewayNames.push(`${gw.city}, ${gw.country}`);
      return;
    }

    const normalizedCountry = normalizeToken(gw.country);
    const normalizedGeoName = normalizeToken(geojsonFeature.properties?.Name || '');
    const dedupeByNameKey = `${normalizedCountry}::${normalizedGeoName}`;
    const coordKey = makeCoordKey(geojsonFeature.geometry?.coordinates);
    const dedupeByCoordKey = coordKey ? `${normalizedCountry}::${coordKey}` : null;

    if (
      enableConservativeDedupe &&
      (
        seenGatewayByName.has(dedupeByNameKey) ||
        (dedupeByCoordKey && seenGatewayByCoordCountry.has(dedupeByCoordKey))
      )
    ) {
      mergedGatewayNames.push(`${gw.city}, ${gw.country}`);
      return;
    }

    seenGatewayByName.add(dedupeByNameKey);
    if (dedupeByCoordKey) {
      seenGatewayByCoordCountry.add(dedupeByCoordKey);
    }

    const description = geojsonFeature.properties?.Description || '';
    const parsedDescription = parseGatewayDescription(description);

    gatewayFeatures.push({
      type: 'Feature',
      properties: {
        ...geojsonFeature.properties,
        featureType: 'gateway',
        gatewayId: index + 1,
        ChineseName: `${gw.city}, ${gw.country}`,
        city: gw.city,
        country: gw.country,
        countryCode: countryCodeMap[gw.country] || '',
        region: gw.region,
        state: gw.state || '',
        status: gw.status,
        gatewayLocation: parsedDescription.location,
        notes: parsedDescription.notes,
        kaOperational: parsedDescription.kaOperational,
        eOperational: parsedDescription.eOperational,
        kaAntennaCount: parsedDescription.kaAntennaCount,
        eAntennaCount: parsedDescription.eAntennaCount,
        freq: parsedDescription.freq,
      },
      geometry: geojsonFeature.geometry,
    });
  });

  return {
    gatewayFeatures,
    missingGatewayNames,
    mergedGatewayNames,
  };
};
