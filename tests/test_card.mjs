import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {setImmediate} from "node:timers/promises";
import {test} from "node:test";
import vm from "node:vm";

const SCRIPT = new URL("../custom_components/philips_skylight/frontend/philips-skylight-card.js",
  import.meta.url);

// Just enough of a browser to define the card and build it.
async function browser() {
  const defined = new Map();
  const made = [];
  const node = (tag) => {
    const item = {tag, attributes: {}, children: [], className: "", textContent: "", listeners: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      append(...children) { this.children.push(...children); },
      addEventListener(type, handler) { this.listeners[type] = handler; }};
    made.push(item);
    return item;
  };
  class HTMLElement {
    constructor() { this.children = []; }
    replaceChildren(...children) { this.children = children; }
  }
  const window = {
    async loadCardHelpers() {
      return {createCardElement: (config) => Object.assign(node(config.type), {config,
        getCardSize: () => 12, getGridOptions: () => ({columns: 12})})};
    },
  };
  const context = vm.createContext({
    HTMLElement, window, String, Error,
    customElements: {
      get: (name) => defined.get(name),
      define(name, element) {
        if (defined.has(name)) throw new Error("already defined");
        defined.set(name, element);
      },
    },
    document: {createElement: node},
  });
  // A block keeps each load's names apart, as each module load does in a browser.
  const source = "{" + await readFile(SCRIPT, "utf8") + "\n}";
  vm.runInContext(source, context);
  return {Card: defined.get("philips-skylight-card"), window, made,
    load: () => vm.runInContext(source, context)};
}

test("the card is in the card picker, and a second load does not throw", async () => {
  const {Card, window, load} = await browser();
  load();
  assert.equal(window.customCards.length, 1);
  assert.equal(window.customCards[0].type, "philips-skylight-card");
  assert.equal(window.customCards[0].name, "Philips Skylight");
  assert.equal(window.customCards[0].preview, true);
  assert.deepEqual({...Card.getStubConfig()}, {});
  const card = new Card();
  card.setConfig({type: "custom:philips-skylight-card"});
  assert.equal(card.getCardSize(), 8);
  assert.deepEqual({...card.getGridOptions()}, {});
});

test("the card asks once, then builds the standard cards with the newest hass", async () => {
  const {Card} = await browser();
  const asked = [];
  let answer;
  const hass = (name) => ({name, callWS(message) {
    asked.push(message);
    return new Promise((resolve) => { answer = resolve; });
  }});
  const card = new Card();
  card.setConfig({type: "custom:philips-skylight-card"});
  card.hass = hass("first");
  card.hass = hass("second"); // A state change before the answer arrives.
  assert.equal(asked.length, 1);
  assert.equal(asked[0].type, "philips_skylight/card");
  answer({card: {type: "vertical-stack", cards: []}});
  await setImmediate();
  const [inner] = card.children;
  assert.equal(inner.tag, "vertical-stack");
  assert.equal(inner.hass.name, "second");
  card.hass = hass("third");
  assert.equal(inner.hass.name, "third");
  assert.equal(asked.length, 1);
  assert.equal(card.getCardSize(), 12);
  assert.equal(card.getGridOptions().columns, 12);
});

test("a failed request shows its message in a plain card", async () => {
  const {Card} = await browser();
  const card = new Card();
  card.setConfig({});
  card.hass = {callWS: async () => { throw {code: "not_found", message: "Enable switch.x."}; }};
  await setImmediate();
  const [inner] = card.children;
  assert.equal(inner.tag, "ha-card");
  assert.equal(inner.attributes.header, "Philips Skylight");
  assert.equal(inner.children[0].textContent, "Enable switch.x.");
});

test("after a failure, the card asks again only once the retry time has passed", async () => {
  const {Card} = await browser();
  const card = new Card();
  card.setConfig({});
  let calls = 0;
  let fail = true;
  const hass = {callWS: async () => {
    calls += 1;
    if (fail) throw {message: "Home Assistant is starting."};
    return {card: {type: "vertical-stack", cards: []}};
  }};
  card.hass = hass;
  await setImmediate();
  card.hass = hass;  // A state change right away does not ask again.
  await setImmediate();
  assert.equal(calls, 1);
  fail = false;
  card._retryAt = 0;  // The retry time has passed.
  card.hass = hass;
  await setImmediate();
  await setImmediate();
  assert.equal(calls, 2);
  assert.equal(card.children[0].tag, "vertical-stack");
  card.hass = hass;  // A working card never asks again.
  await setImmediate();
  assert.equal(calls, 2);
});
