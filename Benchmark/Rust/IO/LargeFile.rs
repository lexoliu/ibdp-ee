use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::time::Instant;

const FILE_PATH: &str = "../../large_file.bin";
const FILE_SIZE: usize = 1_000_000_000; // 1GB

fn write_large_file() {
    let start = Instant::now();
    let mut file = BufWriter::new(File::create(FILE_PATH).unwrap());
    let buffer = vec![0u8; 8192];

    for _ in 0..(FILE_SIZE / buffer.len()) {
        file.write_all(&buffer).unwrap();
    }

    file.flush().unwrap();
    println!("Sequential write time: {:?}", start.elapsed());
}

fn read_large_file() {
    let start = Instant::now();
    let mut file = BufReader::new(File::open(FILE_PATH).unwrap());
    let mut buffer = vec![0u8; 8192];

    while file.read(&mut buffer).unwrap() > 0 {}

    println!("Sequential read time: {:?}", start.elapsed());
}

fn main() {
    write_large_file();
    read_large_file();
}
