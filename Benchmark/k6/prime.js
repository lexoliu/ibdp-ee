import http from "k6/http";

export let options = { vus: 50, duration: "30s" };

export default function () {
  // 生成大数 (1e12 ~ 1e18)
  let n = Math.floor(Math.random() * 1e6) + 1e12;
  http.get(`http://127.0.0.1:8080/prime/${n}`);
}
