use std::sync::Arc;

use axum::{Json, extract::State};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct Article {
    title: String,
    content: String,
    author: String,
}

#[derive(Clone)]
pub struct Engine {
    template: Arc<liquid::Template>,
}

impl Engine {
    pub fn new() -> Self {
        let template = liquid::ParserBuilder::with_stdlib()
            .build()
            .unwrap()
            .parse("Liquid! {{num | minus: 2}}")
            .unwrap();

        Self {
            template: Arc::new(template),
        }
    }

    pub fn render(&self, article: &Article) -> String {
        let context = liquid::object!({
            "title": &article.title,
            "content": &article.content,
            "author": &article.author,
            "num": 10,
        });
        self.template.render(&context).unwrap()
    }
}

pub async fn handler(State(engine): State<Engine>, article: Json<Article>) -> String {
    engine.render(&article)
}
