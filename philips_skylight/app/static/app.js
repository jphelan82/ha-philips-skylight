"use strict";
const base = document.querySelector("base").href;
const csrf = document.querySelector('meta[name="csrf"]').content;
let busy = false;
let state = null;
// A restart is under way: the page asked for it, or Home Assistant went away
// while a restart was pending. Either way, failed requests are expected.
let restarting = false;
let pairStage = "pair";
let lastRemaining = 0;
let preparedNode = null;
// What the last status showed, so the page can say when an install has finished.
let lastProxyReady = null;
let lastFirmware = null;
let dashboardRevision = null;
let dashboardRead = 0;
const el = (id) => document.getElementById(id);
const show = (id, visible) => { el(id).hidden = !visible; };
// Home Assistant shows this page in a frame from its own address, so the page can
// read the open theme and match it, custom themes and dark mode included.
const THEME = {
  "--accent": ["--primary-color"], "--on-accent": ["--text-primary-color"],
  "--text": ["--primary-text-color"], "--muted": ["--secondary-text-color"],
  "--page": ["--primary-background-color"], "--card": ["--ha-card-background", "--card-background-color"],
  "--line": ["--divider-color"], "--done": ["--success-color"], "--error": ["--error-color"],
  "--radius": ["--ha-card-border-radius"], "--font": ["--ha-font-family-body", "--paper-font-body1_-_font-family"],
};
function followTheme() {
  try {
    const theirs = getComputedStyle(window.parent.document.documentElement);
    const ours = document.documentElement.style;
    for (const [name, sources] of Object.entries(THEME)) {
      const value = sources.map((source) => theirs.getPropertyValue(source).trim()).find(Boolean);
      if (value) ours.setProperty(name, value);
    }
    if (["light", "dark"].includes(theirs.colorScheme)) ours.colorScheme = theirs.colorScheme;
  } catch { /* Opened outside Home Assistant: keep the default colors. */ }
}
followTheme();
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
// The first setup step starts with what it needs: Device Builder, a proxy in it,
// and Home Assistant's connection to that proxy. Each line says how to fix it.
const LINKS = {
  builder: "https://my.home-assistant.io/redirect/supervisor_addon/?addon=5c53de3b_esphome&repository_url=https%3A%2F%2Fgithub.com%2Fesphome%2Fhome-assistant-addon",
  projects: "https://esphome.io/projects/",
  devices: "/config/integrations/integration/esphome",
};
function checkLine(id, state, text, link) {
  const parts = [];
  const mark = document.createElement("span");
  mark.className = "mark";
  mark.textContent = state === "ok" ? "✓" : "!";
  parts.push(mark);
  const words = document.createElement("span");
  words.textContent = text;
  parts.push(words);
  if (link) {
    const anchor = document.createElement("a");
    anchor.href = link.href;
    anchor.textContent = link.label;
    anchor.target = link.href.startsWith("/") ? "_top" : "_blank";
    anchor.rel = "noopener";
    parts.push(anchor);
  }
  el(id).className = state === "ok" ? "ok" : "todo";
  el(id).replaceChildren(...parts);
  show(id, Boolean(state));
}
function renderChecks(checks, visible) {
  show("prereq", Boolean(checks) && visible);
  // The recommended path is Device Builder. Building it yourself stays a quiet second choice.
  show("manual-firmware", Boolean(checks) && visible && !checks.builder);
  if (!checks) return;
  checkLine("check-builder", checks.builder ? "ok" : "todo", checks.builder
    ? "ESPHome Device Builder is installed."
    : "Install ESPHome Device Builder, ESPHome's app for Home Assistant, then start it. ",
  checks.builder ? null : {href: LINKS.builder, label: "Open it in the app store"});
  const nodes = (state.esphome_nodes || []).map((node) => node.node);
  if (checks.proxy === "ok") {
    checkLine("check-proxy", "ok", "Device Builder has a Bluetooth proxy: " + nodes.join(", ") + ".");
  } else if (checks.proxy === "adopt") {
    checkLine("check-proxy", "todo", "Home Assistant sees " + checks.unadopted.join(", ")
      + ", but Device Builder does not manage it yet. In Device Builder, select Adopt on it.");
  } else {
    checkLine("check-proxy", "todo", "Device Builder has no Bluetooth proxy yet. Set one up near the panel, then select Adopt on it in Device Builder. ",
      {href: LINKS.projects, label: "ESPHome's ready-made projects"});
  }
  const connections = Object.entries(checks.connections || {});
  const missing = connections.filter(([, value]) => value === "missing").map(([node]) => node);
  const offline = connections.filter(([, value]) => value === "offline").map(([node]) => node);
  const connected = connections.filter(([, value]) => value === "ok").map(([node]) => node);
  if (connected.length) {
    checkLine("check-connected", "ok", "Home Assistant is connected to " + connected.join(", ") + ".");
  } else if (offline.length) {
    checkLine("check-connected", "todo", offline.join(", ") + " is offline. Check that it has power and Wi-Fi.");
  } else if (missing.length) {
    checkLine("check-connected", "todo", "Home Assistant has not added " + missing.join(", ")
      + " yet. Add it where Home Assistant lists discovered ESPHome devices. ",
    {href: LINKS.devices, label: "Open ESPHome devices"});
  } else {
    checkLine("check-connected", "", "");
  }
}
// While a restart is pending, only Install and Restart Home Assistant stay usable.
// Restart needs the connection to Home Assistant, and Install does not.
function buttonDisabled(kind, data) {
  if (busy) return true;
  if (kind === "install") return false;
  if (kind === "restart") return !data.connected;
  return !data.connected || data.restart_required;
}
function render(data) {
  state = data;
  el("connection").textContent = !data.connected ? "Connecting" : data.proxy_online ? "Proxy online" : "Proxy offline";
  el("connection").className = "badge" + (data.connected && data.proxy_online ? " online" : "");
  const needsInstall = !data.installed || data.restart_required;
  show("installation", needsInstall);
  show("install", !data.installed);
  show("restart", data.installed && data.restart_required);
  if (data.restart_required && !data.connected) restarting = true;
  if (restarting && data.connected && !data.restart_required) {
    restarting = false;
    notice("Home Assistant has restarted. The Skylight integration is loaded.");
  }
  show("restart-status", restarting && data.restart_required);
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
  if (lastProxyReady === false && proxyReady && preparedNode) {
    notice("The proxy is back with the Skylight firmware. The install is complete.");
  }
  lastProxyReady = proxyReady;
  show("proxy-firmware", !proxyReady && nodes.some((node) => !node.has_skylight) && !preparedNode);
  options("node-choice", nodes.filter((node) => !node.has_skylight).map((node) => ({value: node.file, name: node.node})), "Choose a proxy");
  const installNode = preparedNode || (waiting.length === 1 ? waiting[0].node : null);
  show("proxy-install", !proxyReady && Boolean(installNode));
  el("proxy-node").textContent = installNode || "";
  if (data.device_builder) el("device-builder").href = data.device_builder;
  show("device-builder", Boolean(data.device_builder));
  renderChecks(data.prerequisites, !proxyReady);

  step("step-connect", data.configured, data.configured ? "✓" : proxyReady && data.proxies.length === 1 ? "Connecting…" : "");
  show("connect-choice", proxyReady && !data.configured && data.proxies.length > 1);
  const proxyNames = data.proxies.map((item) => ({...item, name: item.name + " · " + item.node}));
  options("proxy-choice", proxyNames, "Choose a proxy");
  options("proxy-change", proxyNames, "Choose a proxy");

  step("step-tracking", data.tracking === true, data.tracking === true ? "✓" : data.tracking === false ? "" : proxyReady ? "Checking…" : "");
  show("tracking-off", data.tracking === false);

  // The integration sends the pairing request for 10 seconds, then the test follows.
  const remaining = data.pairing_remaining || 0;
  if (lastRemaining && !remaining && !setupDone && pairStage === "pair") pairStage = "test";
  lastRemaining = remaining;
  show("pair-wait", remaining > 0);
  el("pair-countdown").textContent = "Pairing… " + remaining + " s";
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
  const firmware = data.firmware?.status;
  const cards = data.outdated_cards || [];
  const nodeNames = (data.firmware?.nodes || []).join(", ");
  const keyless = nodes.filter((node) => node.has_skylight && node.api_key === false).map((node) => node.node);
  const needed = firmware === "files" || firmware === "install" || cards.length > 0;
  show("updates", ready && (needed || keyless.length > 0));
  // The API key is the user's choice, so a page with only that item says so.
  el("updates-title").textContent = needed ? "Needs attention" : "Needs attention (optional)";
  show("proxy-key", keyless.length > 0);
  el("keyless-nodes").textContent = keyless.join(", ");
  show("firmware-files", firmware === "files");
  show("firmware-install", firmware === "install");
  if (lastFirmware === "install" && firmware === "current") {
    notice("The proxy runs the new Skylight firmware " + data.firmware.version + ". The install is complete.");
  }
  lastFirmware = firmware;
  el("firmware-nodes").textContent = nodeNames || "your proxy";
  el("install-nodes").textContent = nodeNames || "your proxy";
  if (data.device_builder) el("update-builder").href = data.device_builder;
  show("update-builder", Boolean(data.device_builder));
  show("card-update", cards.length > 0);
  el("card-dashboards").textContent = cards.join(", ");
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
    button.disabled = buttonDisabled(button.dataset.action, data);
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
  followTheme();  // The theme can change while the page is open.
  try { render(await get("api/status")); }
  catch (error) {
    // During a restart the page's requests fail too, because they pass through Home Assistant.
    if (restarting || state?.restart_required) {
      restarting = true;
      show("restart-status", true);
      notice("");
    } else if (!busy) notice(error.message, true);
  }
}
const messages = {
  test: "Sending…",
};
const results = {
  restart: () => { restarting = true; return ""; },
  prepare_firmware: () => "",
  allow_tracking: () => "",
  pair: () => "",
  test: () => "",
  confirm_test: (body) => body.result === "none" ? "The panel did not respond. Pair again: switch the power off and on, then select Pair." : "",
  finish_setup: () => "Setup is complete.",
  setup: () => "",
  create_dashboard: (body, result) => result.created ? "Dashboard created." : "You already have a Skylight dashboard.",
  add_card: (body, result) => result.added ? "Card added." : "That view already has the card.",
  skip_sequence: () => "Counter moved forward. Try the power button above.",
  unpair_all: () => "Unpairing for 10 seconds. When the panel blinks, pair your remote, then select Continue.",
  start_over: () => "",
  rhythm_start: () => "Schedule started. The panel blinks.",
  update_firmware: () => "Firmware files updated. Now install them on the proxy.",
  update_card: (body, result) => result.updated?.length ? "Card updated on " + result.updated.join(", ") + "." : "The card is already current.",
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
    if (body.action === "test") pairStage = "ask";
    if (body.action === "confirm_test") pairStage = body.result === "none" ? "pair" : "mode";
    if (body.action === "finish_setup") pairStage = "pair";
    if (body.action === "skip_sequence") el("skip-confirm").checked = false;
    if (body.action === "unpair_all") el("unpair-confirm").checked = false;
    if (body.action === "start_over") pairStage = "pair";
    if (body.action === "add_card") await loadViews();
  } catch (error) {
    // Home Assistant can drop the request as it shuts down for the restart.
    if (body.action === "restart") { restarting = true; notice(""); }
    else notice(error.message, true);
  }
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
  // Keep a steady 0.6-second beat, like the remote: set the next step first,
  // so the time a request takes never adds a pause.
  current.timer = setTimeout(holdTick, 600);
  if (current.busy) return;
  current.busy = true;
  await post({action: "dim_hold", direction: current.direction});
  current.busy = false;
}
function holdEnd() {
  if (!hold) return;
  clearTimeout(hold.timer);
  const {direction, sent} = hold;
  hold = null;
  if (!sent) action({action: "dim_" + direction});
}
for (const id of ["dim-down", "dim-up"]) {
  const button = el(id);
  button.addEventListener("pointerdown", (event) => {
    // Keep the finger's events on this button, even if it slides a little.
    if (event && button.setPointerCapture) button.setPointerCapture(event.pointerId);
    holdStart(button.dataset.hold);
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) button.addEventListener(type, holdEnd);
  // On a phone, a long touch opens the phone's own menu and cancels the touch.
  // Stop that, so the hold keeps going until the finger lifts.
  button.addEventListener("contextmenu", (event) => event.preventDefault());
}
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  // Pointer presses on dim buttons are handled above; a keyboard press is one step.
  if (button.dataset.hold && event.detail !== 0) return;
  if (button.id === "choose-dashboard") return chooseDashboard();
  if (button.id === "add-card") return action({action: "add_card", url_path: el("dashboard-choice").value,
    view_index: Number(el("view-choice").value), revision: dashboardRevision});
  const kind = button.dataset.action;
  if (!kind) return;
  if (kind === "restart" && !confirm("Restart Home Assistant now?")) return;
  if (kind === "skip_sequence" && !el("skip-confirm").checked) return notice("Tick the box first.", true);
  if (kind === "unpair_all" && !el("unpair-confirm").checked) return notice("Tick the box first.", true);
  if (kind === "connect") return action(connectBody(button));
  if (kind === "prepare_firmware") return el("node-choice").value
    ? action({action: kind, file: el("node-choice").value}) : notice("Choose a proxy first.", true);
  if (kind === "scene") return action({action: "scene", effect: button.dataset.effect});
  if (kind === "finish_setup") return action(button.dataset.effect ? {action: kind, effect: button.dataset.effect} : {action: kind});
  if (kind === "confirm_test") return action({action: kind, result: button.dataset.result});
  if (kind === "sync_power") return action({action: kind, is_on: button.dataset.on === "yes"});
  action({action: kind, confirm: ["pair", "restart", "skip_sequence", "unpair_all"].includes(kind)});
});
el("observed-mode").addEventListener("change", () => {
  action({action: "sync_mode", effect: el("observed-mode").value});
});
el("dashboard-choice").addEventListener("change", loadViews);
el("view-choice").addEventListener("change", () => state && render(state));
refresh();
setInterval(refresh, 2000);
