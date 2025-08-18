use axum::{
    extract::{Path, Query, State},
    response::{Html, Json},
    http::StatusCode,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Instant;
use crate::AppState;

#[derive(Serialize)]
pub struct MacroResponse {
    data: serde_json::Value,
    duration_ms: f64,
    endpoint: String,
}

#[derive(Deserialize)]
pub struct EchoQuery {
    msg: Option<String>,
    repeat: Option<usize>,
}

/// C1: Echo (minimal framework path)
pub async fn c1_echo(Query(params): Query<EchoQuery>) -> Json<MacroResponse> {
    let start = Instant::now();
    
    let message = params.msg.unwrap_or_else(|| "Hello, World!".to_string());
    let repeat = params.repeat.unwrap_or(1);
    
    let echoed = if repeat == 1 {
        message
    } else {
        (0..repeat).map(|i| format!("{} {}", message, i)).collect::<Vec<_>>().join(" | ")
    };
    
    let duration = start.elapsed();
    
    Json(MacroResponse {
        data: serde_json::json!({
            "echo": echoed,
            "length": echoed.len(),
            "repeat_count": repeat
        }),
        duration_ms: duration.as_secs_f64() * 1000.0,
        endpoint: "echo".to_string(),
    })
}

#[derive(Deserialize)]
pub struct StaticQuery {
    size: Option<usize>,
}

/// C2: Static file (simulated)
pub async fn c2_static_file(
    Path(path): Path<String>,
    Query(params): Query<StaticQuery>,
) -> Result<Html<String>, StatusCode> {
    let start = Instant::now();
    
    let size = params.size.unwrap_or(1024);
    
    // Simulate static file content
    let content = match path.as_str() {
        "index.html" => {
            let body_content = "Lorem ipsum ".repeat(size / 12);
            format!(
                r#"<!DOCTYPE html>
<html>
<head><title>Static Page</title></head>
<body>
<h1>Static Content</h1>
<p>{}</p>
<p>Generated at: {:?}</p>
</body>
</html>"#,
                body_content,
                start
            )
        }
        "data.json" => {
            let data: Vec<serde_json::Value> = (0..size / 50)
                .map(|i| {
                    serde_json::json!({
                        "id": i,
                        "name": format!("item_{}", i),
                        "value": i as f64 * 0.1
                    })
                })
                .collect();
            serde_json::to_string_pretty(&data).unwrap()
        }
        _ => "File not found".to_string(),
    };
    
    Ok(Html(content))
}

#[derive(Deserialize)]
pub struct JsonApiQuery {
    items: Option<usize>,
    nested: Option<bool>,
}

#[derive(Serialize)]
struct ApiItem {
    id: u32,
    name: String,
    data: Vec<f64>,
    metadata: HashMap<String, serde_json::Value>,
    nested: Option<Box<ApiItem>>,
}

/// C3: JSON API (complex serialization)
pub async fn c3_json_api(Query(params): Query<JsonApiQuery>) -> Json<MacroResponse> {
    let start = Instant::now();
    
    let item_count = params.items.unwrap_or(100);
    let include_nested = params.nested.unwrap_or(true);
    
    let items: Vec<ApiItem> = (0..item_count)
        .map(|i| {
            let mut metadata = HashMap::new();
            metadata.insert("category".to_string(), serde_json::json!(format!("cat_{}", i % 5)));
            metadata.insert("tags".to_string(), serde_json::json!(vec![
                format!("tag_{}", i % 3),
                format!("tag_{}", (i + 1) % 3),
            ]));
            metadata.insert("config".to_string(), serde_json::json!({
                "enabled": i % 2 == 0,
                "priority": i % 10,
                "settings": {
                    "timeout": 1000 + (i * 100),
                    "retries": 3
                }
            }));
            
            ApiItem {
                id: i as u32,
                name: format!("api_item_{}", i),
                data: (0..20).map(|j| (i + j) as f64 * 0.1).collect(),
                metadata,
                nested: if include_nested && i % 5 == 0 {
                    Some(Box::new(ApiItem {
                        id: (i + 1000) as u32,
                        name: format!("nested_item_{}", i),
                        data: (0..5).map(|j| (i + j) as f64 * 0.01).collect(),
                        metadata: HashMap::new(),
                        nested: None,
                    }))
                } else {
                    None
                },
            }
        })
        .collect();
    
    let duration = start.elapsed();
    
    Json(MacroResponse {
        data: serde_json::json!({
            "items": items,
            "total_count": item_count,
            "has_nested": include_nested,
        }),
        duration_ms: duration.as_secs_f64() * 1000.0,
        endpoint: "json_api".to_string(),
    })
}

#[derive(Deserialize)]
pub struct TemplateQuery {
    name: Option<String>,
    items: Option<usize>,
    theme: Option<String>,
}

/// C4: Template rendering (server-side HTML generation)
pub async fn c4_template_render(Query(params): Query<TemplateQuery>) -> Html<String> {
    let start = Instant::now();
    
    let name = params.name.unwrap_or_else(|| "User".to_string());
    let item_count = params.items.unwrap_or(50);
    let theme = params.theme.unwrap_or_else(|| "default".to_string());
    
    // Generate data for template
    let items: Vec<serde_json::Value> = (0..item_count)
        .map(|i| {
            serde_json::json!({
                "id": i,
                "title": format!("Article {}", i + 1),
                "content": format!("This is the content of article {}. {}", 
                    i + 1, 
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ".repeat(3)
                ),
                "author": format!("Author {}", (i % 5) + 1),
                "date": format!("2024-{:02}-{:02}", (i % 12) + 1, (i % 28) + 1),
                "tags": (0..(i % 5) + 1).map(|j| format!("tag{}", j + 1)).collect::<Vec<_>>(),
                "views": (i + 1) * 42,
                "featured": i % 7 == 0,
            })
        })
        .collect();
    
    let duration_ms = start.elapsed().as_secs_f64() * 1000.0;
    
    // Simple template rendering (without template engine for this example)
    let html = format!(
        r#"<!DOCTYPE html>
<html>
<head>
    <title>Blog - {}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: {}; }}
        .header {{ background: #333; color: white; padding: 20px; margin-bottom: 30px; }}
        .article {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; background: white; }}
        .featured {{ border-left: 5px solid #007acc; }}
        .tags {{ color: #666; font-size: 0.9em; }}
        .meta {{ color: #888; font-size: 0.8em; }}
        .footer {{ margin-top: 40px; padding: 20px; background: #f5f5f5; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome to {}'s Blog</h1>
        <p>Showing {} articles (rendered in {:.2}ms)</p>
    </div>
    
    <div class="content">
        {}
    </div>
    
    <div class="footer">
        <p>Theme: {} | Total articles: {} | Performance: {:.2}ms</p>
    </div>
</body>
</html>"#,
        name,
        if theme == "dark" { "#2d2d2d" } else { "#f9f9f9" },
        name,
        item_count,
        duration_ms,
        items
            .iter()
            .map(|item| {
                format!(
                    r#"<div class="article{}">
                        <h2>{}</h2>
                        <div class="meta">By {} | {} | {} views</div>
                        <p>{}</p>
                        <div class="tags">Tags: {}</div>
                    </div>"#,
                    if item["featured"].as_bool().unwrap_or(false) { " featured" } else { "" },
                    item["title"].as_str().unwrap(),
                    item["author"].as_str().unwrap(),
                    item["date"].as_str().unwrap(),
                    item["views"].as_u64().unwrap(),
                    item["content"].as_str().unwrap(),
                    item["tags"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(|t| t.as_str().unwrap())
                        .collect::<Vec<_>>()
                        .join(", ")
                )
            })
            .collect::<Vec<_>>()
            .join("\n"),
        theme,
        item_count,
        duration_ms
    );
    
    Html(html)
}

#[derive(Deserialize)]
pub struct DbQuery {
    id: Option<u32>,
    limit: Option<usize>,
}

/// C5: Database query (simulated)
pub async fn c5_db_query(
    State(state): State<AppState>,
    Query(params): Query<DbQuery>,
) -> Json<MacroResponse> {
    let start = Instant::now();
    
    let user_id = params.id.unwrap_or(1);
    let limit = params.limit.unwrap_or(10);
    
    // Simulate database operations with in-memory store
    let mut store = state.data_store.lock();
    
    // Simulate complex queries and joins
    let user_data = serde_json::json!({
        "id": user_id,
        "name": format!("User {}", user_id),
        "email": format!("user{}@example.com", user_id),
        "profile": {
            "age": 20 + (user_id % 50),
            "location": format!("City {}", user_id % 10),
            "preferences": (0..5).map(|i| format!("pref_{}", (user_id + i) % 20)).collect::<Vec<_>>(),
        }
    });
    
    // Simulate related data fetching
    let posts: Vec<serde_json::Value> = (0..limit)
        .map(|i| {
            serde_json::json!({
                "id": user_id * 1000 + i as u32,
                "title": format!("Post {} by User {}", i + 1, user_id),
                "content": format!("Content of post {}. {}", i + 1, "Sample text ".repeat(20)),
                "created_at": format!("2024-01-{:02}", (i % 30) + 1),
                "comments_count": (i * 3) % 25,
                "likes": (user_id * (i as u32 + 1)) % 100,
            })
        })
        .collect();
    
    // Cache some data in the store (simulate database caching)
    let cache_key = format!("user_{}", user_id);
    store.insert(cache_key, serde_json::to_vec(&user_data).unwrap());
    
    let duration = start.elapsed();
    
    Json(MacroResponse {
        data: serde_json::json!({
            "user": user_data,
            "posts": posts,
            "cache_info": {
                "cached_keys": store.len(),
                "cache_hit": false, // First time
            }
        }),
        duration_ms: duration.as_secs_f64() * 1000.0,
        endpoint: "db_query".to_string(),
    })
}
