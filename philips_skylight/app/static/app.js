"use strict";
const base = document.querySelector("base").href;
const csrf = document.querySelector('meta[name="csrf"]').content;
let busy = false;
let state = null;
let dashboardRevision = null;
let dashboardRead = 0;
let initializedName = false;
let setupPresentation = null;
let matchingPresentation = null;
const el = (id) => document.getElementById(id);
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
function render(data) {
  state = data;
  el("connection").textContent = data.connected ? "Connected locally" : "Reconnecting";
  el("connection").className = "badge" + (data.connected ? " online" : "");
  el("installation").hidden = data.installed && !data.restart_required;
  el("install").hidden = data.installed;
  el("restart").hidden = !data.restart_required;
  el("install-message").textContent = data.installed
    ? "The companion integration is installed. Restart Home Assistant to activate it."
    : "Install the bundled integration to create the native light entity. No MQTT broker is needed.";
  for (const id of ["pairing", "recovery", "matching", "dashboard"]) el(id).hidden = !data.configured;
  const presentation = !data.configured ? "proxy" : data.first_setup ? "pair" : "ready";
  const initial = presentation !== "ready";
  el("title").textContent = initial ? "Set up Skylight" : "Skylight";
  el("first-setup").hidden = !initial;
  el("next-step").textContent = data.configured ? "Pair, then record initial state" : "Connect your proxy";
  el("setup-guidance").textContent = data.configured
    ? "Enable the proxy's remote-tracking permission, pair this new transmitter, then record the panel's power and mode below. Already paired transmitters can skip pairing."
    : data.proxies.length ? "Choose your Bluetooth proxy below and save. A single compatible proxy is selected for you."
    : "Prepare your Bluetooth proxy with the downloadable ESPHome package, then choose it below. Your existing Wi-Fi and node settings are kept.";
  if (setupPresentation !== presentation) {
    el("maintenance").open = initial;
    el("setup").open = !data.configured;
    el("firmware").open = !data.configured && !data.proxies.length;
    el("tracking").open = data.configured && data.first_setup;
    el("pairing").open = data.configured && data.first_setup;
    setupPresentation = presentation;
  }
  const needsMatch = data.configured && !data.power_synchronized;
  if (matchingPresentation !== needsMatch) {
    el("matching").open = needsMatch;
    matchingPresentation = needsMatch;
  }
  if (!initializedName && data.configured) {
    el("light-name").value = data.name;
    initializedName = true;
  }
  el("entity").textContent = data.entity_id || "Awaiting setup";
  el("version").textContent = "v" + data.version;
  options("service", data.transmit_services, "Choose an action");
  options("proxy", data.proxy_sensors, "Choose a sensor");
  options("proxy-choice", data.proxies.map((item) => ({...item, name: item.name + " · " + item.node})), "Choose a proxy");
  options("observed-mode", ["Unknown", ...data.effects]);
  if (!busy && data.connected) el("observed-mode").value = data.effects.includes(data.effect) ? data.effect : "Unknown";
  el("proxy-hint").textContent = data.proxies.length === 1
    ? "One compatible proxy found and selected. Save to use it."
    : data.proxies.length ? "Choose the proxy near your panel." : "No matched proxy found. Prepare the firmware, or use advanced selection.";
  el("firmware-status").textContent = data.proxies.length
    ? "Compatible transmitter firmware found. You can skip the firmware update."
    : "No compatible transmitter has been matched yet. Install the package if your proxy needs it.";
  el("recorded-state").textContent = "Current record: " + data.state + " · " + (data.effect || "mode unknown") + ". This is an estimate.";
  el("observed-mode").disabled = busy || !data.connected || data.restart_required;
  for (const button of document.querySelectorAll("button")) {
    const install = button.dataset.action === "install";
    button.disabled = busy || (!install && (!data.connected || data.restart_required));
  }
  el("add-card").disabled ||= !dashboardRevision || !el("view-choice").value;
}
async function get(path) {
  const response = await fetch(new URL(path, base), {cache: "no-store"});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Cannot read add-on status");
  return result;
}
async function refresh() {
  try { render(await get("api/status")); }
  catch (error) { if (!busy) notice(error.message, true); }
}
async function action(body) {
  if (busy) return;
  busy = true;
  if (state) render(state);
  const recording = ["sync_state", "sync_power", "sync_mode"].includes(body.action);
  notice(recording ? "" : body.action === "pair" ? "Sending pairing request for about ten seconds…" : "Applying…");
  try {
    const response = await fetch(new URL("api/action", base), {
      method: "POST", headers: {"Content-Type": "application/json", "X-Skylight-CSRF": csrf},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "Action failed");
    if (result.url) {
      el("dashboard-link").href = result.url;
      el("dashboard-link").hidden = false;
    }
    notice(body.action === "pair" ? "Request finished. Check the panel and original remote, then record the starting state."
      : body.action === "restart" ? "Home Assistant is restarting. This page will reconnect."
      : body.action === "setup" ? "Transmitter saved. Enable remote tracking, pair on first setup, and record the starting state."
      : body.action === "create_dashboard" ? (result.created ? "Dashboard created. Use Open dashboard below." : "Existing dashboard preserved. Use Open dashboard below.")
      : body.action === "add_card" ? (result.added ? "Card added. Use Open dashboard below." : "This card is already in that view. No changes made.")
      : body.action === "skip_sequence" ? "Sequence skipped forward. Try a power or mode command and watch the panel." : "");
    if (body.action === "pair") el("pair-confirm").checked = false;
    if (body.action === "skip_sequence") el("skip-confirm").checked = false;
    if (body.action === "setup") el("matching").open = true;
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
    el("dashboard-hint").textContent = result.views.length
      ? "Adds the card to this view while preserving its existing controls."
      : "This dashboard has no editable views. Use the manual card download or create a separate dashboard.";
  } catch (error) { if (read === dashboardRead) notice(error.message, true); }
  if (state) render(state);
}
async function chooseDashboard() {
  try {
    const result = await get("api/dashboards");
    options("dashboard-choice", result.dashboards.map((item) => ({value: item.url_path, name: item.title})), "Choose a dashboard");
    el("dashboard-target").hidden = false;
    el("dashboard-hint").textContent = result.dashboards.length ? "Choose a dashboard and view." : "No editable storage dashboards found. Use the manual download or create a dashboard.";
    await loadViews();
  } catch (error) { notice(error.message, true); }
}
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled || (button.closest("form") && button.type === "submit")) return;
  if (button.id === "choose-dashboard") return chooseDashboard();
  if (button.id === "add-card") return action({action: "add_card", url_path: el("dashboard-choice").value,
    view_index: Number(el("view-choice").value), revision: dashboardRevision, style: el("card-style").value});
  const kind = button.dataset.action;
  if (kind === "restart" && !confirm("Restart Home Assistant to activate the installed integration?")) return;
  if (kind === "pair" && !el("pair-confirm").checked) return notice("Confirm that you are ready to pair first.", true);
  if (kind === "skip_sequence" && !el("skip-confirm").checked) return notice("Confirm that the panel ignores this transmitter first.", true);
  if (kind) action({action: kind, confirm: ["pair", "restart", "skip_sequence"].includes(kind), style: el("card-style").value});
});
el("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {action: "setup", name: el("light-name").value};
  if (el("advanced").open) {
    body.transmit_service = el("service").value;
    body.proxy_entity = el("proxy").value;
  } else body.proxy = el("proxy-choice").value;
  action(body);
});
el("match-form").addEventListener("submit", (event) => {
  event.preventDefault();
  // The integration already has the latest mode; never overwrite a newer remote press.
  action({action: "sync_power", is_on: el("observed-power").value === "on"});
});
el("observed-mode").addEventListener("change", () => {
  action({action: "sync_mode", effect: el("observed-mode").value});
});
el("dashboard-choice").addEventListener("change", loadViews);
el("view-choice").addEventListener("change", () => state && render(state));
el("card-style").addEventListener("change", () => {
  el("card-download").href = "api/dashboard-card?style=" + el("card-style").value;
  el("card-download").textContent = "Download " + el("card-style").value + " Skylight card";
});
refresh();
setInterval(refresh, 2000);
