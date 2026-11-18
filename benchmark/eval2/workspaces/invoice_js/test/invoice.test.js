const test = require('node:test');
const assert = require('node:assert');
const { lineTotal, subtotal, vat, total } = require('../src/invoice.js');

const lines = [{ quantity: 3, price: 1250.5 }, { quantity: 2, price: 799.96 }];

test('line totals', () => { assert.strictEqual(lineTotal(lines[0]), 3751.5); });
test('subtotal', () => { assert.strictEqual(subtotal(lines), 5351.42); });
test('vat rounds to the nearest kobo', () => { assert.strictEqual(vat(5351.42), 401.36); });
test('total is subtotal plus vat', () => { assert.strictEqual(total(lines), 5752.78); });
