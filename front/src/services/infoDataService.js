const jsonCache = new Map();
const textCache = new Map();

/**
 * Fetch JSON data from public static path.
 * Reuse the same in-flight request so tabs/panels do not refetch identical assets.
 * @param {string} path
 * @returns {Promise<any>}
 */
const fetchPublicJson = async (path) => {
  if (jsonCache.has(path)) {
    return jsonCache.get(path);
  }

  const request = fetch(path)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`请求失败: ${path}`);
      }
      return response.json();
    })
    .catch((error) => {
      jsonCache.delete(path);
      throw error;
    });

  jsonCache.set(path, request);
  return request;
};

/**
 * Fetch text data from public static path.
 * @param {string} path
 * @param {{ cache?: boolean }} options
 * @returns {Promise<string>}
 */
const fetchPublicText = async (path, options = {}) => {
  const { cache = true } = options;
  if (cache && textCache.has(path)) {
    return textCache.get(path);
  }

  const requestPath = cache
    ? path
    : `${path}${path.includes('?') ? '&' : '?'}_=${Date.now()}`;

  const request = fetch(requestPath)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`请求失败: ${path}`);
      }
      return response.text();
    })
    .catch((error) => {
      if (cache) {
        textCache.delete(path);
      }
      throw error;
    });

  if (cache) {
    textCache.set(path, request);
  }
  return request;
};

export const fetchGatewayPopGeojson = () => fetchPublicJson('/data/Unofficial Starlink Global Gateways & PoPs.geojson');

/**
 * @param {string} csvPath
 */
export const fetchScanReportCsv = (csvPath) => fetchPublicText(csvPath);

export const fetchIpv4PrefixesCsv = () => fetchPublicText('/data/as14593_ipv4_prefixes.csv');

export const fetchFofaAsnCsv = () => fetchPublicText('/data/FOFA探测ASN结果.csv', { cache: false });
