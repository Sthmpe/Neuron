// Split one CSV line into fields. Fields may be wrapped in double quotes.
function splitLine(line) {
  return line.split(',').map(f => f.trim().replace(/^"|"$/g, ''));
}
function parse(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = splitLine(lines[0]);
  return lines.slice(1).map(l => Object.fromEntries(splitLine(l).map((v, i) => [header[i], v])));
}
module.exports = { splitLine, parse };
