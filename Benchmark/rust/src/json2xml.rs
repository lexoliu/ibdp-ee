use axum::{
    body::Body,
    http::{header, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde_json::{Map, Number, Value};

pub async fn handler(Json(input): Json<Value>) -> Response {
    match json_to_xml(&input) {
        Ok(xml) => {
            let mut response = Response::new(Body::from(xml));
            response.headers_mut().insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("application/xml; charset=utf-8"),
            );
            response
        }
        Err(_) => (
            StatusCode::BAD_REQUEST,
            "json2xml failed",
        )
            .into_response(),
    }
}

fn json_to_xml(value: &Value) -> Result<String, ConvertError> {
    let mut output = String::from(r#"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"#);
    output.push('\n');
    write_element(&mut output, "root", value, 0)?;
    Ok(output)
}

#[derive(Debug)]
struct ConvertError;

type ConvertResult<T> = Result<T, ConvertError>;

const INDENT: &str = "  ";

fn write_element(output: &mut String, name: &str, value: &Value, depth: usize) -> ConvertResult<()> {
    match value {
        Value::Object(map) => write_object(output, name, map, depth),
        Value::Array(items) => write_array(output, name, items, depth),
        Value::Null => write_text_element(output, name, "", depth),
        Value::Bool(flag) => write_text_element(output, name, if *flag { "true" } else { "false" }, depth),
        Value::Number(number) => write_text_element(output, name, &format_number(number), depth),
        Value::String(text) => write_text_element(output, name, text, depth),
    }
}

fn write_object(output: &mut String, name: &str, map: &Map<String, Value>, depth: usize) -> ConvertResult<()> {
    push_indent(output, depth);
    output.push('<');
    output.push_str(name);
    output.push('>');
    if map.is_empty() {
        output.push_str("</");
        output.push_str(name);
        output.push_str(">\n");
        return Ok(());
    }
    output.push('\n');
    for (key, child) in map {
        write_element(output, key, child, depth + 1)?;
    }
    push_indent(output, depth);
    output.push_str("</");
    output.push_str(name);
    output.push_str(">\n");
    Ok(())
}

fn write_array(output: &mut String, name: &str, items: &[Value], depth: usize) -> ConvertResult<()> {
    push_indent(output, depth);
    output.push('<');
    output.push_str(name);
    output.push('>');
    if items.is_empty() {
        output.push_str("</");
        output.push_str(name);
        output.push_str(">\n");
        return Ok(());
    }
    output.push('\n');
    for item in items {
        write_element(output, "item", item, depth + 1)?;
    }
    push_indent(output, depth);
    output.push_str("</");
    output.push_str(name);
    output.push_str(">\n");
    Ok(())
}

fn write_text_element(output: &mut String, name: &str, text: &str, depth: usize) -> ConvertResult<()> {
    push_indent(output, depth);
    output.push('<');
    output.push_str(name);
    output.push('>');
    escape_xml(text, output);
    output.push_str("</");
    output.push_str(name);
    output.push_str(">\n");
    Ok(())
}

fn push_indent(output: &mut String, depth: usize) {
    for _ in 0..depth {
        output.push_str(INDENT);
    }
}

fn escape_xml(input: &str, output: &mut String) {
    for ch in input.chars() {
        match ch {
            '&' => output.push_str("&amp;"),
            '<' => output.push_str("&lt;"),
            '>' => output.push_str("&gt;"),
            '\"' => output.push_str("&quot;"),
            '\'' => output.push_str("&apos;"),
            _ => output.push(ch),
        }
    }
}

fn format_number(number: &Number) -> String {
    if let Some(i) = number.as_i64() {
        return i.to_string();
    }
    if let Some(u) = number.as_u64() {
        return u.to_string();
    }
    if let Some(f) = number.as_f64() {
        return format_float(f);
    }
    number.to_string()
}

fn format_float(value: f64) -> String {
    if !value.is_finite() {
        return value.to_string();
    }
    let mut s = format!("{value:.6}");
    if let Some(idx) = s.find('.') {
        let mut end = s.len();
        while end > idx + 1 && s.as_bytes()[end - 1] == b'0' {
            end -= 1;
        }
        if end > idx && s.as_bytes()[end - 1] == b'.' {
            end -= 1;
        }
        s.truncate(end);
    }
    if s == "-0" {
        s = "0".to_string();
    }
    s
}
