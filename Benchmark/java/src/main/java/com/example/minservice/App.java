package com.example.minservice;

import java.util.Locale;

import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class App {
  private static boolean loggingEnabled() {
    String value = System.getenv("SERVER_LOG");
    if (value == null)
      return false;
    String lowered = value.trim().toLowerCase(Locale.ROOT);
    if (lowered.isEmpty())
      return false;
    return lowered.equals("1") || lowered.equals("true") || lowered.equals("yes") || lowered.equals("on");
  }

  public static void main(String[] args) {
    SpringApplication app = new SpringApplication(App.class);
    if (!loggingEnabled()) {
      app.setBannerMode(Banner.Mode.OFF);
      app.setLogStartupInfo(false);
      System.setProperty("logging.level.root", "ERROR");
      System.setProperty("logging.level.org.springframework", "ERROR");
      System.setProperty("logging.level.org.springframework.web", "ERROR");
      System.setProperty("logging.level.reactor.netty", "ERROR");
      System.setProperty("reactor.netty.http.server.accessLogEnabled", "false");
    }
    app.run(args);
  }
}
