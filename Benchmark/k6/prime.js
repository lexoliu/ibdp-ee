import http from "k6/http";

// Parse duration to get total seconds for threshold generation
const duration = __ENV.K6_DURATION || "30s";
const DURATION_SEC = parseDuration(duration);

// Generate thresholds for each second to force k6 to aggregate per-second
function generateThresholds() {
  const thresholds = {};
  for (let s = 0; s <= DURATION_SEC; s++) {
    const sec = s.toString().padStart(6, '0');
    thresholds[`http_reqs{sec:${sec}}`] = ['count>=0'];
    thresholds[`http_req_duration{sec:${sec}}`] = ['p(95)>=0'];
  }
  return thresholds;
}

export let options = { 
  vus: 50, 
  duration: duration,
  thresholds: generateThresholds()
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || "http://127.0.0.1:8080";
const startTimestamp = Date.now();

export default function () {
  // Add per-second tag
  const secIndex = Math.floor((Date.now() - startTimestamp) / 1000);
  const secTag = secIndex.toString().padStart(6, '0');
  
  // 生成大数 (1e12 ~ 1e18)
  let n = Math.floor(Math.random() * 1e6) + 1e12;
  http.get(`${base}/prime/${n}`, {
    tags: {
      name: 'prime-check',
      url: '/prime/:n',
      sec: secTag,
    },
  });
}

export function handleSummary(data) {
  const metrics = data.metrics;
  let csv = 'second,requests,avg_ms,p50_ms,p90_ms,p99_ms\n';
  
  for (let s = 0; s <= DURATION_SEC; s++) {
    const sec = s.toString().padStart(6, '0');
    const count = metrics[`http_reqs{sec:${sec}}`]?.values?.count ?? 0;
    const avg = metrics[`http_req_duration{sec:${sec}}`]?.values?.avg ?? '';
    const p50 = metrics[`http_req_duration{sec:${sec}}`]?.values?.['p(50)'] ?? '';
    const p90 = metrics[`http_req_duration{sec:${sec}}`]?.values?.['p(90)'] ?? '';
    const p99 = metrics[`http_req_duration{sec:${sec}}`]?.values?.['p(99)'] ?? '';
    if (count > 0) {
      csv += `${s},${count},${avg || 0},${p50 || 0},${p90 || 0},${p99 || 0}\n`;
    }
  }
  
  return { 'prime_timeseries.csv': csv };
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
