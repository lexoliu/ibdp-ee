package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/mux"
)

type ServerState struct {
	counter  int64
	memory   [][]byte
	cache    map[string]interface{}
	mu       sync.RWMutex
}

// Helper type alias for compatibility with c0_tests.go
type AppState = ServerState

// Helper functions for c0_tests.go compatibility
func getQueryParamInt(r *http.Request, param string, defaultValue int) int {
	if val := r.URL.Query().Get(param); val != "" {
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return defaultValue
}

func getQueryParamBool(r *http.Request, param string, defaultValue bool) bool {
	if val := r.URL.Query().Get(param); val != "" {
		if b, err := strconv.ParseBool(val); err == nil {
			return b
		}
	}
	return defaultValue
}

func writeJSONResponse(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

// Adapter to convert c0 handlers to our expected signature
func adaptHandler(state *ServerState, handler func(*AppState, http.ResponseWriter, *http.Request)) func(*ServerState, http.ResponseWriter, *http.Request) error {
	return func(s *ServerState, w http.ResponseWriter, r *http.Request) error {
		handler(s, w, r)
		return nil
	}
}

// makeHandler wraps handlers to provide common functionality
func makeHandler(state *ServerState, handler func(*ServerState, http.ResponseWriter, *http.Request) error) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		if err := handler(state, w, r); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		
		duration := time.Since(start)
		w.Header().Set("X-Duration", duration.String())
	}
}

func main() {
	state := &ServerState{
		memory: make([][]byte, 0),
		cache:  make(map[string]interface{}),
	}

	r := mux.NewRouter()

	// C0 Tests (Pure Computation) - Direct from c0_tests.go
	r.HandleFunc("/compute/c0a", makeHandler(state, adaptHandler(state, c0aVectorDotProduct))).Methods("GET")
	r.HandleFunc("/compute/c0b", makeHandler(state, adaptHandler(state, c0bVectorizableVsBranchy))).Methods("GET")
	r.HandleFunc("/compute/c0c", makeHandler(state, adaptHandler(state, c0cFFTConvolution))).Methods("GET")
	r.HandleFunc("/compute/c0d", makeHandler(state, adaptHandler(state, c0dAllocationStrategy))).Methods("GET")
	
	// Health check
	r.HandleFunc("/health", makeHandler(state, func(s *ServerState, w http.ResponseWriter, r *http.Request) error {
		fmt.Fprintf(w, "Go Server - OK")
		return nil
	})).Methods("GET")

	fmt.Println("Go server starting on port 8081...")
	log.Fatal(http.ListenAndServe(":8081", r))
}