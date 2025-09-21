import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  thresholds: { http_req_failed: ['rate<0.01'] },
};

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || 'http://127.0.0.1:8080';

export default function () {
  // 80% get，18% set，2% delete
  const id = `${__VU}-${__ITER % 100000}`;
  const r = Math.random();

  if (r < 0.80) {
    const res = http.get(`${base}/kv/get/${id}`, {
      tags: {
        name: 'kv-get',
        url: '/kv/get/:id',
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  } else if (r < 0.98) {
    const res = http.post(`${base}/kv/set/${id}`, 'v' + Math.random(), {
      tags: {
        name: 'kv-set',
        url: '/kv/set/:id',
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  } else {
    const res = http.del(`${base}/kv/delete/${id}`, null, {
      tags: {
        name: 'kv-delete',
        url: '/kv/delete/:id',
      },
    });
    check(res, { '200': (r) => r.status === 200 });
  }
  sleep(0.001);
}
