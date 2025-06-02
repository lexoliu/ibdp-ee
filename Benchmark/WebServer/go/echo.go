package main

import (
	"fmt"
	"io"
	"net/http"

	"github.com/spf13/cobra"
)

var echoCmd = &cobra.Command{
	Use:   "echo",
	Short: "Start an echo server at /echo",
	Run: func(cmd *cobra.Command, args []string) {
		addr, _ := cmd.Flags().GetString("addr")

		http.HandleFunc("/echo", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != http.MethodPost {
				http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
				return
			}
			body, err := io.ReadAll(r.Body)
			if err != nil {
				http.Error(w, "Failed to read body", http.StatusBadRequest)
				return
			}
			fmt.Printf("📩 Received %d bytes\n", len(body))
			w.Header().Set("Content-Type", "application/octet-stream")
			w.Write(body)
		})

		fmt.Println("🔁 Echo server listening at http://" + addr + "/echo")
		if err := http.ListenAndServe(addr, nil); err != nil {
			fmt.Println("Server error:", err)
		}
	},
}

func init() {
	echoCmd.Flags().StringP("addr", "a", "127.0.0.1:8080", "Address to bind")
}
