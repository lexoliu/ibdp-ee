import http from "k6/http";

export let options = { vus: 50, duration: "30s" };

export default function () {
  let key = Math.floor(Math.random() * 1000000).toString();
  http.get(`http://127.0.0.1:8080/kv/${key}`);
}
