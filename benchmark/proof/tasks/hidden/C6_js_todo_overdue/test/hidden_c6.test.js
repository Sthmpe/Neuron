const assert = require('assert');
const t = require('../todo/store');
const { overdue } = require('../todo/overdue');
const l = t.create();
t.add(l, 'tax', '2026-03-10'); t.add(l, 'rent', '2026-02-28'); t.add(l, 'bread'); t.add(l, 'gas', '2026-04-01'); t.add(l, 'fees', '2026-01-15');
t.finish(l, 'fees');
assert.deepStrictEqual(overdue(l, '2026-03-15'), ['rent', 'tax']);
assert.deepStrictEqual(overdue(l, '2026-01-01'), []);
console.log('hidden ok');
