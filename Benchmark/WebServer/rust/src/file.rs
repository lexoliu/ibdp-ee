use std::net::SocketAddr;
use std::path::PathBuf;

pub async fn serve(path: PathBuf, addr: SocketAddr) {
    if !path.exists() || !path.is_dir() {
        eprintln!("❌ Directory not found or invalid: {path:?}");
        std::process::exit(1);
    }

    println!("📁 Serving static files from: {path:?}");
    println!("🌐 Listening on http://{addr}/");

    let route = warp::fs::dir(path);
    warp::serve(route).run(addr).await;
}
