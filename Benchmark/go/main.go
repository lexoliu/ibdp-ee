package main

import (
    "encoding/json"
    "encoding/xml"
    "io"
    "log"
    "math/big"
    "net/http"
    "os"
    "strings"
    "sync"
    "time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

/* =========================
   echo: POST /echo
   - Body 原样返回
   ========================= */

func echoHandler(w http.ResponseWriter, r *http.Request) {
	b, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "read body error", http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(b)
}

/* =========================
   json: POST /json
   - 读取JSON并原样返回相同结构
   ========================= */

type Model struct {
	Gender      string  `json:"gender"`
	ID          uint32  `json:"id"`
	Name        string  `json:"name"`
	Age         uint32  `json:"age"`
	Description string  `json:"description"`
	Height      float32 `json:"height"`
	Weight      float32 `json:"weight"`
}

func jsonHandler(w http.ResponseWriter, r *http.Request) {
	var m Model
	if err := json.NewDecoder(r.Body).Decode(&m); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	_ = json.NewEncoder(w).Encode(m)
}

/* =========================
   json2xml: POST /json2xml
   - 任意 JSON -> XML 字符串
   - 尽量接近 serde_xml_rs 的简单映射
   ========================= */

type xmlNode struct {
	XMLName xml.Name
	Nodes   []xmlNode  `xml:",any"`
	Content []byte     `xml:",innerxml"`
	Attr    []xml.Attr `xml:",attr"`
}

func json2xmlHandler(w http.ResponseWriter, r *http.Request) {
	var v any
	if err := json.NewDecoder(r.Body).Decode(&v); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	node, err := toXMLNode("root", v)
	if err != nil {
		http.Error(w, "json2xml failed", http.StatusBadRequest)
		return
	}
	buf, err := xml.MarshalIndent(node, "", "  ")
	if err != nil {
		http.Error(w, "xml marshal failed", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/xml; charset=utf-8")
	_, _ = w.Write(append([]byte(xml.Header), buf...))
}

func toXMLNode(name string, v any) (xmlNode, error) {
	switch t := v.(type) {
	case map[string]any:
		n := xmlNode{XMLName: xml.Name{Local: name}}
		for k, vv := range t {
			child, err := toXMLNode(k, vv)
			if err != nil {
				return n, err
			}
			n.Nodes = append(n.Nodes, child)
		}
		return n, nil
	case []any:
		n := xmlNode{XMLName: xml.Name{Local: name}}
		for _, item := range t {
			child, err := toXMLNode("item", item)
			if err != nil {
				return n, err
			}
			n.Nodes = append(n.Nodes, child)
		}
		return n, nil
	case string:
		return xmlNode{XMLName: xml.Name{Local: name}, Content: []byte(xmlEscape(t))}, nil
	case float64, bool, nil:
		return xmlNode{XMLName: xml.Name{Local: name}, Content: []byte(xmlEscape(toString(t)))}, nil
	default:
		// 兜底：再 JSON 一把 (结构体等)
		b, _ := json.Marshal(t)
		var m any
		if err := json.Unmarshal(b, &m); err != nil {
			return xmlNode{}, err
		}
		return toXMLNode(name, m)
	}
}

func xmlEscape(s string) string {
	var b strings.Builder
	_ = xml.EscapeText(&b, []byte(s))
	return b.String()
}

func toString(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case float64:
		// 去掉多余小数尾巴
		s := big.NewFloat(x).Text('f', 6)
		s = strings.TrimRight(s, "0")
		return strings.TrimRight(s, ".")
	case bool:
		if x {
			return "true"
		}
		return "false"
	case nil:
		return ""
	default:
		b, _ := json.Marshal(x)
		return string(b)
	}
}

func loggingEnabled() bool {
	if value, ok := os.LookupEnv("SERVER_LOG"); ok {
		value = strings.TrimSpace(strings.ToLower(value))
		if value == "" {
			return false
		}
		return value != "0" && value != "false" && value != "off" && value != "no"
	}
	return false
}

/* =========================
   kv: /kv/get/{id} /kv/set/{id} /kv/delete/{id}
   - 与 Rust 版同样的字符串响应
   ========================= */

type KVEngine struct {
	mu sync.RWMutex
	m  map[string]string
}

func NewKVEngine() *KVEngine { return &KVEngine{m: make(map[string]string)} }

func (e *KVEngine) Get(id string) (string, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	v, ok := e.m[id]
	return v, ok
}
func (e *KVEngine) Set(id, v string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.m[id] = v
}
func (e *KVEngine) Delete(id string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	delete(e.m, id)
}

func kvGetHandler(kv *KVEngine) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		if v, ok := kv.Get(id); ok {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("Found: " + v))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("Not found"))
	}
}
func kvSetHandler(kv *KVEngine) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		b, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "read body error", http.StatusBadRequest)
			return
		}
		kv.Set(id, string(b))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("Set value for " + id))
	}
}
func kvDeleteHandler(kv *KVEngine) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		kv.Delete(id)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("Deleted value for " + id))
	}
}

/* =========================
   is_prime: POST /is_prime
   - Body 是字符串数字；返回 "true"/"false"/"Invalid input"
   - 64 位确定性 Miller-Rabin（与 Rust 版一致的 bases）
   ========================= */

func isPrimeHandler(w http.ResponseWriter, r *http.Request) {
	b, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "read body error", http.StatusBadRequest)
		return
	}
	s := strings.TrimSpace(string(b))
	n := new(big.Int)
	if _, ok := n.SetString(s, 10); !ok || n.Sign() < 0 || n.BitLen() > 64 {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("Invalid input"))
		return
	}
	if isPrimeUint64(n.Uint64()) {
		_, _ = w.Write([]byte("true"))
	} else {
		_, _ = w.Write([]byte("false"))
	}
}

func isPrimeUint64(n uint64) bool {
	// 小数 & 偶数快速处理
	smallPrimes := []uint64{2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37}
	if n < 2 {
		return false
	}
	for _, p := range smallPrimes {
		if n == p {
			return true
		}
		if n%p == 0 {
			return n == p
		}
	}
	if n%2 == 0 {
		return false
	}

	// n-1 = d * 2^s
	d := new(big.Int).SetUint64(n - 1)
	s := 0
	for d.Bit(0) == 0 {
		d.Rsh(d, 1)
		s++
	}

	// 64位确定性底数集合
	bases := []uint64{2, 325, 9375, 28178, 450775, 9780504, 1795265022}
	N := new(big.Int).SetUint64(n)
	Nminus1 := new(big.Int).Sub(N, big.NewInt(1))
	for _, a := range bases {
		if a%uint64(n) == 0 {
			continue
		}
		// x = (a % n)^d % n
		x := new(big.Int).Exp(new(big.Int).Mod(new(big.Int).SetUint64(a), N), d, N)
		if x.Cmp(big.NewInt(1)) == 0 || x.Cmp(Nminus1) == 0 {
			continue
		}
		composite := true
		for i := 1; i < s; i++ {
			x.Mul(x, x)
			x.Mod(x, N)
			if x.Cmp(Nminus1) == 0 {
				composite = false
				break
			}
		}
		if composite {
			return false
		}
	}
	return true
}

/* =========================
   Router & Main
   ========================= */

func buildRouter(enableLogging bool) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	if enableLogging {
		r.Use(middleware.Logger)
	}
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(60 * time.Second))

	kv := NewKVEngine()

	r.Post("/echo", echoHandler)
	r.Post("/json", jsonHandler)
	r.Post("/json2xml", json2xmlHandler)
	r.Post("/is_prime", isPrimeHandler)

	r.Route("/kv", func(sr chi.Router) {
		sr.Get("/get/{id}", kvGetHandler(kv))
		sr.Post("/set/{id}", kvSetHandler(kv))
		sr.Delete("/delete/{id}", kvDeleteHandler(kv))
	})

	return r
}

func main() {
	logHost := os.Getenv("SERVER_HOST")
	if logHost == "" {
		logHost = "0.0.0.0"
	}
	port := os.Getenv("SERVER_PORT")
	if port == "" {
		port = "8080"
	}
	addr := logHost + ":" + port

	enableLogging := loggingEnabled()
	if !enableLogging {
		log.SetOutput(io.Discard)
	}
	if enableLogging {
		log.Printf("listening on http://%s\n", addr)
	}
	if err := http.ListenAndServe(addr, buildRouter(enableLogging)); err != nil {
		log.Fatal(err)
	}
}
