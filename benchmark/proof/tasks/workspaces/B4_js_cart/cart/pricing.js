// Price after a percentage discount, rounded to whole naira. percent is like 10 for 10%.
function discounted(price, percent) {
  return Math.round(price - price * percent);
}
module.exports = { discounted };
