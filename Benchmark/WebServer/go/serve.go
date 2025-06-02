package main

import (
	"fmt"
	"net/http"
	"os"

	"github.com/spf13/cobra"
)

var serveCmd = &cobra.Command{
	Use:   "serve <path>",
	Short: "Serve static files from a directory",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		dir := args[0]
		if stat, err := os.Stat(dir); err != nil || !stat.IsDir() {
			fmt.Println("❌ Directory does not exist or is not valid:", dir)
			os.Exit(1)
		}

		addr, _ := cmd.Flags().GetString("addr")
		fmt.Println("📁 Serving directory:", dir)
		fmt.Println("🌐 Listening at http://" + addr + "/")

		http.Handle("/", http.FileServer(http.Dir(dir)))
		if err := http.ListenAndServe(addr, nil); err != nil {
			fmt.Println("Server error:", err)
		}
	},
}

func init() {
	serveCmd.Flags().StringP("addr", "a", "127.0.0.1:8080", "Address to bind")
}
