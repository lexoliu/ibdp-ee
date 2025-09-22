pub fn is_prime(n: u64) -> bool {
    // 小数 & 偶数快速处理
    const SMALL_PRIMES: [u64; 12] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    if n < 2 {
        return false;
    }
    for &p in &SMALL_PRIMES {
        if n == p {
            return true;
        }
        if n.is_multiple_of(p) {
            return n == p;
        }
    }
    if n.is_multiple_of(2) {
        return false;
    }

    // n-1 = d * 2^s
    let (mut d, mut s) = (n - 1, 0u32);
    while d & 1 == 0 {
        d >>= 1;
        s += 1;
    }

    // 64位确定性底数集合
    const BASES: [u64; 7] = [2, 325, 9375, 28178, 450775, 9780504, 1795265022];

    #[inline]
    fn mul_mod(a: u128, b: u128, m: u128) -> u128 {
        (a * b) % m
    }

    #[inline]
    fn pow_mod(mut a: u128, mut e: u128, m: u128) -> u128 {
        let mut r: u128 = 1;
        while e > 0 {
            if e & 1 == 1 {
                r = mul_mod(r, a, m);
            }
            a = mul_mod(a, a, m);
            e >>= 1;
        }
        r
    }

    'outer: for &a in &BASES {
        if a % n == 0 {
            continue;
        } // 底数等于n的倍数可跳过
        let mut x = pow_mod((a % n) as u128, d as u128, n as u128);
        if x == 1 || x == (n as u128 - 1) {
            continue 'outer;
        }
        for _ in 1..s {
            x = mul_mod(x, x, n as u128);
            if x == (n as u128 - 1) {
                continue 'outer;
            }
        }
        return false; // 此底数下为合数
    }
    true
}

pub async fn handler(body: String) -> String {
    let trimmed = body.trim();
    if trimmed.is_empty() {
        return "Invalid input".to_string();
    }
    match trimmed.parse::<u64>() {
        Ok(num) => {
            if is_prime(num) {
                "true".to_string()
            } else {
                "false".to_string()
            }
        }
        Err(_) => "Invalid input".to_string(),
    }
}
