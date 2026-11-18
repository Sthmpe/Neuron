//! Temperature statistics for a weather station (degrees Celsius).

pub fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

pub fn median(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut v = values.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        v[n / 2]
    }
}

pub fn longest_streak_above(values: &[f64], threshold: f64) -> usize {
    let mut best = 0;
    let mut run = 0;
    for &x in values {
        if x > threshold {
            run += 1;
            if run > best {
                best = run;
            }
        } else {
            run = 0;
        }
    }
    best
}
