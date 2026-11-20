const assert = require('assert');
const { discounted } = require('../cart/pricing');
assert.strictEqual(discounted(1000, 25), 750);
assert.strictEqual(discounted(999, 0), 999);
assert.strictEqual(discounted(1500, 5), 1425);
console.log('hidden ok');
