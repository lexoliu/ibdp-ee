import http from "k6/http";

export let options = { vus: 50, duration: "30s" };

const base = __ENV.K6_BASE_URL || __ENV.BASE_URL || "http://127.0.0.1:8080";

export default function () {
  let key = Math.floor(Math.random() * 1000000).toString();
  http.del(`${base}/kv/${key}`);
}
