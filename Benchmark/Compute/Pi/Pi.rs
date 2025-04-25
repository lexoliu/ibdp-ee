use std::env;

fn calculate_pi(terms: usize) -> f64 {
    let mut pi = 0.0;
    for k in 0..terms {
        if k % 2 == 0 {
            pi += 1.0 / (2 * k + 1) as f64;
        } else {
            pi -= 1.0 / (2 * k + 1) as f64;
        }
    }
    4.0 * pi
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert!(args.len() == 2, "Usage: pi <terms>");
    let terms = args[1].parse::<usize>().expect("Invalid integer");
    let pi = calculate_pi(terms);
    println!("{:.12}", pi);
}
