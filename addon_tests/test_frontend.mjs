import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {setImmediate} from "node:timers/promises";
import {test} from "node:test";
import vm from "node:vm";

const SCRIPT = new URL("../philips_skylight/app/static/app.js", import.meta.url);

async function page(source) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      id, value: "", dataset: {}, options: [], listeners: {}, hidden: false,
      textContent: "", className: "",
      addEventListener(type, handler) { this.listeners[type] = handler; },
      replaceChildren(...options) { this.options = options; this.value = options[0]?.value ?? ""; },
    });
    return elements.get(id);
  };
  const posts = [];
  const timers = [];
  let poll;
  let click;
  const context = vm.createContext({
    URL, console, confirm: () => true,
    setTimeout(callback) { timers.push(callback); return timers.length; },
    clearTimeout(id) { timers[id - 1] = null; },
    document: {
      querySelector(selector) {
        return selector === "base" ? {href: "http://localhost/"} : {content: "test-session"};
      },
      getElementById: element,
      createElement: () => ({dataset: {}}),
      querySelectorAll: () => [],
      addEventListener(type, handler) { if (type === "click") click = handler; },
    },
    setInterval(callback) { poll = callback; },
    async fetch(url, init) {
      if (init?.method === "POST") {
        posts.push(JSON.parse(init.body));
        return {ok: true, json: async () => ({ok: true})};
      }
      return {ok: true, json: async () => structuredClone(source)};
    },
  });
  vm.runInContext(await readFile(SCRIPT, "utf8"), context);
  await setImmediate();
  const press = async (dataset) => {
    click({target: {closest: () => ({dataset, disabled: false})}});
    await setImmediate();
  };
  const tick = async () => {
    const callback = timers.findLast((item) => item);
    timers.fill(null);
    await callback?.();
    await setImmediate();
  };
  return {element, posts, press, poll: () => poll(), tick};
}

const base = () => ({
  connected: true, installed: true, restart_required: false, configured: false,
  first_setup: false, state: "unknown", effect: null, name: "Philips Skylight",
  version: "0.3.0", entity_id: null, effects: ["Refresh", "Energize", "Relax"],
  proxies: [], transmit_services: [], proxy_sensors: [], proxy_online: false,
  tracking: null, esphome_nodes: [], device_builder: "/esphome_ingress",
});

test("setup checklist walks from firmware to a passed pairing test", async () => {
  const source = base();
  source.esphome_nodes = [{file: "proxy.yaml", node: "proxy-1", has_skylight: false}];
  const {element, posts, press, poll} = await page(source);
  assert.equal(element("setup").hidden, false);
  assert.equal(element("proxy-firmware").hidden, false);
  assert.equal(element("node-choice").value, "proxy.yaml"); // A single proxy is preselected.
  assert.equal(element("control").hidden, true);

  await press({action: "prepare_firmware"});
  assert.deepEqual(posts.at(-1), {action: "prepare_firmware", file: "proxy.yaml"});
  assert.equal(element("proxy-install").hidden, false);
  assert.equal(element("proxy-firmware").hidden, true);
  assert.equal(element("proxy-node").textContent, "proxy-1");
  assert.equal(element("device-builder").hidden, false);

  // The proxy returns with the firmware; the add-on connects it by itself.
  source.esphome_nodes[0].has_skylight = true;
  source.proxies = [{entity_id: "sensor.p", name: "Proxy", node: "proxy-1", transmit_service: "proxy_1_adv_svc_v1"}];
  source.proxy_online = true;
  await poll();
  assert.equal(element("step-proxy").className, "done");
  assert.equal(element("step-connect-status").textContent, "Connecting…");
  assert.equal(element("connect-choice").hidden, true);

  source.configured = true;
  source.first_setup = true;
  source.entity_id = "light.skylight";
  source.tracking = false;
  await poll();
  assert.equal(element("step-connect").className, "done");
  assert.equal(element("tracking-off").hidden, false);
  await press({action: "allow_tracking"});
  assert.equal(posts.at(-1).action, "allow_tracking");

  source.tracking = true;
  await poll();
  assert.equal(element("step-tracking").className, "done");
  assert.equal(element("pair-steps").hidden, false);
  await press({action: "pair"});
  assert.equal(posts.at(-1).action, "pair");
  assert.equal(posts.at(-1).confirm, true);
  source.pairing_remaining = 8;
  await poll();
  assert.equal(element("pair-wait").hidden, false);
  assert.equal(element("pair-steps").hidden, true);
  assert.equal(element("pair-countdown").textContent, "Pairing… 8 s");
  source.pairing_remaining = 0; // The 10-second burst ends; the test follows.
  await poll();
  assert.equal(element("pair-wait").hidden, true);
  assert.equal(element("pair-test").hidden, false);
  await press({action: "test"});
  assert.equal(posts.at(-1).action, "test");
  assert.equal(element("pair-ask").hidden, false);

  await press({action: "confirm_test", result: "none"});
  assert.deepEqual(posts.at(-1), {action: "confirm_test", result: "none"});
  assert.equal(element("pair-steps").hidden, false); // Back to pairing.

  await press({action: "pair"});
  source.pairing_remaining = 3;
  await poll();
  source.pairing_remaining = 0;
  await poll();
  assert.equal(element("pair-test").hidden, false);
  await press({action: "test"});
  await press({action: "confirm_test", result: "off"});
  assert.deepEqual(posts.at(-1), {action: "confirm_test", result: "off"});
  assert.equal(element("pair-mode").hidden, false); // Choose a mode to finish.
  await press({action: "finish_setup", effect: "Energize"});
  assert.deepEqual(posts.at(-1), {action: "finish_setup", effect: "Energize"});
  source.first_setup = false;
  source.state = "on";
  source.effect = "Energize";
  await poll();
  assert.equal(element("setup").hidden, true);
  assert.equal(element("control").hidden, false);
  assert.equal(element("dashboard").hidden, false);
  assert.equal(element("state-text").textContent, "On · Energize");
  assert.equal(element("connection").textContent, "Proxy online");
});

test("several proxies need a choice, and no proxy shows a hint", async () => {
  const source = base();
  const {element, posts, press, poll} = await page(source);
  assert.equal(element("proxy-none").hidden, false);
  source.proxies = [
    {entity_id: "sensor.a", name: "A", node: "a", transmit_service: "a_adv_svc_v1"},
    {entity_id: "sensor.b", name: "B", node: "b", transmit_service: "b_adv_svc_v1"},
  ];
  source.esphome_nodes = [{file: "a.yaml", node: "a", has_skylight: true}];
  await poll();
  assert.equal(element("proxy-none").hidden, true);
  assert.equal(element("connect-choice").hidden, false);
  element("proxy-choice").value = "sensor.b";
  await press({action: "connect"});
  assert.deepEqual(posts.at(-1), {action: "setup", proxy: "sensor.b", name: "Philips Skylight"});
});

test("corrections change only the record, and controls send commands", async () => {
  const source = {...base(), configured: true, entity_id: "light.skylight", tracking: true,
    proxies: [{entity_id: "sensor.p", name: "P", node: "p", transmit_service: "p_adv_svc_v1"}]};
  const {element, posts, press} = await page(source);
  assert.equal(element("setup").hidden, true);
  assert.equal(element("fixes").hidden, false);
  await press({action: "sync_power", on: "yes"});
  assert.deepEqual(posts.at(-1), {action: "sync_power", is_on: true});
  element("observed-mode").value = "Relax";
  element("observed-mode").listeners.change();
  await setImmediate();
  assert.deepEqual(posts.at(-1), {action: "sync_mode", effect: "Relax"});
  await press({action: "scene", effect: "Refresh"});
  assert.deepEqual(posts.at(-1), {action: "scene", effect: "Refresh"});
  await press({action: "skip_sequence"});
  assert.equal(posts.at(-1).action, "scene"); // Needs the tick box first.
  assert.equal(element("notice").textContent, "Tick the box first.");
  await press({action: "unpair_all"});
  assert.equal(posts.at(-1).action, "scene"); // Unpair all needs its tick box too.
  element("unpair-confirm").checked = true;
  await press({action: "unpair_all"});
  assert.deepEqual(posts.at(-1), {action: "unpair_all", confirm: true});
  await press({action: "start_over"});
  assert.equal(posts.at(-1).action, "start_over");
});

test("holding a dim button repeats the hold command until release", async () => {
  const source = {...base(), configured: true, entity_id: "light.skylight", tracking: true,
    proxies: [{entity_id: "sensor.p", name: "P", node: "p", transmit_service: "p_adv_svc_v1"}]};
  const {element, posts, press, tick} = await page(source);
  const dimUp = element("dim-up");
  dimUp.dataset.hold = "up";
  dimUp.listeners.pointerdown();
  await tick(); // Held long enough: the first hold command.
  await tick(); // 0.6 seconds later: another one.
  dimUp.listeners.pointerup();
  assert.deepEqual(posts, [
    {action: "dim_hold", direction: "up"},
    {action: "dim_hold", direction: "up"},
  ]);
  // A quick press is one ordinary step.
  dimUp.listeners.pointerdown();
  dimUp.listeners.pointerup();
  await setImmediate();
  assert.deepEqual(posts.at(-1), {action: "dim_up"});
  // A pointer click on a dim button sends nothing more; the keyboard sends one step.
  await press({action: "dim_up", hold: "up"});
  assert.equal(posts.length, 3);
});

test("updates show only the firmware and card steps that apply", async () => {
  const source = {...base(), configured: true, entity_id: "light.skylight", tracking: true,
    proxies: [{entity_id: "sensor.p", name: "P", node: "p", transmit_service: "p_adv_svc_v1"}],
    firmware: {status: "current", version: "2", reported: ["2"], nodes: ["proxy-1"]},
    outdated_cards: []};
  const {element, posts, press, poll} = await page(source);
  assert.equal(element("updates").hidden, true);

  source.firmware = {...source.firmware, status: "files", reported: ["1"]};
  await poll();
  await setImmediate();
  assert.equal(element("updates").hidden, false);
  assert.equal(element("firmware-files").hidden, false);
  assert.equal(element("firmware-install").hidden, true);
  assert.equal(element("firmware-nodes").textContent, "proxy-1");
  await press({action: "update_firmware"});
  assert.equal(posts.at(-1).action, "update_firmware");

  source.firmware = {...source.firmware, status: "install"};
  await poll();
  await setImmediate();
  assert.equal(element("firmware-files").hidden, true);
  assert.equal(element("firmware-install").hidden, false);
  assert.equal(element("update-builder").href, "/esphome_ingress");

  source.firmware = {...source.firmware, status: "current", reported: ["2"]};
  source.outdated_cards = ["Skylight", "Kitchen"];
  await poll();
  await setImmediate();
  assert.equal(element("firmware-install").hidden, true);
  assert.equal(element("card-update").hidden, false);
  assert.equal(element("card-dashboards").textContent, "Skylight, Kitchen");
  await press({action: "update_card"});
  assert.equal(posts.at(-1).action, "update_card");

  source.outdated_cards = [];
  await poll();
  await setImmediate();
  assert.equal(element("updates").hidden, true);

  // A proxy with the firmware but no API key gets a warning.
  source.esphome_nodes = [{file: "p.yaml", node: "proxy-1", has_skylight: true, uses_package: true, api_key: false}];
  await poll();
  await setImmediate();
  assert.equal(element("updates").hidden, false);
  assert.equal(element("proxy-key").hidden, false);
  assert.equal(element("keyless-nodes").textContent, "proxy-1");
  source.esphome_nodes[0].api_key = true;
  await poll();
  await setImmediate();
  assert.equal(element("updates").hidden, true);
});
