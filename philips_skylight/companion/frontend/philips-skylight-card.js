// The Philips Skylight card. The integration builds its config from Home Assistant's
// own cards and the light's current entity IDs, so a renamed entity still works.
// Plain JavaScript with no imports: Home Assistant serves this file as it is.
const CARD_TYPE = "philips-skylight-card";
// About the height of the controls, in Home Assistant's 50-pixel rows.
const CARD_SIZE = 8;
// After a failed request, such as during a restart, ask again after this long.
const RETRY_MS = 10000;

class PhilipsSkylightCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("The card needs a config");
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._card) this._card.hass = hass;
    // Home Assistant sets hass on every state change. Only the first one asks,
    // and after a failure, the first one after the retry time.
    if (!this._loading && (!this._card || (this._failed && Date.now() >= this._retryAt))) {
      this._load();
    }
  }

  get hass() {
    return this._hass;
  }

  async _load() {
    this._loading = true;
    let element;
    try {
      const result = await this._hass.callWS({type: "philips_skylight/card"});
      element = await this._create(result.card);
      this._failed = false;
    } catch (error) {
      element = this._error(error && error.message ? error.message : String(error));
      this._failed = true;
      this._retryAt = Date.now() + RETRY_MS;
    }
    // The newest hass, since it can change while the request runs.
    element.hass = this._hass;
    this._card = element;
    this._loading = false;
    this.replaceChildren(element);
  }

  async _create(config) {
    const helpers = await window.loadCardHelpers();
    const element = helpers.createCardElement(config);
    // A card type that loads late asks for a rebuild. Build it again from the same config.
    element.addEventListener("ll-rebuild", (event) => {
      event.stopPropagation();
      this._create(config).then((rebuilt) => {
        rebuilt.hass = this._hass;
        if (this._card === element) {
          this._card = rebuilt;
          this.replaceChildren(rebuilt);
        }
      });
    }, {once: true});
    return element;
  }

  _error(message) {
    const card = document.createElement("ha-card");
    card.setAttribute("header", "Philips Skylight");
    const text = document.createElement("div");
    text.className = "card-content";
    text.textContent = message;
    card.append(text);
    return card;
  }

  getCardSize() {
    if (this._card && typeof this._card.getCardSize === "function") return this._card.getCardSize();
    return CARD_SIZE;
  }

  getGridOptions() {
    if (this._card && typeof this._card.getGridOptions === "function") return this._card.getGridOptions();
    return {};
  }
}

// A second copy of this script, such as an old cached one, must not throw.
if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, PhilipsSkylightCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Philips Skylight",
    description: "Controls for the Philips Skylight panel, with its modes, dimming and state correction.",
    preview: true,
  });
}
