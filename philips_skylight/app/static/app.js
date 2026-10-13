"use strict";
const base = document.querySelector("base").href;
const csrf = document.querySelector('meta[name="csrf"]').content;
let busy = false;
let state = null;
let pairStage = "pair";
let lastRemaining = 0;
let stopped = false;
let preparedNode = null;
let dashboardRevision = null;
let dashboardRead = 0;
const el = (id) => document.getElementById(id);
const show = (id, visible) => { el(id).hidden = !visible; };
function notice(message, error = false) {
  el("notice").textContent = message;
  el("notice").className = error ? "error" : "";
  el("notice").hidden = !message;
}
function options(id, items, empty = null) {
  const select = el(id);
  const current = select.value;
  const encoded = JSON.stringify([items, empty]);
  const value = (item) => typeof item === "string" ? item : item.value ?? item.entity_id;
  if (select.dataset.items === encoded) return;
  select.replaceChildren(...(empty ? [{value: "", name: empty}, ...items] : items).map((item) => {
    const option = document.createElement("option");
    option.value = value(item);
    option.textContent = typeof item === "string" ? item : item.name;
    return option;
  }));
  if (empty && items.length === 1 && !current) select.value = value(items[0]);
  else if ([...select.options].some((item) => item.value === current)) select.value = current;
  select.dataset.items = encoded;
}
function step(id, done, text) {
  el(id).className = done ? "done" : "";
  el(id + "-status").textContent = text;
}
function modeButtons(id, action, effects) {
  if (el(id).dataset.items === JSON.stringify(effects)) return;
  el(id).replaceChildren(...effects.map((effect) => {
    const button = document.createElement("button");
    button.dataset.action = action;
    button.dataset.effect = effect;
    button.textContent = effect;
    return button;
  }));
  el(id).dataset.items = JSON.stringify(effects);
}
function render(data) {
  state = data;
  el("connection").textContent = !data.connected ? "Connecting" : data.proxy_online ? "Proxy online" : "Proxy offline";
  el("connection").className = "badge" + (data.connected && data.proxy_online ? " online" : "");
  const needsInstall = !data.installed || data.restart_required;
  show("installation", needsInstall);
  show("install", !data.installed);
  show("restart", data.installed && data.restart_required);
  el("install-message").textContent = data.installed
    ? "Restart Home Assistant to load the Skylight integration."
    : "Install the Skylight integration to continue.";

  // The checklist stays until the pairing test has passed once.
  const setupDone = data.configured && !data.first_setup;
  show("setup", !needsInstall && !setupDone);
  const proxyReady = data.proxies.length > 0;
  const nodes = data.esphome_nodes || [];
  const waiting = nodes.filter((node) => node.has_skylight);
  step("step-proxy", proxyReady, proxyReady ? "✓" : "");
  show("proxy-firmware", !proxyReady && nodes.some((node) => !node.has_skylight) && !preparedNode);
  options("node-choice", nodes.filter((node) => !node.has_skylight).map((node) => ({value: node.file, name: node.node})), "Choose a proxy");
  const installNode = preparedNode || (waiting.length === 1 ? waiting[0].node : null);
  show("proxy-install", !proxyReady && Boolean(installNode));
  el("proxy-node").textContent = installNode || "";
  if (data.device_builder) el("device-builder").href = data.device_builder;
  show("device-builder", Boolean(data.device_builder));
  show("proxy-none", !proxyReady && nodes.length === 0);

  step("step-connect", data.configured, data.configured ? "✓" : proxyReady && data.proxies.length === 1 ? "Connecting…" : "");
  show("connect-choice", proxyReady && !data.configured && data.proxies.length > 1);
  const proxyNames = data.proxies.map((item) => ({...item, name: item.name + " · " + item.node}));
  options("proxy-choice", proxyNames, "Choose a proxy");
  options("proxy-change", proxyNames, "Choose a proxy");

  step("step-tracking", data.tracking === true, data.tracking === true ? "✓" : data.tracking === false ? "" : proxyReady ? "Checking…" : "");
  show("tracking-off", data.tracking === false);

  // The integration repeats the request; the user reaches the switch meanwhile.
  // After Stop, ignore the old window until the integration reports it has ended.
  if (!data.pairing_remaining) stopped = false;
  const remaining = stopped ? 0 : data.pairing_remaining || 0;
  // Move on to the test only when the window ran out by itself, not after Stop.
  if (lastRemaining && lastRemaining <= 4 && !remaining && !setupDone && pairStage === "pair") pairStage = "test";
  lastRemaining = remaining;
  show("pair-wait", remaining > 0);
  el("pair-countdown").textContent = "Pairing… " + Math.floor(remaining / 60) + ":" + String(remaining % 60).padStart(2, "0") + " left";
  step("step-pair", setupDone, setupDone ? "✓" : remaining ? "Pairing…" : "");
  const pairing = data.configured && !setupDone && !remaining;
  show("pair-steps", pairing && pairStage === "pair");
  show("pair-test", pairing && pairStage === "test");
  show("pair-ask", pairing && pairStage === "ask");
  show("pair-mode", pairing && pairStage === "mode");

  const ready = data.configured && !needsInstall && setupDone;
  show("control", ready);
  show("dashboard", ready);
  show("fixes", ready);
  el("state-text").textContent = data.state === "on" ? "On" + (data.effect ? " · " + data.effect : "")
    : data.state === "off" ? "Off" : "State unknown";
  modeButtons("modes", "scene", data.effects);
  modeButtons("setup-modes", "finish_setup", data.effects);
  options("observed-mode", ["Unknown", ...data.effects]);
  if (!busy && data.connected) el("observed-mode").value = data.effects.includes(data.effect) ? data.effect : "Unknown";
  options("service", data.transmit_services, "Choose an action");
  options("proxy", data.proxy_sensors, "Choose a sensor");
  el("version").textContent = "v" + data.version;
  for (const button of document.querySelectorAll("button")) {
    const install = button.dataset.action === "install";
    button.disabled = busy || (!install && (!data.connected || data.restart_required));
  }
  el("add-card").disabled ||= !dashboardRevision || !el("view-choice").value;
}
async function get(path) {
  const response = await fetch(new URL(path, base), {cache: "no-store"});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Cannot read the add-on status");
  return result;
}
async function refresh() {
  try { render(await get("api/status")); }
  catch (error) { if (!busy) notice(error.message, true); }
}
const messages = {
  test: "Sending…",
};
const results = {
  restart: () => "Home Assistant is restarting. This page reconnects by itself.",
  prepare_firmware: () => "",
  allow_tracking: () => "",
  pair: () => "",
  test: () => "",
  confirm_test: (body) => body.result === "none" ? "The panel did not respond. Start pairing again." : "",
  finish_setup: () => "Setup is complete.",
  setup: () => "",
  create_dashboard: (body, result) => result.created ? "Dashboard created." : "You already have a Skylight dashboard.",
  add_card: (body, result) => result.added ? "Card added." : "That view already has the card.",
  skip_sequence: () => "Counter moved forward. Try the power button above.",
  rhythm_start: () => "Schedule started. The panel blinks.",
};
async function action(body) {
  if (busy) return;
  busy = true;
  if (state) render(state);
  notice(messages[body.action] || "");
  try {
    const response = await fetch(new URL("api/action", base), {
      method: "POST", headers: {"Content-Type": "application/json", "X-Skylight-CSRF": csrf},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "That did not work");
    if (result.url) {
      el("dashboard-link").href = result.url;
      el("dashboard-link").hidden = false;
    }
    notice(results[body.action] ? results[body.action](body, result) : "");
    if (body.action === "prepare_firmware") {
      preparedNode = (state?.esphome_nodes || []).find((node) => node.file === body.file)?.node || body.file;
    }
    if (body.action === "stop_pairing") pairStage = body.done ? "test" : "pair";
    if (body.action === "stop_pairing") { lastRemaining = 0; stopped = true; }
    if (body.action === "pair") stopped = false;
    if (body.action === "test") pairStage = "ask";
    if (body.action === "confirm_test") pairStage = body.result === "none" ? "pair" : "mode";
    if (body.action === "finish_setup") pairStage = "pair";
    if (body.action === "skip_sequence") el("skip-confirm").checked = false;
    if (body.action === "add_card") await loadViews();
  } catch (error) { notice(error.message, true); }
  finally { busy = false; await refresh(); }
}
async function loadViews() {
  const read = ++dashboardRead;
  dashboardRevision = null;
  options("view-choice", [], "Choose a view");
  if (state) render(state);
  const path = el("dashboard-choice").value;
  if (!path) return;
  try {
    const result = await get("api/dashboards?url_path=" + encodeURIComponent(path));
    if (read !== dashboardRead) return;
    dashboardRevision = result.revision;
    options("view-choice", result.views.map((view) => ({value: String(view.index), name: view.title})), "Choose a view");
    if (!result.views.length) notice("That dashboard has no views that can be changed. Create a Skylight dashboard instead.", true);
  } catch (error) { if (read === dashboardRead) notice(error.message, true); }
  if (state) render(state);
}
async function chooseDashboard() {
  try {
    const result = await get("api/dashboards");
    options("dashboard-choice", result.dashboards.map((item) => ({value: item.url_path, name: item.title})), "Choose a dashboard");
    el("dashboard-target").hidden = false;
    if (!result.dashboards.length) notice("No dashboard can be changed. Create a Skylight dashboard instead.", true);
    await loadViews();
  } catch (error) { notice(error.message, true); }
}
function connectBody(button) {
  if (button.dataset.from === "advanced") {
    return {action: "setup", transmit_service: el("service").value, proxy_entity: el("proxy").value, name: state?.name};
  }
  const choice = el(button.dataset.from === "proxy-change" ? "proxy-change" : "proxy-choice").value;
  return {action: "setup", proxy: choice, name: state?.name};
}
// Press and hold: a short press sends one step. After a moment, the remote's hold
// command repeats every 0.6 seconds until the finger lifts.
let hold = null;
async function post(body) {
  try {
    const response = await fetch(new URL("api/action", base), {
      method: "POST", headers: {"Content-Type": "application/json", "X-Skylight-CSRF": csrf},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "That did not work");
  } catch (error) { notice(error.message, true); }
}
function holdStart(direction) {
  if (hold || !state || !state.connected || state.restart_required) return;
  hold = {direction, sent: false, busy: false};
  hold.timer = setTimeout(holdTick, 450);
}
async function holdTick() {
  const current = hold;
  if (!current) return;
  current.sent = true;
  if (!current.busy) {
    current.busy = true;
    await post({action: "dim_hold", direction: current.direction});
    current.busy = false;
  }
  if (hold === current) current.timer = setTimeout(holdTick, 600);
}
function holdEnd() {
  if (!hold) return;
  clearTimeout(hold.timer);
  const {direction, sent} = hold;
  hold = null;
  if (!sent) action({action: "dim_" + direction});
}
for (const id of ["dim-down", "dim-up"]) {
  el(id).addEventListener("pointerdown", () => holdStart(el(id).dataset.hold));
  for (const type of ["pointerup", "pointerleave", "pointercancel"]) el(id).addEventListener(type, holdEnd);
}
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  // Pointer presses on dim buttons are handled above; a keyboard press is one step.
  if (button.dataset.hold && event.detail !== 0) return;
  if (button.id === "choose-dashboard") return chooseDashboard();
  if (button.id === "add-card") return action({action: "add_card", url_path: el("dashboard-choice").value,
    view_index: Number(el("view-choice").value), revision: dashboardRevision, style: el("card-style").value});
  const kind = button.dataset.action;
  if (!kind) return;
  if (kind === "restart" && !confirm("Restart Home Assistant now?")) return;
  if (kind === "skip_sequence" && !el("skip-confirm").checked) return notice("Tick the box first.", true);
  if (kind === "connect") return action(connectBody(button));
  if (kind === "prepare_firmware") return el("node-choice").value
    ? action({action: kind, file: el("node-choice").value}) : notice("Choose a proxy first.", true);
  if (kind === "scene") return action({action: "scene", effect: button.dataset.effect});
  if (kind === "finish_setup") return action(button.dataset.effect ? {action: kind, effect: button.dataset.effect} : {action: kind});
  if (kind === "confirm_test") return action({action: kind, result: button.dataset.result});
  if (kind === "sync_power") return action({action: kind, is_on: button.dataset.on === "yes"});
  if (kind === "stop_pairing") return action({action: kind, done: button.dataset.done === "yes"});
  action({action: kind, confirm: ["pair", "restart", "skip_sequence"].includes(kind), style: el("card-style").value});
});
el("observed-mode").addEventListener("change", () => {
  action({action: "sync_mode", effect: el("observed-mode").value});
});
el("dashboard-choice").addEventListener("change", loadViews);
el("view-choice").addEventListener("change", () => state && render(state));
el("card-style").addEventListener("change", () => {
  el("card-download").href = "api/dashboard-card?style=" + el("card-style").value;
});
refresh();
setInterval(refresh, 2000);
