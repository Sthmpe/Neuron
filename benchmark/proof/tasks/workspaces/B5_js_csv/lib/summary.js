const { parse } = require('./parse');

// Total of a numeric column for each value of a key column.
function totalBy(text, key, value) {
  const out = {};
  for (const row of parse(text)) out[row[key]] = (out[row[key]] || 0) + Number(row[value]);
  return out;
}
module.exports = { totalBy };
