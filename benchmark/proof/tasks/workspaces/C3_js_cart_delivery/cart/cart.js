const { discounted } = require('./pricing');

// items: [{ name, price, qty }]; discountPercent applies to every item.
function total(items, discountPercent = 0) {
  return items.reduce((sum, it) => sum + discounted(it.price, discountPercent) * it.qty, 0);
}
function count(items) { return items.reduce((n, it) => n + it.qty, 0); }
module.exports = { total, count };
