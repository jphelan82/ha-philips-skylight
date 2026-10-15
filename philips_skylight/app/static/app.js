"use strict";
const base = document.querySelector("base").href;
const csrf = document.querySelector('meta[name="csrf"]').content;
let busy = false;
let state = null;
// A restart is under way: the page asked for it, or Home Assistant went away
// while a restart was pending. Either way, failed requests are expected.
let restarting = false;
let pairStage = "pair";
// Unpair remotes: ready → wait (unpair running) → ask (did it blink?) → remote (continue to pairing).
let unpairStage = "ready";
let unpairSeen = false;
let unpairStarted = 0;
let lastRemaining = 0;
let preparedNode = null;
// A short pause after the last change of the observed mode, before the page sends it.
let modeTimer = null;
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
// A failed status poll shows a notice. The next good poll clears it, but leaves
// any other notice, such as an action's result, in place.
let pollNotice = false;
function notice(message, error = false, fromPoll = false) {
  el("notice").textContent = message;
  el("notice").className = error ? "error" : "";
  el("notice").hidden = !message;
  pollNotice = Boolean(message) && fromPoll;
}
// Disabled or hidden controls lose keyboard focus. Put it back on the same control,
// or else on the nearest usable control after it, or else before it.
function keepFocus(previous) {
  const now = document.activeElement;
  if (!previous || previous === document.body || (now && now !== document.body && now !== previous)) return;
  const usable = (item) => !item.disabled && item.getClientRects().length > 0;
  if (usable(previous)) return previous.focus();
  const items = [...document.querySelectorAll("button, input, select, summary")];
  const at = items.indexOf(previous);
  if (at < 0) return;
  (items.slice(at + 1).find(usable) || items.slice(0, at).reverse().find(usable))?.focus();
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
    // A new tab keeps this page open: setup continues here when the user comes back.
    anchor.target = "_blank";
    anchor.rel = "noopener";
    parts.push(anchor);
  }
  el(id).className = state === "ok" ? "ok" : "todo";
  el(id).replaceChildren(...parts);
  show(id, Boolean(state));
}
// Device Builder and Home Assistant show a proxy's friendly name, so lead with it.
function nodeLabel(name) {
  const node = (state?.esphome_nodes || []).find((item) => item.node === name);
  return node?.friendly_name && node.friendly_name !== name ? node.friendly_name + " (" + name + ")" : name;
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
  const nodes = (state.esphome_nodes || []).map((node) => nodeLabel(node.node));
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
  const missing = connections.filter(([, value]) => value === "missing").map(([node]) => nodeLabel(node));
  const offline = connections.filter(([, value]) => value === "offline").map(([node]) => nodeLabel(node));
  const connected = connections.filter(([, value]) => value === "ok").map(([node]) => nodeLabel(node));
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
  // Unpair remotes: only the current step's buttons work.
  if (kind === "unpair_all" && unpairStage !== "ready") return true;
  if (kind === "unpair_blinked" && unpairStage !== "ask") return true;
  if (kind === "start_over" && unpairStage !== "remote") return true;
  if (kind === "install") return false;
  if (kind === "restart") return !data.connected;
  return !data.connected || data.restart_required;
}
function render(data) {
  state = data;
  el("connection").textContent = !data.connected ? "Connecting" : data.proxy_online ? "Proxy online" : "Proxy offline";
  // Before a proxy has the Skylight firmware, "Proxy offline" reads like a fault.
  show("connection", !data.connected || data.proxies.length > 0);
  el("connection").className = "badge" + (data.connected && data.proxy_online ? " online" : "");
  const needsInstall = !data.installed || data.restart_required;
  // The add-on keeps running when its own install fails at startup, so the page can say why.
  show("installation", needsInstall || Boolean(data.install_error));
  show("install-message", needsInstall);
  el("install-error").textContent = data.install_error
    ? "The add-on could not install its integration: " + String(data.install_error).replace(/\.$/, "")
      + ". Restart the add-on. If this keeps happening, open an issue."
    : "";
  show("install-error", Boolean(data.install_error));
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
  // Once a proxy has the firmware files, the only step left is its install.
  show("proxy-firmware", !proxyReady && nodes.some((node) => !node.has_skylight) && !preparedNode && waiting.length === 0);
  options("node-choice", nodes.filter((node) => !node.has_skylight).map((node) => ({value: node.file, name: nodeLabel(node.node)})), "Choose a proxy");
  const installNode = preparedNode || (waiting.length === 1 ? waiting[0].node : null);
  show("proxy-install", !proxyReady && Boolean(installNode));
  el("proxy-node").textContent = installNode ? nodeLabel(installNode) : "";
  if (data.device_builder) el("device-builder").href = data.device_builder;
  show("device-builder", Boolean(data.device_builder));
  renderChecks(data.prerequisites, !proxyReady);

  // With one proxy, the add-on connects it by itself. The button stays in case that fails.
  step("step-connect", data.configured, data.configured ? "✓" : "");
  show("connect-choice", proxyReady && !data.configured);
  const proxyNames = data.proxies.map((item) => ({...item, name: item.name + " · " + item.node}));
  options("proxy-choice", proxyNames, "Choose a proxy");
  options("proxy-change", proxyNames, "Choose a proxy");

  step("step-tracking", data.tracking === true, data.tracking === true ? "✓" : data.tracking === false ? "" : proxyReady ? "Checking…" : "");
  show("tracking-off", data.tracking === false);

  // The integration sends the pairing request for 10 seconds, then the test follows.
  const remaining = data.pairing_remaining || 0;
  const unpairing = data.last_command === "unpair all";
  if (lastRemaining && !remaining && !setupDone && pairStage === "pair" && !unpairing) pairStage = "test";
  // The stage lives only in this page. After a reload, the add-on says that Home Assistant has paired.
  if (data.first_setup && data.setup_paired === true && !remaining && pairStage === "pair") pairStage = "test";
  // The unpair runs from Unpair remotes, far down the page, so its countdown shows there.
  if (unpairStage === "wait") {
    if (unpairing && remaining) {
      unpairSeen = true;
      besideButton("unpair_all", "Unpairing… " + remaining + " s. The panel blinks when it unpairs.", false);
    } else if (unpairSeen || Date.now() - unpairStarted > 15000) {
      unpairStage = "ask";
      besideButton("unpair_all", "", false);
    }
  }
  const unpairAt = {ready: 1, wait: 1, ask: 2, remote: 3}[unpairStage];
  [1, 2, 3].forEach((n) => {
    el("unpair-" + n).className = n < unpairAt ? "done" : n > unpairAt ? "later" : "";
    el("unpair-" + n + "-status").textContent = n < unpairAt ? "✓" : "";
  });
  lastRemaining = remaining;
  show("pair-wait", remaining > 0 && !unpairing);
  el("pair-countdown").textContent = "Pairing… " + remaining + " s";
  step("step-pair", setupDone, setupDone ? "✓" : remaining ? "Pairing…" : "");
  const pairing = data.configured && !setupDone && !remaining;
  show("pair-steps", pairing && pairStage === "pair");
  show("pair-test", pairing && pairStage === "test");
  show("pair-ask", pairing && pairStage === "ask");
  show("pair-remote", pairing && pairStage === "remote");
  // After Unpair all, the wall remote is certainly gone. After a first pairing, it often still works.
  const afterUnpair = data.setup_after_unpair === true;
  el("pair-remote-text").textContent = afterUnpair
    ? "It works. Unpair all removed your wall remote too, so pair the remote again now."
    : "It works. Pairing Home Assistant often unpairs your wall remote. Press the remote's power button. If the panel does not respond, pair the remote again:";
  show("remote-skip", !afterUnpair);
  show("pair-mode", pairing && pairStage === "mode");

  const ready = data.configured && !needsInstall && setupDone;
  show("control", ready);
  show("dashboard", ready);
  show("fixes", ready);
  const firmware = data.firmware?.status;
  const cards = data.outdated_cards || [];
  const nodeNames = (data.firmware?.nodes || []).map(nodeLabel).join(", ");
  const keyless = nodes.filter((node) => node.has_skylight && node.api_key === false).map((node) => nodeLabel(node.node));
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
  if (!busy && !modeTimer && data.connected) el("observed-mode").value = data.effects.includes(data.effect) ? data.effect : "Unknown";
  options("service", data.transmit_services, "Choose an action");
  options("proxy", data.proxy_sensors, "Choose a sensor");
  el("version").textContent = "v" + data.version;
  for (const button of document.querySelectorAll("button")) {
    button.disabled = buttonDisabled(button.dataset.action, data);
  }
  el("add-card").disabled ||= !dashboardRevision || !el("view-choice").value;
}
// The add-on answers in JSON. Plain text comes from its access check, which refuses
// an old action session after the add-on restarts. An HTML page comes from Home Assistant.
async function answer(response, fallback) {
  if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
    const text = await response.text().catch(() => "");
    if (response.status === 403 && text.includes("Invalid action session")) {
      throw new Error("The add-on restarted. Reload this page.");
    }
    throw new Error("The add-on did not answer as expected. HTTP status " + response.status + ".");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || fallback);
  return result;
}
async function get(path) {
  const response = await fetch(new URL(path, base), {cache: "no-store"});
  return answer(response, "Cannot read the add-on status");
}
async function refresh() {
  followTheme();  // The theme can change while the page is open.
  try {
    const data = await get("api/status");
    if (pollNotice) notice("");
    render(data);
  } catch (error) {
    // During a restart the page's requests fail too, because they pass through Home Assistant.
    if (restarting || state?.restart_required) {
      restarting = true;
      show("restart-status", true);
      notice("");
    } else if (!busy) notice(error.message, true, true);
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
  unpair_all: () => "",
  start_over: () => "Home Assistant pairs next. Follow the setup steps at the top of this page.",
  rhythm_start: () => "Schedule started. The panel blinks.",
  update_firmware: () => "Firmware files updated. Now install them on the proxy.",
  update_card: (body, result) => result.updated?.length ? "Card updated on " + result.updated.join(", ") + "." : "The card is already current.",
};
// The notice bar sits at the top of the page. A result from further down also
// shows next to the button that caused it, where the user is looking.
const BESIDE = {create_dashboard: "dashboard-result", add_card: "dashboard-result",
  unpair_all: "unpair-1-result", start_over: "unpair-3-result", skip_sequence: "skip-result",
  update_card: "card-result"};
function besideButton(kind, message, error) {
  const id = BESIDE[kind];
  if (!id) return;
  el(id).textContent = message;
  el(id).className = "result" + (error ? " error" : "");
  show(id, Boolean(message));
}
function clearUnpairResults() {
  for (const id of ["unpair-1-result", "unpair-3-result"]) { el(id).textContent = ""; show(id, false); }
}
async function action(body) {
  if (busy) return;
  busy = true;
  const focused = document.activeElement;
  let scrollToSetup = false;
  if (state) render(state);
  notice(messages[body.action] || "");
  try {
    const response = await fetch(new URL("api/action", base), {
      method: "POST", headers: {"Content-Type": "application/json", "X-Skylight-CSRF": csrf},
      body: JSON.stringify(body),
    });
    const result = await answer(response, "That did not work");
    if (!result.ok) throw new Error(result.error || "That did not work");
    if (result.url) {
      el("dashboard-link").href = result.url;
      el("dashboard-link").hidden = false;
    }
    const message = results[body.action] ? results[body.action](body, result) : "";
    notice(message);
    besideButton(body.action, message, false);
    if (body.action === "prepare_firmware") {
      preparedNode = (state?.esphome_nodes || []).find((node) => node.file === body.file)?.node || body.file;
    }
    if (body.action === "test") pairStage = "ask";
    if (body.action === "confirm_test") pairStage = body.result === "none" ? "pair" : "remote";
    if (body.action === "finish_setup") { pairStage = "pair"; clearUnpairResults(); }
    if (body.action === "skip_sequence") el("skip-confirm").checked = false;
    if (body.action === "unpair_all") { el("unpair-confirm").checked = false; unpairStage = "wait"; unpairSeen = false; unpairStarted = Date.now(); }
    // The setup checklist shows only after the next status, so scroll after the refresh.
    if (body.action === "start_over") { pairStage = "pair"; unpairStage = "ready"; clearUnpairResults(); scrollToSetup = true; }
    if (body.action === "add_card") await loadViews();
  } catch (error) {
    // Home Assistant can drop the request as it shuts down for the restart.
    if (body.action === "restart") { restarting = true; notice(""); }
    else { notice(error.message, true); besideButton(body.action, error.message, true); }
  }
  finally {
    busy = false;
    await refresh();
    keepFocus(focused);
    if (scrollToSetup && !el("setup").hidden) el("setup").scrollIntoView({behavior: "smooth"});
  }
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
    const result = await answer(response, "That did not work");
    if (!result.ok) throw new Error(result.error || "That did not work");
  } catch (error) { notice(error.message, true); }
}
function holdStart(button, pointerId) {
  if (hold || busy || button.disabled || !state || !state.connected || state.restart_required) return false;
  hold = {direction: button.dataset.hold, pointerId, sent: false, busy: false};
  hold.timer = setTimeout(holdTick, 450);
  return true;
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
// Only a lifted finger sends the short step. A cancelled press sends nothing.
// Another finger, on the other dim button, does not end this hold.
function holdEnd(pointerId, lifted) {
  if (!hold || (pointerId !== undefined && pointerId !== hold.pointerId)) return;
  clearTimeout(hold.timer);
  const {direction, sent} = hold;
  hold = null;
  if (lifted && !sent) action({action: "dim_" + direction});
}
for (const id of ["dim-down", "dim-up"]) {
  const button = el(id);
  button.addEventListener("pointerdown", (event) => {
    // Only the main mouse button, a finger or a pen starts a hold.
    if (event.button !== 0 || !holdStart(button, event.pointerId)) return;
    // Keep the finger's events on this button, even if it slides a little.
    if (button.setPointerCapture) button.setPointerCapture(event.pointerId);
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
    button.addEventListener(type, (event) => holdEnd(event.pointerId, type === "pointerup"));
  }
  // On a phone, a long touch opens the phone's own menu and cancels the touch.
  // Stop that, so the hold keeps going until the finger lifts.
  button.addEventListener("contextmenu", (event) => event.preventDefault());
}
// A hold stops when the page loses focus or goes out of sight, since no lift follows.
window.addEventListener("blur", () => holdEnd(undefined, false));
document.addEventListener("visibilitychange", () => { if (document.hidden) holdEnd(undefined, false); });
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
  if ((kind === "skip_sequence" && !el("skip-confirm").checked) || (kind === "unpair_all" && !el("unpair-confirm").checked)) {
    notice("Tick the box first.", true);
    return besideButton(kind, "Tick the box first.", true);
  }
  const focused = document.activeElement;
  if (kind === "remote_paired") {
    pairStage = "mode";
    if (state) render(state);
    return keepFocus(focused);
  }
  if (kind === "unpair_blinked") {
    const blinked = button.dataset.blinked === "yes";
    unpairStage = blinked ? "remote" : "ready";
    clearUnpairResults();
    besideButton("unpair_all", blinked ? "" : "The panel did not unpair. Switch the power off and on, wait until it is back on, then select Unpair all straight away.", !blinked);
    if (state) render(state);
    return keepFocus(focused);
  }
  if (kind === "connect") return action(connectBody(button));
  if (kind === "prepare_firmware") return el("node-choice").value
    ? action({action: kind, file: el("node-choice").value}) : notice("Choose a proxy first.", true);
  if (kind === "scene") return action({action: "scene", effect: button.dataset.effect});
  if (kind === "finish_setup") return action(button.dataset.effect ? {action: kind, effect: button.dataset.effect} : {action: kind});
  if (kind === "confirm_test") return action({action: kind, result: button.dataset.result});
  if (kind === "sync_power") return action({action: kind, is_on: button.dataset.on === "yes"});
  action({action: kind, confirm: ["pair", "restart", "skip_sequence", "unpair_all"].includes(kind)});
});
// Arrow keys on a closed list can send a change at each step. Send only the last
// one, after a short pause. If another action is still running, wait for it.
function sendMode() {
  if (busy) { modeTimer = setTimeout(sendMode, 300); return; }
  modeTimer = null;
  action({action: "sync_mode", effect: el("observed-mode").value});
}
el("observed-mode").addEventListener("change", () => {
  clearTimeout(modeTimer);
  modeTimer = setTimeout(sendMode, 600);
});
el("dashboard-choice").addEventListener("change", loadViews);
el("view-choice").addEventListener("change", () => state && render(state));
refresh();
setInterval(refresh, 2000);
