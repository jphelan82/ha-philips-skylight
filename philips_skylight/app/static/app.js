"use strict";
const base = document.querySelector("base").href;
const csrf = document.querySelector('meta[name="csrf"]').content;
let busy = false;
let state = null;
const el = (id) => document.getElementById(id);
function notice(message, error = false) {
  el("notice").textContent = message;
  el("notice").className = error ? "error" : "";
  el("notice").hidden = !message;
}
function options(id, items) {
  const select = el(id);
  const current = select.value;
  const encoded = JSON.stringify(items);
  if (select.dataset.items === encoded) return;
  select.replaceChildren(...items.map((item) => {
    const option = document.createElement("option");
    option.value = typeof item === "string" ? item : item.entity_id;
    option.textContent = typeof item === "string" ? item : item.name;
    return option;
  }));
  if ([...select.options].some((item) => item.value === current)) select.value = current;
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
  el("controls").hidden = !data.configured;
  el("pairing").hidden = !data.configured;
  el("power").textContent = {on: "On", off: "Off", unknown: "Check power", unavailable: "Unavailable"}[data.state] || "Check power";
  el("light").className = "panel-light" + (data.state === "off" ? " off" : "");
  el("effect").textContent = data.effect || "Select a scene";
  el("sync").className = "sync" + (!data.power_synchronized ? " needed" : "");
  el("entity").textContent = data.entity_id || "Awaiting setup";
  el("version").textContent = "v" + data.version;
  options("service", data.transmit_services);
  options("proxy", data.proxy_sensors);
  if (!data.configured) el("setup").open = true;
  if (!el("scenes").children.length) {
    for (const effect of data.effects) {
      const button = document.createElement("button");
      button.textContent = effect;
      button.dataset.effect = effect;
      el("scenes").append(button);
    }
  }
  for (const button of el("scenes").children) button.classList.toggle("selected", button.dataset.effect === data.effect);
  for (const button of document.querySelectorAll("button")) {
    const install = button.dataset.action === "install";
    const control = button.closest("#controls, #pairing");
    const power = button.dataset.action === "on" || button.dataset.action === "off";
    button.disabled = busy || (!install && !data.connected)
      || (control && (data.restart_required || data.state === "unavailable"))
      || (power && !data.power_synchronized);
  }
}
async function refresh() {
  try {
    const response = await fetch(new URL("api/status", base), {cache: "no-store"});
    if (!response.ok) throw new Error("Cannot read add-on status");
    render(await response.json());
  } catch (error) { if (!busy) notice(error.message, true); }
}
async function action(body) {
  if (busy) return;
  busy = true;
  if (state) render(state);
  notice(body.action === "pair" ? "Sending pairing request for about ten seconds…" : "Applying…");
  try {
    const response = await fetch(new URL("api/action", base), {
      method: "POST", headers: {"Content-Type": "application/json", "X-Skylight-CSRF": csrf},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "Action failed");
    notice(body.action === "pair" ? "Request finished. Check the panel and original remote, then synchronize power."
      : body.action === "restart" ? "Home Assistant is restarting. This page will reconnect."
      : body.action === "setup" ? "Transmitter saved. Check the light’s power state below." : "");
  } catch (error) { notice(error.message, true); }
  finally { busy = false; await refresh(); }
}
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || (button.closest("form") && button.type === "submit")) return;
  if (button.dataset.effect) return action({action: "scene", effect: button.dataset.effect});
  if (button.dataset.sync) return action({action: "sync_power", is_on: button.dataset.sync === "true"});
  const kind = button.dataset.action;
  if (kind === "restart" && !confirm("Restart Home Assistant to activate the installed integration?")) return;
  if (kind === "pair" && !el("pair-confirm").checked) return notice("Confirm that you are ready to pair first.", true);
  if (kind) action({action: kind, confirm: kind === "pair" || kind === "restart"});
});
el("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action({action: "setup", ...Object.fromEntries(new FormData(event.target))});
});
refresh();
setInterval(refresh, 2000);
