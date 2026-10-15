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
      if (source.offline) throw new Error("Failed to fetch");
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
  return {element, posts, press, poll: () => poll(), tick, context};
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
  assert.equal(element("notice").textContent, "The proxy is back with the Skylight firmware. The install is complete.");
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

test("several proxies need a choice, and the setup checks say what is missing", async () => {
  const source = {...base(), prerequisites: {builder: false, proxy: "none", unadopted: [], connections: {}}};
  const {element, posts, press, poll} = await page(source);
  const line = (id) => element(id).options.map((part) => part.textContent).join("");
  const link = (id) => element(id).options.find((part) => part.href)?.href || "";
  assert.equal(element("prereq").hidden, false);
  assert.equal(element("check-builder").className, "todo");
  assert.match(line("check-builder"), /Install ESPHome Device Builder/);
  assert.match(link("check-builder"), /my\.home-assistant\.io\/redirect\/supervisor_addon/);
  assert.match(line("check-proxy"), /no Bluetooth proxy yet/);
  assert.equal(link("check-proxy"), "https://esphome.io/projects/");
  assert.equal(element("check-connected").hidden, true); // Nothing to report yet.
  assert.equal(element("manual-firmware").hidden, false); // The secondary route, without Device Builder.

  // Device Builder is there, and Home Assistant sees a proxy that is not adopted.
  source.prerequisites = {builder: true, proxy: "adopt", unadopted: ["Kitchen Proxy"], connections: {}};
  await poll();
  await setImmediate();
  assert.equal(element("check-builder").className, "ok");
  assert.equal(element("manual-firmware").hidden, true);
  assert.match(line("check-proxy"), /Home Assistant sees Kitchen Proxy, but Device Builder does not manage it yet/);

  // Adopted, but Home Assistant has not added it.
  source.esphome_nodes = [{file: "k.yaml", node: "kitchen-proxy", has_skylight: false}];
  source.prerequisites = {builder: true, proxy: "ok", unadopted: [], connections: {"kitchen-proxy": "missing"}};
  await poll();
  await setImmediate();
  assert.equal(element("check-proxy").className, "ok");
  assert.match(line("check-connected"), /has not added kitchen-proxy/);
  assert.equal(link("check-connected"), "/config/integrations/integration/esphome");
  assert.equal(element("check-connected").options.find((part) => part.href).target, "_blank");
  source.prerequisites.connections = {"kitchen-proxy": "offline"};
  await poll();
  await setImmediate();
  assert.match(line("check-connected"), /kitchen-proxy is offline/);
  source.prerequisites.connections = {"kitchen-proxy": "ok"};
  await poll();
  await setImmediate();
  assert.equal(element("check-connected").className, "ok");

  // Once a Skylight proxy is ready, the checks are done and hide.
  source.proxies = [
    {entity_id: "sensor.a", name: "A", node: "a", transmit_service: "a_adv_svc_v1"},
    {entity_id: "sensor.b", name: "B", node: "b", transmit_service: "b_adv_svc_v1"},
  ];
  source.esphome_nodes = [{file: "a.yaml", node: "a", has_skylight: true}];
  await poll();
  await setImmediate();
  assert.equal(element("prereq").hidden, true);
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
  const captured = [];
  dimUp.setPointerCapture = (id) => captured.push(id);
  dimUp.listeners.pointerdown({pointerId: 7});
  assert.deepEqual(captured, [7]); // The finger stays on the button if it slides.
  // A long touch on a phone opens the phone's menu unless the page stops it.
  let stopped = false;
  dimUp.listeners.contextmenu({preventDefault: () => { stopped = true; }});
  assert.equal(stopped, true);
  await tick(); // Held long enough: the first hold command.
  await tick(); // 0.6 seconds later: another one.
  dimUp.listeners.pointerup();
  assert.deepEqual(posts, [
    {action: "dim_hold", direction: "up"},
    {action: "dim_hold", direction: "up"},
  ]);
  // A quick press is one ordinary step. Releasing also ends the capture.
  dimUp.listeners.pointerdown({pointerId: 8});
  dimUp.listeners.pointerup();
  dimUp.listeners.lostpointercapture();
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
  assert.equal(element("updates-title").textContent, "Needs attention");
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
  // The page says plainly that the install finished.
  assert.equal(element("notice").textContent, "The proxy runs the new Skylight firmware 2. The install is complete.");
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
  assert.equal(element("updates-title").textContent, "Needs attention (optional)");
  source.esphome_nodes[0].api_key = true;
  await poll();
  await setImmediate();
  assert.equal(element("updates").hidden, true);
});


test("a pending restart leaves the restart and install buttons usable", async () => {
  const source = {...base(), installed: true, restart_required: true};
  const {context} = await page(source);
  const data = {connected: true, restart_required: true};
  assert.equal(context.buttonDisabled("restart", data), false);
  assert.equal(context.buttonDisabled("install", data), false);
  assert.equal(context.buttonDisabled("pair", data), true);
  // Restart goes through Home Assistant, so it waits for the connection.
  assert.equal(context.buttonDisabled("restart", {connected: false, restart_required: true}), true);
  assert.equal(context.buttonDisabled("install", {connected: false}), false);
  assert.equal(context.buttonDisabled("pair", {connected: true, restart_required: false}), false);
});


test("the page shows a restart under way, through failed requests, until it is done", async () => {
  const source = {...base(), installed: true, restart_required: true};
  const {element, posts, press, poll} = await page(source);
  assert.equal(element("restart").hidden, false);
  assert.equal(element("restart-status").hidden, true); // Needed, not started yet.
  await press({action: "restart"});
  assert.equal(posts.at(-1).action, "restart");
  assert.equal(element("restart-status").hidden, false);
  // Home Assistant goes away: requests fail, and the page shows no error.
  source.offline = true;
  await poll();
  await setImmediate();
  assert.equal(element("restart-status").hidden, false);
  assert.equal(element("notice").textContent, "");
  // It comes back with the integration loaded.
  source.offline = false;
  source.restart_required = false;
  await poll();
  await setImmediate();
  assert.equal(element("installation").hidden, true);
  assert.equal(element("notice").textContent, "Home Assistant has restarted. The Skylight integration is loaded.");
});

test("a restart request that Home Assistant drops still counts as a restart", async () => {
  const source = {...base(), installed: true, restart_required: true};
  const {element, press, context} = await page(source);
  context.fetch = async (url, init) => {
    if (init?.method === "POST") throw new Error("Failed to fetch");
    return {ok: true, json: async () => structuredClone(source)};
  };
  await press({action: "restart"});
  assert.equal(element("restart-status").hidden, false);
  assert.equal(element("notice").textContent, "");
});

test("a restart started outside the page shows too", async () => {
  const source = {...base(), installed: true, restart_required: true, connected: false};
  const {element} = await page(source);
  assert.equal(element("restart-status").hidden, false);
});


test("proxies show their friendly name, and the badge waits for a Skylight proxy", async () => {
  const source = {...base(), esphome_nodes: [
    {file: "esphome-web-ece638.yaml", node: "esphome-web-ece638", friendly_name: "bluetooth-proxy-1", has_skylight: false},
    {file: "plain.yaml", node: "kitchen", friendly_name: null, has_skylight: false},
  ], prerequisites: {builder: true, proxy: "ok", unadopted: [], connections: {"esphome-web-ece638": "ok"}}};
  const {element, poll} = await page(source);
  assert.ok(element("node-choice").options.length >= 2);
  const line = (id) => element(id).options.map((part) => part.textContent).join("");
  assert.match(line("check-proxy"), /bluetooth-proxy-1 \(esphome-web-ece638\), kitchen/);
  assert.match(line("check-connected"), /connected to bluetooth-proxy-1 \(esphome-web-ece638\)/);
  assert.equal(element("connection").hidden, true); // No Skylight proxy yet.
  source.proxies = [{entity_id: "sensor.p", name: "P", node: "esphome-web-ece638", transmit_service: "x_adv_svc_v1"}];
  source.proxy_online = true;
  await poll();
  await setImmediate();
  assert.equal(element("connection").hidden, false);
  assert.equal(element("connection").textContent, "Proxy online");
});


test("a proxy with the firmware files but no install shows only the install step", async () => {
  const source = {...base(), esphome_nodes: [
    {file: "apollo.yaml", node: "apollo", friendly_name: "Apollo MSR-2", has_skylight: false},
    {file: "proxy.yaml", node: "esphome-web-ece638", friendly_name: "bluetooth-proxy-1", has_skylight: true},
  ]};
  const {element} = await page(source);
  assert.equal(element("proxy-firmware").hidden, true);
  assert.equal(element("proxy-install").hidden, false);
  assert.equal(element("proxy-node").textContent, "bluetooth-proxy-1 (esphome-web-ece638)");
});
