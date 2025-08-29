package com.example.minservice;

import java.util.concurrent.ConcurrentHashMap;

public class KVEngine {
  private final ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();

  public String get(String key) { return map.get(key); }
  public void set(String key, String value) { map.put(key, value); }
  public void delete(String key) { map.remove(key); }
}
