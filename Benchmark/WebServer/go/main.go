package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "server",
	Short: "A multipurpose HTTP server",
}

func main() {
	rootCmd.AddCommand(serveCmd)
	rootCmd.AddCommand(echoCmd)

	if err := rootCmd.Execute(); err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}
}
