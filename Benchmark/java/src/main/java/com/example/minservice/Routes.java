package com.example.minservice;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.server.*;

import static org.springframework.web.reactive.function.server.RequestPredicates.accept;

@Configuration
public class Routes {

  @Bean
  public RouterFunction<ServerResponse> router(Handlers h) {
    return RouterFunctions.route()
        .POST("/echo", accept(MediaType.ALL), h::echo)
        .POST("/json", accept(MediaType.APPLICATION_JSON), h::json)
        .POST("/json2xml", accept(MediaType.APPLICATION_JSON), h::json2xml)
        .POST("/is_prime", accept(MediaType.ALL), h::isPrime)
        .path("/kv", kv -> kv
            .GET("/get/{id}", h::kvGet)
            .POST("/set/{id}", h::kvSet)
            .DELETE("/delete/{id}", h::kvDelete))
        .build();
  }

  @Bean
  public KVEngine kvEngine() {
    return new KVEngine();
  }
}
