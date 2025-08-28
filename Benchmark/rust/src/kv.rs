use std::{
    collections::BTreeMap,
    sync::{Arc, RwLock},
};

use axum::extract::{Path, State};

pub async fn get(Path(id): Path<String>, State(engine): State<Engine>) -> String {
    let value = engine.get(&id);
    match value {
        Some(v) => format!("Found: {}", v),
        None => "Not found".to_string(),
    }
}

pub async fn post(Path(id): Path<String>, State(engine): State<Engine>, content: String) -> String {
    engine.set(id.clone(), content);
    format!("Set value for {}", id)
}

pub async fn delete(Path(id): Path<String>, State(engine): State<Engine>) -> String {
    engine.delete(&id);
    format!("Deleted value for {}", id)
}

#[derive(Debug, Clone)]
pub struct Engine {
    budget: Arc<RwLock<Budget>>,
}

#[derive(Debug)]
struct Budget {
    map: BTreeMap<String, String>,
}

impl Budget {
    pub fn new() -> Self {
        Self {
            map: BTreeMap::new(),
        }
    }

    pub fn get(&self, key: &str) -> Option<String> {
        self.map.get(key).cloned()
    }

    pub fn set(&mut self, key: String, value: String) {
        self.map.insert(key, value);
    }

    pub fn delete(&mut self, key: &str) -> Option<String> {
        self.map.remove(key)
    }
}

impl Engine {
    pub fn new() -> Self {
        Self {
            budget: Arc::new(RwLock::new(Budget::new())),
        }
    }

    pub fn get(&self, key: &str) -> Option<String> {
        let budget = self.budget.read().unwrap();
        budget.get(key)
    }

    pub fn set(&self, key: String, value: String) {
        let mut budget = self.budget.write().unwrap();
        budget.set(key, value);
    }

    pub fn delete(&self, key: &str) -> Option<String> {
        let mut budget = self.budget.write().unwrap();
        budget.delete(key)
    }
}
