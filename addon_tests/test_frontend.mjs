import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {setImmediate} from "node:timers/promises";
import {test} from "node:test";
import vm from "node:vm";

test("initial-state form always follows modes, records manual choices and saves power without a stale mode", async () => {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      value: "", dataset: {}, options: [], listeners: {},
      addEventListener(type, handler) { this.listeners[type] = handler; },
      replaceChildren(...options) { this.options = options; this.value = options[0]?.value ?? ""; },
    });
    return elements.get(id);
  };
  const source = {
    connected: true, installed: true, configured: true, first_setup: true,
    restart_required: false, power_synchronized: false, state: "unknown", effect: null,
    name: "Skylight", version: "0.2.4", entity_id: "light.skylight",
    effects: ["Focus", "Rest", "Relax", "Energize"],
    proxies: [], transmit_services: [], proxy_sensors: [],
  };
  const posts = [];
  let poll;
  const context = vm.createContext({
    URL, console,
    document: {
      querySelector(selector) {
        return selector === "base" ? {href: "http://localhost/"} : {content: "test-session"};
      },
      getElementById: element, createElement: () => ({}),
      querySelectorAll: () => [], addEventListener() {},
    },
    setInterval(callback) { poll = callback; },
    async fetch(url, init) {
      if (init?.method === "POST") {
        const body = JSON.parse(init.body);
        posts.push(body);
        // Mode choices record immediately; a remote mode can arrive during power saving.
        source.effect = body.action === "sync_mode" ? body.effect : "Energize";
        return {ok: true, json: async () => ({ok: true})};
      }
      return {ok: true, json: async () => structuredClone(source)};
    },
  });
  vm.runInContext(await readFile(new URL("../philips_skylight/app/static/app.js", import.meta.url), "utf8"), context);
  await setImmediate();
  assert.equal(element("observed-mode").value, "Unknown");
  assert.equal(element("observed-power").value, "");
  assert.equal(posts.length, 0);

  source.effect = "Focus";
  await poll();
  assert.equal(element("observed-mode").value, "Focus");
  element("observed-mode").value = "Relax";
  element("observed-mode").listeners.change();
  await setImmediate();
  assert.deepEqual(posts, [{action: "sync_mode", effect: "Relax"}]);
  assert.equal(element("observed-mode").value, "Relax");
  source.effect = "Rest";
  await poll();
  assert.equal(element("observed-mode").value, "Rest");
  source.connected = false;
  source.effect = null;
  await poll();
  assert.equal(element("observed-mode").value, "Rest");
  source.connected = true;
  source.effect = "Rest";
  source.state = "on";
  source.power_synchronized = true;
  await poll();
  assert.equal(element("observed-power").value, ""); // Never invent the user's observation.

  element("observed-power").value = "on";
  element("match-form").listeners.submit({preventDefault() {}});
  await setImmediate();
  assert.deepEqual(posts[1], {action: "sync_power", is_on: true});
  assert.equal(element("observed-mode").value, "Energize");
  element("observed-mode").value = "Unknown";
  element("observed-mode").listeners.change();
  await setImmediate();
  assert.deepEqual(posts[2], {action: "sync_mode", effect: "Unknown"});
  await poll();
  assert.equal(element("observed-mode").value, "Unknown");
  element("match-form").listeners.submit({preventDefault() {}});
  await setImmediate();
  assert.deepEqual(posts[3], {action: "sync_power", is_on: true});
});
