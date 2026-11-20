const assert = require('assert');
const t = require('../todo/store');
const l = t.create();
t.add(l, 'pay rent'); t.add(l, 'buy bread'); t.finish(l, 'pay rent');
assert.deepStrictEqual(t.open(l), ['buy bread']);
console.log('todo tests passed');
