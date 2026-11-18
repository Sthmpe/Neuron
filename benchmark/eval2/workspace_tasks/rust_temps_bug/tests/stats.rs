use temps::{longest_streak_above, mean, median};

#[test]
fn mean_of_values() {
    assert_eq!(mean(&[20.0, 22.0, 24.0]), 22.0);
}

#[test]
fn median_odd_and_even() {
    assert_eq!(median(&[31.0, 25.0, 28.0]), 28.0);
    assert_eq!(median(&[30.0, 24.0, 26.0, 28.0]), 27.0);
}

#[test]
fn streak_above() {
    assert_eq!(longest_streak_above(&[30.0, 33.0, 34.0, 29.0, 35.0, 36.0, 37.0], 32.0), 3);
}
