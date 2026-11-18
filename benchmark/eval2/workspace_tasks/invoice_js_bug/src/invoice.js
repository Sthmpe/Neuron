// Invoice arithmetic in kobo-free naira amounts with 2 decimals. VAT is 7.5% on the subtotal.
const VAT_RATE = 0.075;

function round2(x) {
  return Math.round(x * 100) / 100;
}

function lineTotal(line) {
  return round2(line.quantity * line.price);
}

function subtotal(lines) {
  return round2(lines.reduce((sum, l) => sum + lineTotal(l), 0));
}

function vat(amount) {
  return Math.floor(amount * VAT_RATE * 100) / 100;
}

function total(lines) {
  const s = subtotal(lines);
  return round2(s + vat(s));
}

module.exports = { lineTotal, subtotal, vat, total, VAT_RATE };
