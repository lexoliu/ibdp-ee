import http from 'k6/http';
import { check, sleep } from 'k6';

// 从环境读取并发/时长（也支持 CLI --vus/--duration）
export const options = {
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || 'http://127.0.0.1:8080';

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
  const which = pick();
  let res;

  if (which === 'echo') {
    const body = 'hello ' + Math.random();
    res = http.post(`${base}/echo`, body);
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
    });
  }

  check(res, { 'status 200': (r) => r.status === 200 });
  // 轻微节流，避免把事件循环压满
  sleep(0.001);
}
