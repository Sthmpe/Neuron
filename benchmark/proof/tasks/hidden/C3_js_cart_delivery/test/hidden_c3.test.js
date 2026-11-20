const assert = require('assert');
const { deliveryFee } = require('../cart/delivery');
const { total } = require('../cart/cart');
assert.strictEqual(deliveryFee(19999), 1500);
assert.strictEqual(deliveryFee(20000), 0);
assert.strictEqual(total([{ name: 'soap', price: 500, qty: 3 }]), 3000);
assert.strictEqual(total([{ name: 'rice', price: 42000, qty: 2 }, { name: 'oil', price: 9000, qty: 1 }], 10), 83700);
assert.strictEqual(total([{ name: 'tea', price: 21000, qty: 1 }], 10), 18900 + 1500);
console.log('hidden ok');
