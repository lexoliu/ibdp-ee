import http from 'k6/http';
import { check, sleep, fail } from 'k6';

// Parse duration to get total seconds for threshold generation
const duration = __ENV.K6_DURATION || "30s";
const DURATION_SEC = parseDuration(duration);

// Generate thresholds for each second to force k6 to aggregate per-second
function generateThresholds() {
  const thresholds = {
    http_req_failed: ['rate<0.01'],
  };
  for (let s = 0; s <= DURATION_SEC; s++) {
    const sec = s.toString().padStart(6, '0');
    thresholds[`http_reqs{sec:${sec}}`] = ['count>=0'];
    thresholds[`http_req_duration{sec:${sec}}`] = ['p(95)>=0'];
  }
  return thresholds;
}

export const options = {
  duration: duration,
  thresholds: generateThresholds(),
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)'],
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || 'http://127.0.0.1:8080';
const startTimestamp = Date.now();
const MAX_RETRIES = parseInt(__ENV.K6_MAX_RETRIES || '5', 10);
const RETRY_DELAY = parseFloat(__ENV.K6_RETRY_DELAY || '0.01');
const mode = (__ENV.K6_MODE || __ENV.MODE || 'normal').toLowerCase();
const defaultKeySpace = mode === 'debug' ? 1000 : 100000;
const KEY_SPACE = parseInt(__ENV.K6_KV_KEY_SPACE || `${defaultKeySpace}`, 10);

// Realistic cache value generation for middleware simulation
const CACHE_PATTERNS = {
  // User session data (common in web apps)
  userSession: () => JSON.stringify({
    userId: Math.floor(Math.random() * 1000000),
    sessionId: generateUUID(),
    loginTime: Date.now(),
    permissions: ['read', 'write', 'admin'][Math.floor(Math.random() * 3)],
    preferences: {
      theme: ['dark', 'light'][Math.floor(Math.random() * 2)],
      language: ['en', 'zh', 'es', 'fr'][Math.floor(Math.random() * 4)],
      timezone: 'UTC+' + (Math.floor(Math.random() * 24) - 12)
    },
    lastActivity: Date.now() - Math.floor(Math.random() * 3600000)
  }),
  
  // API response cache (typical JSON responses)
  apiResponse: () => JSON.stringify({
    status: 'success',
    data: {
      items: Array.from({length: Math.floor(Math.random() * 50) + 10}, (_, i) => ({
        id: i,
        name: `Item ${i}`,
        value: Math.random() * 1000,
        metadata: {
          created: Date.now() - Math.floor(Math.random() * 86400000),
          tags: Array.from({length: Math.floor(Math.random() * 5)}, () => 
            ['urgent', 'normal', 'low', 'critical', 'pending'][Math.floor(Math.random() * 5)]
          )
        }
      })),
      pagination: {
        page: Math.floor(Math.random() * 100),
        total: Math.floor(Math.random() * 10000),
        hasMore: Math.random() > 0.5
      }
    },
    timestamp: Date.now(),
    requestId: generateUUID()
  }),
  
  // Configuration cache (smaller but important data)
  config: () => JSON.stringify({
    appVersion: '2.1.' + Math.floor(Math.random() * 100),
    features: {
      enableAnalytics: Math.random() > 0.3,
      enableChat: Math.random() > 0.2,
      enableNotifications: Math.random() > 0.1,
      maxConnections: Math.floor(Math.random() * 1000) + 100
    },
    endpoints: {
      api: 'https://api.example.com/v' + Math.floor(Math.random() * 5),
      ws: 'wss://ws.example.com',
      cdn: 'https://cdn.example.com'
    },
    updated: Date.now()
  }),
  
  // Large text content (documents, articles)
  document: () => {
    const paragraphs = Math.floor(Math.random() * 20) + 5;
    const content = Array.from({length: paragraphs}, () => {
      const sentences = Math.floor(Math.random() * 10) + 3;
      return Array.from({length: sentences}, () => 
        generateLoremSentence()
      ).join(' ');
    }).join('\n\n');
    
    return JSON.stringify({
      title: 'Document ' + Math.floor(Math.random() * 100000),
      content: content,
      wordCount: content.split(' ').length,
      created: Date.now() - Math.floor(Math.random() * 2592000000), // up to 30 days ago
      author: 'User' + Math.floor(Math.random() * 1000),
      tags: Array.from({length: Math.floor(Math.random() * 8) + 2}, () => 
        ['tech', 'business', 'news', 'analysis', 'report', 'draft', 'published'][Math.floor(Math.random() * 7)]
      )
    });
  },
  
  // Binary-like data (base64 encoded "files")
  binaryData: () => {
    const size = Math.floor(Math.random() * 2048) + 256; // 256-2304 bytes
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let result = '';
    for (let i = 0; i < size; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return JSON.stringify({
      type: ['image', 'document', 'archive', 'video'][Math.floor(Math.random() * 4)],
      encoding: 'base64',
      size: size,
      data: result,
      checksum: 'sha256:' + generateUUID().replace(/-/g, ''),
      uploadTime: Date.now()
    });
  }
};

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function generateLoremSentence() {
  const words = ['lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing', 'elit',
    'sed', 'do', 'eiusmod', 'tempor', 'incididunt', 'ut', 'labore', 'et', 'dolore', 'magna',
    'aliqua', 'enim', 'ad', 'minim', 'veniam', 'quis', 'nostrud', 'exercitation', 'ullamco',
    'laboris', 'nisi', 'aliquip', 'ex', 'ea', 'commodo', 'consequat', 'duis', 'aute', 'irure',
    'in', 'reprehenderit', 'voluptate', 'velit', 'esse', 'cillum', 'fugiat', 'nulla', 'pariatur'];
  
  const sentenceLength = Math.floor(Math.random() * 15) + 8;
  const sentence = Array.from({length: sentenceLength}, () => 
    words[Math.floor(Math.random() * words.length)]
  ).join(' ');
  
  return sentence.charAt(0).toUpperCase() + sentence.slice(1) + '.';
}

function generateRealisticCacheValue() {
  const patterns = Object.keys(CACHE_PATTERNS);
  // Weight distribution to simulate real cache usage:
  // 40% API responses, 25% user sessions, 15% documents, 10% config, 10% binary
  const weights = [0.4, 0.65, 0.8, 0.9, 1.0];
  const rand = Math.random();
  
  let patternIndex = 0;
  for (let i = 0; i < weights.length; i++) {
    if (rand < weights[i]) {
      patternIndex = i;
      break;
    }
  }
  
  const patternName = patterns[patternIndex];
  return CACHE_PATTERNS[patternName]();
}

function requestWithRetry(fn, description) {
  let attempt = 0;
  let res;
  while (attempt < MAX_RETRIES) {
    res = fn();
    if (res?.status === 200) {
      check(res, { '200': (r) => r.status === 200 });
      return res;
    }
    attempt += 1;
    if (attempt < MAX_RETRIES) {
      sleep(RETRY_DELAY);
    }
  }
  check(res, { '200': (r) => r?.status === 200 });
  fail(`${description} failed after ${MAX_RETRIES} attempts (status=${res?.status})`);
}

export default function () {
  // Add per-second tag
  const secIndex = Math.floor((Date.now() - startTimestamp) / 1000);
  const secTag = secIndex.toString().padStart(6, '0');
  
  // 80% get，18% set，2% delete
  const id = `${__VU}-${__ITER % KEY_SPACE}`;
  const r = Math.random();

  if (__ITER < KEY_SPACE) {
    requestWithRetry(
      () => http.post(`${base}/kv/set/${id}`, generateRealisticCacheValue(), {
        tags: {
          name: 'kv-prime',
          url: '/kv/set/:id',
          sec: secTag,
        },
      }),
      `kv-prime ${id}`,
    );
    sleep(0.001);
    return;
  }

  if (r < 0.80) {
    const res = http.get(`${base}/kv/get/${id}`, {
      tags: {
        name: 'kv-get',
        url: '/kv/get/:id',
        sec: secTag,
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  } else if (r < 0.98) {
    const params = {
      tags: {
        name: 'kv-set',
        url: '/kv/set/:id',
        sec: secTag,
      },
    };
    requestWithRetry(
      () => http.post(`${base}/kv/set/${id}`, generateRealisticCacheValue(), params),
      `kv-set ${id}`,
    );
  } else {
    const params = {
      tags: {
        name: 'kv-delete',
        url: '/kv/delete/:id',
        sec: secTag,
      },
    };
    requestWithRetry(
      () => http.del(`${base}/kv/delete/${id}`, null, params),
      `kv-delete ${id}`,
    );
    requestWithRetry(
      () => http.post(`${base}/kv/set/${id}`, generateRealisticCacheValue(), {
        tags: {
          name: 'kv-refill',
          url: '/kv/set/:id',
          sec: secTag,
        },
      }),
      `kv-refill ${id}`,
    );
  }
  sleep(0.001);
}

export function handleSummary(data) {
  const metrics = data.metrics;
  let csv = 'second,requests,avg_ms,p50_ms,p90_ms,p99_ms\n';
  
  for (let s = 0; s <= DURATION_SEC; s++) {
    const sec = s.toString().padStart(6, '0');
    const count = metrics[`http_reqs{sec:${sec}}`]?.values?.count ?? 0;
    const durationStats = metrics[`http_req_duration{sec:${sec}}`]?.values ?? {};
    const avg = durationStats.avg ?? '';
    const p50 = durationStats['p(50)'] ?? durationStats.med ?? '';
    const p90 = durationStats['p(90)'] ?? '';
    const p99 = durationStats['p(99)'] ?? '';
    if (count > 0) {
      csv += `${s},${count},${avg || 0},${p50 || 0},${p90 || 0},${p99 || 0}\n`;
    }
  }
  
  return { 'kv_timeseries.csv': csv };
}

function parseDuration(duration) {
  const match = duration.match(/(\d+)([smh])/);
  if (!match) return 30; // default
  const [, num, unit] = match;
  const n = parseInt(num);
  if (unit === 's') return n;
  if (unit === 'm') return n * 60;
  if (unit === 'h') return n * 3600;
  return 30;
}
