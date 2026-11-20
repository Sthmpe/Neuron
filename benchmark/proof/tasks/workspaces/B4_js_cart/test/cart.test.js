const assert = require('assert');
const { total, count } = require('../cart/cart');
const items = [{ name: 'rice', price: 42000, qty: 2 }, { name: 'oil', price: 9000, qty: 1 }];
assert.strictEqual(count(items), 3);
assert.strictEqual(total(items), 93000);
assert.strictEqual(total(items, 10), 83700);
console.log('cart tests passed');
