mod echo;
mod file;

use clap::{Parser, Subcommand};
use std::net::SocketAddr;

/// CLI entry point
#[derive(Parser)]
#[command(name = "server", version, about = "A multipurpose HTTP server")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Serve static files from a directory
    Serve {
        /// Directory to serve
        path: String,

        /// Address to bind to
        #[arg(short, long, default_value = "127.0.0.1:8080")]
        addr: SocketAddr,
    },

    /// Echo POST requests at /echo
    Echo {
        /// Address to bind to
        #[arg(short, long, default_value = "127.0.0.1:8080")]
        addr: SocketAddr,
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Serve { path, addr } => {
            file::serve(path.into(), addr).await;
        }
        Commands::Echo { addr } => {
            echo::echo(addr).await;
        }
    }
}
