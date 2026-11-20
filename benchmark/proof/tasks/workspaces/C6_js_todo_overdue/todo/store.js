// A small to-do list kept in memory.
function create() { return []; }
function add(list, title) { list.push({ title, done: false }); return list; }
function finish(list, title) { const it = list.find(i => i.title === title); if (it) it.done = true; return list; }
function open(list) { return list.filter(i => !i.done).map(i => i.title); }
module.exports = { create, add, finish, open };
