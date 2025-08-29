import http from "k6/http";

let counter = 0;

function fnv1aHash(x) {
  let hash = 2166136261;
  const prime = 16777619;
  const s = x.toString();
  for (let i = 0; i < s.length; i++) {
    hash ^= s.charCodeAt(i);
    hash = (hash * prime) >>> 0; // 保持32位
  }
  return hash.toString();
}

export let options = { vus: 50, duration: "120s" };

export default function () {
  counter++;
  let key = fnv1aHash(counter);
  let value = "val" + key;
  http.post(`http://127.0.0.1:8080/kv/${key}`, value, {
    headers: { "Content-Type": "text/plain" },
  });
}
