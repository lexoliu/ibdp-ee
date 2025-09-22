import http from 'k6/http';
import { check, sleep } from 'k6';

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
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || 'http://127.0.0.1:8080';
const startTimestamp = Date.now();

export default function () {
  // Add per-second tag
  const secIndex = Math.floor((Date.now() - startTimestamp) / 1000);
  const secTag = secIndex.toString().padStart(6, '0');
  
  // 80% get，18% set，2% delete
  const id = `${__VU}-${__ITER % 100000}`;
  const r = Math.random();

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
    const res = http.post(`${base}/kv/set/${id}`, 'v' + Math.random(), {
      tags: {
        name: 'kv-set',
        url: '/kv/set/:id',
        sec: secTag,
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  } else {
    const res = http.del(`${base}/kv/delete/${id}`, null, {
      tags: {
        name: 'kv-delete',
        url: '/kv/delete/:id',
        sec: secTag,
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  }
  sleep(0.001);
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
