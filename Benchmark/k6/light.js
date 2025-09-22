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

// 从环境读取并发/时长（也支持 CLI --vus/--duration）
export const options = {
  duration: duration,
  thresholds: generateThresholds(),
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)'],
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || 'http://127.0.0.1:8080';
const startTimestamp = Date.now();

// 负载配比（总和为1）：你可以随时调整
const MIX = [
  { name: 'echo',    p: 0.40 },
  { name: 'json',    p: 0.40 },
  { name: 'json2xml',p: 0.20 },
];

function pick() {
  const r = Math.random();
  let acc = 0;
  for (const it of MIX) {
    acc += it.p;
    if (r < acc) return it.name;
  }
  return MIX[MIX.length - 1].name;
}

export default function () {
  // Add per-second tag
  const secIndex = Math.floor((Date.now() - startTimestamp) / 1000);
  const secTag = secIndex.toString().padStart(6, '0');
  
  const which = pick();
  let res;

  if (which === 'echo') {
    const body = 'hello ' + Math.random();
    res = http.post(`${base}/echo`, body, {
      tags: { sec: secTag, name: 'echo' }
    });
  } else if (which === 'json') {
    const payload = JSON.stringify({
      gender: 'M',
      id: Math.floor(Math.random() * 1e9),
      name: 'Lexo',
      age: 19,
      description: 'hi',
      height: 1.78,
      weight: 60.0,
    });
    res = http.post(`${base}/json`, payload, {
      headers: { 'Content-Type': 'application/json' },
      tags: { sec: secTag, name: 'json' }
    });
  } else { // json2xml
    const payload = JSON.stringify({
      user: { name: 'Lexo', age: 19 },
      scores: [1, 2, 3, 4, 5],
      ts: Date.now(),
    });
    res = http.post(`${base}/json2xml`, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: '60s',
      tags: { sec: secTag, name: 'json2xml' }
    });
  }

  check(res, { 'status 200': (r) => r.status === 200 });
  // 轻微节流，避免把事件循环压满
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
  
  return { 'light_timeseries.csv': csv };
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
