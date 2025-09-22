package com.example.minservice;

import org.json.JSONObject;
import org.json.XML;
import org.springframework.http.MediaType;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyExtractors;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

@Component
public class Handlers {

  private final KVEngine kv;

  public Handlers(KVEngine kv) {
    this.kv = kv;
  }

  public Mono<ServerResponse> echo(ServerRequest req) {
    return req.bodyToMono(byte[].class)
        .flatMap(bytes -> ServerResponse.ok()
            .contentType(MediaType.APPLICATION_OCTET_STREAM)
            .bodyValue(bytes));
  }

  public Mono<ServerResponse> json(ServerRequest req) {
    return req.bodyToMono(Model.class)
        .flatMap(m -> ServerResponse.ok()
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(m));
  }

  public Mono<ServerResponse> json2xml(ServerRequest req) {
    return req.bodyToMono(String.class).flatMap(body -> {
      try {
        Object json = new org.json.JSONTokener(body).nextValue();
        String xml;
        if (json instanceof org.json.JSONArray arr) {
          JSONObject wrap = new JSONObject(Map.of("root", arr));
          xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + XML.toString(wrap);
        } else if (json instanceof JSONObject obj) {
          JSONObject wrap = new JSONObject(Map.of("root", obj));
          xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + XML.toString(wrap);
        } else {
          JSONObject wrap = new JSONObject(Map.of("root", json));
          xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + XML.toString(wrap);
        }
        return ServerResponse.ok().contentType(MediaType.APPLICATION_XML).bodyValue(xml);
      } catch (Exception e) {
        return ServerResponse.badRequest().bodyValue("json2xml failed");
      }
    });
  }

  public Mono<ServerResponse> isPrime(ServerRequest req) {
    return req.bodyToMono(String.class)
        .defaultIfEmpty("")
        .map(String::trim)
        .flatMap(s -> {
          try {
            if (s.isEmpty())
              return Mono.just("Invalid input");
            BigInteger n = new BigInteger(s);
            if (n.signum() < 0 || n.bitLength() > 64)
              return Mono.just("Invalid input");
            boolean prime = isPrimeUint64(n.longValue());
            return Mono.just(prime ? "true" : "false");
          } catch (Exception e) {
            return Mono.just("Invalid input");
          }
        })
        .flatMap(out -> ServerResponse.ok().contentType(MediaType.TEXT_PLAIN).bodyValue(out));
  }

  private static final List<Long> BASES = List.of(2L, 325L, 9375L, 28178L, 450775L, 9780504L, 1795265022L);
  private static final long[] SMALL_PRIMES = { 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37 };

  private boolean isPrimeUint64(long val) {
    if (val < 2)
      return false;
    long n = val;
    for (long p : SMALL_PRIMES) {
      if (n == p)
        return true;
      if (n % p == 0)
        return n == p;
    }
    if ((n & 1L) == 0L)
      return false;

    BigInteger N = toUnsignedBig(n);
    BigInteger one = BigInteger.ONE;
    BigInteger Nm1 = N.subtract(one);
    BigInteger d = Nm1;
    int s = 0;
    while (d.and(one).equals(BigInteger.ZERO)) {
      d = d.shiftRight(1);
      s++;
    }

    for (long a : BASES) {
      long amod = Long.remainderUnsigned(a, n);
      if (amod == 0L)
        continue;
      BigInteger A = BigInteger.valueOf(a).mod(N);
      BigInteger x = A.modPow(d, N);
      if (x.equals(one) || x.equals(Nm1))
        continue;
      boolean composite = true;
      for (int i = 1; i < s; i++) {
        x = x.multiply(x).mod(N);
        if (x.equals(Nm1)) {
          composite = false;
          break;
        }
      }
      if (composite)
        return false;
    }
    return true;
  }

  private static BigInteger toUnsignedBig(long x) {
    if (x >= 0)
      return BigInteger.valueOf(x);
    return BigInteger.valueOf(x & 0x7fffffffffffffffL).setBit(63);
  }

  public Mono<ServerResponse> kvGet(ServerRequest req) {
    String id = req.pathVariable("id");
    String v = kv.get(id);
    String out = (v != null) ? ("Found: " + v) : "Not found";
    return ServerResponse.ok().contentType(MediaType.TEXT_PLAIN).bodyValue(out);
  }

  public Mono<ServerResponse> kvSet(ServerRequest req) {
    String id = req.pathVariable("id");
    return DataBufferUtils.join(req.body(BodyExtractors.toDataBuffers()))
        .map(buffer -> {
          try {
            byte[] bytes = new byte[buffer.readableByteCount()];
            buffer.read(bytes);
            return bytes;
          } finally {
            DataBufferUtils.release(buffer);
          }
        })
        .defaultIfEmpty(new byte[0])
        .flatMap(bytes -> {
          kv.set(id, new String(bytes, StandardCharsets.UTF_8));
          return ServerResponse.ok().contentType(MediaType.TEXT_PLAIN)
              .bodyValue("Set value for " + id);
        });
  }

  public Mono<ServerResponse> kvDelete(ServerRequest req) {
    String id = req.pathVariable("id");
    kv.delete(id);
    return ServerResponse.ok().contentType(MediaType.TEXT_PLAIN)
        .bodyValue("Deleted value for " + id);
  }
}
