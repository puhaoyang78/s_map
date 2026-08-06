import {
  CLLI_TO_COUNTRY,
  KNOWN_GATEWAY_COUNTRIES,
  POP_COUNTRY_MAPPING,
} from '../constants/infoViewConstants.js';

export const isGatewayFeature = (description = '') => {
  const desc = String(description).toLowerCase();
  return (
    desc.includes('antenna')
    || desc.includes('operational')
    || desc.includes('freq:')
    || desc.includes('callsign:')
    || desc.includes('ka antenna')
    || desc.includes('status:')
  );
};

export const extractGatewayCountryFromMapping = (chineseName = '') => {
  if (!chineseName) return '其他';
  const parts = chineseName.split(',').map((p) => p.trim());
  if (parts.length > 0) {
    const firstPart = parts[0];
    if (KNOWN_GATEWAY_COUNTRIES.includes(firstPart)) {
      return firstPart;
    }
    if (/^[A-Z]{2}\s*-/.test(firstPart)) {
      return '美国';
    }
  }
  return '其他';
};

export const getPopCountryChineseName = (countryCode) => {
  return POP_COUNTRY_MAPPING[countryCode] || countryCode;
};

export const computePopCountryStats = (features = []) => {
  const countryStats = {};

  features.forEach((feature) => {
    const name = feature.properties?.Name || '';
    let countryCode = '';

    const clliMatch = name.replace(/\n/g, '').match(/([A-Z]{4,8}\d?)$/i);
    if (clliMatch) {
      const clli = clliMatch[1].toUpperCase();
      countryCode = CLLI_TO_COUNTRY[clli] || '';
    }

    if (name === 'HNL') countryCode = 'US';
    if (name === 'Guam') countryCode = 'GU';
    if (name === 'Suva') countryCode = 'FJ';
    if (!countryCode) countryCode = '其他';

    const chineseName = getPopCountryChineseName(countryCode);
    countryStats[chineseName] = (countryStats[chineseName] || 0) + 1;
  });

  return countryStats;
};

export const filterPopFeatures = (features = []) => {
  return features.filter((feature) => {
    if (feature.geometry.type !== 'Point') return false;

    const name = feature.properties?.Name || '';
    const description = feature.properties?.Description || '';
    const isGateway = isGatewayFeature(description);
    const normalizedName = name.replace(/\n/g, '');
    const isPopFormat = /^[A-Z]{2,3}(?:\/[A-Z]{2,3})?\s*-\s*[A-Z]{4,8}\d?$/i.test(normalizedName);

    return !isGateway && (isPopFormat || name === 'HNL' || name === 'Guam' || name === 'Suva');
  });
};

export const parseFofaCsvRows = (csvText) => {
  const lines = csvText.trim().split('\n');
  const parsedData = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    const values = [];
    let inQuotes = false;
    let currentValue = '';

    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"' && (j === 0 || line[j - 1] !== '\\')) {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        values.push(currentValue);
        currentValue = '';
      } else {
        currentValue += char;
      }
    }
    values.push(currentValue);

    if (values.length >= 5) {
      parsedData.push({
        key: i,
        ip: values[0] || '',
        port: values[1] || '',
        protocol: values[2] || '',
        country_name: values[4] || '',
        region: values[5] || '',
        city: values[6] || '',
        longitude: values[7] || '',
        latitude: values[8] || '',
        as_number: values[9] || '',
        as_organization: values[10] || '',
        host: values[11] || '',
        domain: values[12] || '',
        os: values[13] || '',
        server: values[14] || '',
        icp: values[15] || '',
        title: values[16] || '',
        jarm: values[17] || '',
        base_protocol: values[18] || '',
        link: values[19] || '',
        certs_issuer_org: values[20] || '',
        certs_issuer_cn: values[21] || '',
        certs_subject_org: values[22] || '',
        certs_subject_cn: values[23] || '',
        tls_ja3s: values[24] && values[24].trim() ? values[24] : null,
        tls_version: values[25] && values[25].trim() ? values[25] : null,
      });
    }
  }

  return parsedData;
};

export const calculateEndIpFromCidr = (startIp, cidr) => {
  const parts = startIp.split('.').map(Number);
  const hostBits = 32 - cidr;
  const totalIps = Math.pow(2, hostBits) - 1;

  let ipNum = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3];
  ipNum += totalIps;

  const endParts = [
    (ipNum >>> 24) & 0xFF,
    (ipNum >>> 16) & 0xFF,
    (ipNum >>> 8) & 0xFF,
    ipNum & 0xFF,
  ];

  return endParts.join('.');
};
