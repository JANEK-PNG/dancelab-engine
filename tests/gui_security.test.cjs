// Execute the actual GUI script against a minimal DOM. No Python bridge is invoked.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const escape = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.text = ''; this.html = '';
    this.options = []; this.selectedIndex = 0; this.value = '';
  }
  addEventListener() {}
  setAttribute() {}
  querySelectorAll() { return []; }
  set textContent(value) { this.text = String(value); this.children = []; this.html = ''; }
  get textContent() { return this.text + this.children.map(e => e.textContent ?? e).join(''); }
  set innerHTML(value) { this.html = String(value); this.text = ''; this.children = []; }
  get innerHTML() {
    return this.html + escape(this.text) + this.children.map(e => typeof e === 'string'
      ? escape(e) : `<${e.tag}>${e.innerHTML}</${e.tag}>`).join('');
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.text = ''; this.html = ''; this.children = nodes; }
}
function gui() {
  const nodes = new Map();
  const document = {
    querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, new Element());
      return nodes.get(selector);
    },
    querySelectorAll: () => [], addEventListener() {},
    createElement: tag => new Element(tag),
  };
  const context = vm.createContext({document, window: {addEventListener() {}}, console});
  const source = fs.readFileSync(process.env.DANCELAB_GUI_SCRIPT || path.join(__dirname,
    '../src/dancelab/gui/statyczne/app.js'), 'utf8');
  vm.runInContext(source, context);
  return {context, node: selector => document.querySelector(selector)};
}
const payload = '<img src=x onerror="window.pywebview.api.usun_plan(\'private\')">';

test('error context renders both caller and failure as literal text', () => {
  const {context, node} = gui();
  context.pokazBlad(payload, payload);
  assert.ok(node('#kontekst').textContent.includes(payload));
  assert.ok(!node('#kontekst').innerHTML.includes('<img'));
});
test('genre failure cannot introduce markup', () => {
  const {context, node} = gui();
  context.rysujGatunki({blad: payload});
  assert.ok(!node('#tabela-gatunkow').innerHTML.includes('<img'));
  assert.ok(node('#tabela-gatunkow').innerHTML.includes('&lt;img'));
});
test('audio status renders backend reason as text', async () => {
  const {context, node} = gui();
  context.window.pywebview = {api: {stan_dzwieku: async () => ({powod: payload})}};
  await context.sprawdzDzwiek();
  assert.ok(!node('#stan-audio').innerHTML.includes('<img'));
});
test('Rekordbox failure cannot introduce markup', async () => {
  const {context, node} = gui();
  context.window.pywebview = {api: {stan_rekordboxa: async () => ({blad: payload})}};
  await context.odswiezStanRb();
  assert.ok(!node('#stan-rb').innerHTML.includes('<img'));
});

test('engine notes preserve literal entities and block markup at the renderer', () => {
  const {context, node} = gui();
  context.rysujNotki([payload + ' &lt;literal&gt;']);
  assert.ok(!node('#notki-box').innerHTML.includes('<img'));
  assert.ok(node('#notki-box').innerHTML.includes('&amp;lt;literal&amp;gt;'));
});
