const assert = require('assert');
const { totalBy } = require('../lib/summary');
const csv = 'branch,amount\n"Lagos, Ikeja",100\nAbuja,50\n"Lagos, Ikeja",25\n';
assert.deepStrictEqual(totalBy(csv, 'branch', 'amount'), { 'Lagos, Ikeja': 125, Abuja: 50 });
console.log('summary tests passed');
