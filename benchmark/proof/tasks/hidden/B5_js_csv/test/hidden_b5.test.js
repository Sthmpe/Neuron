const assert = require('assert');
const { splitLine } = require('../lib/parse');
assert.deepStrictEqual(splitLine('a,"b, c",d'), ['a', 'b, c', 'd']);
assert.deepStrictEqual(splitLine('"x",y'), ['x', 'y']);
assert.deepStrictEqual(splitLine('1,2,3'), ['1', '2', '3']);
console.log('hidden ok');
