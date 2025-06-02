use bytes::Bytes;
use warp::{Filter, http::Response};

pub async fn echo(addr: std::net::SocketAddr) {
    println!("🔁 Echo server active at http://{addr}/echo");

    let route = warp::path("echo")
        .and(warp::post())
        .and(warp::body::bytes())
        .map(|body: Bytes| {
            Response::builder()
                .header("Content-Type", "application/octet-stream")
                .body(body)
                .unwrap()
        });

    warp::serve(route).run(addr).await;
}
