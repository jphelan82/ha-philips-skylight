# Philips Skylight for Home Assistant

> [!WARNING]
> **Work in progress.** If you found this project by chance: I am still
> developing and testing it. You are welcome to try it. Expect parts that do not
> work fully yet, and expect bugs and errors.
>
> **One Skylight only.** I have tested this with one Skylight panel. Support for
> several Skylights is not built and not tested.

The Philips LED Skylight panel comes with a remote and nothing else. It has no
app, no Wi-Fi and no Hue support. This project lets Home Assistant act as a
second remote. You get a power toggle, the six modes and dim buttons on your
dashboard and in automations. Your original remote keeps working.

Home Assistant talks to the panel through an ESPHome Bluetooth proxy. You do not
need a cloud account, an MQTT broker or a custom dashboard card.

## Read this first: what it cannot do

This is an experimental project. Please read these limits before you install it.

- **The panel never reports what it is doing.** Home Assistant guesses the power
  and mode from the commands it sends and the remote presses it hears. The guess
  is often right, but it is still a guess.
- **The guess goes wrong sometimes.** A missed remote press, a wall switch, a
  power cut, or a restart of Home Assistant or the proxy all put it out of step.
  When that happens, you look at the panel and tell Home Assistant what you see.
- **Power is a toggle.** The panel has one on/off command, not separate on and
  off commands. If Home Assistant thinks the light is on when it is off, then
  "turn on" does nothing, and "turn off" turns it on. A mode button always
  leaves the panel on, in that mode.
- **It supports one Skylight.** It was built and tested with one panel.
  Support for several panels is not built yet. A panel obeys only the senders
  it has paired with. So any panel that paired with Home Assistant responds to
  its commands, and a second panel paired the same way responds too. Home
  Assistant also tracks every compatible remote it hears, so a second panel's
  remote changes the recorded state.
- **Dimming is relative.** Each tap is one step darker or brighter. No
  brightness slider or color temperature control exists.
- **It is tested on one setup.** One owner tested it with the NatureConnect/BioUp
  17.7 × 25.6 inch panel and an ESP32-C3 proxy. Other models are unknown.
- **The add-on needs Home Assistant OS or Supervised.** For Container or Core
  installs, use the [integration-only guide](docs/INTEGRATION.md).

If you want a dependable on/off status for automations, this project cannot
give you one. If you want a remote on your phone and in your dashboard, it
does that well.

## Wall switches

Leave the panel's wall switch on. Control the panel with its remote, its wall
remote, or Home Assistant. A wall switch cuts the power without telling Home
Assistant, so the recorded state goes wrong. You need the wall switch or the
breaker only for pairing.

If the panel's power runs through a **smart** wall switch in Home Assistant, you
can keep the record in step with an automation. When the switch turns off,
press **Record panel off**. When the switch turns back on, record what the panel
does when its power returns.

## What you need

- Home Assistant OS or Supervised, version 2026.6 or newer.
- A Philips Skylight panel.
- An ESPHome Bluetooth proxy near the panel, set up in ESPHome Device Builder.
  ESPHome 2026.4.5 or newer.

## Install

1. In Home Assistant, open **Settings → Apps → App store → Repositories**. On
   older versions, this menu is called **Add-ons**. Add
   `https://github.com/jphelan82/ha-philips-skylight`.
2. Install **Philips Skylight**. Turn on **Start on boot**, start it, and open
   its web page.
3. If the page asks you to restart Home Assistant, select **Restart Home
   Assistant**.
4. Follow the setup checklist on the page. Each step gets a ✓ when it is done.
   1. **Prepare your Bluetooth proxy.** Choose your proxy and select **Add
      Skylight firmware**. The add-on copies the firmware files into your
      ESPHome folder and adds one line to the proxy's YAML. It keeps a backup.
      Then install it in ESPHome Device Builder: open the proxy, then **⋮ →
      Install → Wirelessly**. The page continues by itself when the proxy is
      back. A proxy that already has the firmware skips this step.
   2. **Connect Home Assistant to the proxy.** With one compatible proxy, the
      add-on does this by itself. With several, choose one.
   3. **Let Home Assistant hear your remote.** Select **Allow**. This turns on
      the proxy's setting **Allow the device to perform Home Assistant actions**.
   4. **Pair Home Assistant with the panel.** See [Pairing](#pairing). Then
      select **Switch the panel on or off**, and say what the panel did.
      Finally, choose a mode. The panel switches on in that mode, so Home
      Assistant knows its state.
5. Optional: create a Skylight dashboard, or add the Skylight card to one of
   your dashboards. You can also use the entities in your own cards.

If the add-on is not in the store yet, use the
[local installation](docs/PROTOCOL.md#development-installation).

Already using the Philips Skylight integration? The add-on keeps your light,
settings and pairing. You do not need to pair again.

## Pairing

The panel ignores Home Assistant until you pair it. Pairing is a one-time step.
Updates do not need it. Your other remotes stay paired.

1. Select **Start pairing**. Home Assistant repeats the pairing request for 90
   seconds.
2. Within those 90 seconds, switch the panel's power off at its light switch or
   breaker, then on again. The remote's power button does not work for this.
3. The panel blinks when it pairs.
4. Select **Done — the panel blinked**. If you do not, pairing ends by itself
   after 90 seconds.

The panel listens for pairing only for a moment after its power returns. Before
and after that moment, it ignores the request, so repeating it is harmless.

You can also pair from **Settings → Devices & services → Philips Skylight →
Configure → Pair this transmitter**, or with the `philips_skylight.pair_transmitter`
action.

To make the panel forget **every** remote, use **Configure → Unpair all
remotes**. It removes the original remote, any wall remote and Home Assistant.
It uses the same 90-second window. Afterward, pair each remote again with its
own steps, and pair Home Assistant again. No command removes only one remote.

Removing or reinstalling the add-on does not unpair the panel, because the panel
stores the pairing itself. That leftover pairing does no harm: nothing else
sends as Home Assistant's address.

## Everyday use

The Skylight card follows the remote's layout and icons.

| Control | What it does |
|---|---|
| **Skylight** (⏻) | Toggles the panel, like the remote's power button. It shows the recorded power and mode. |
| Mode buttons | Auto rhythm, Refresh, Energize, Focus, Relax and Rest. A mode button also switches the panel on. The recorded mode lights up in the remote's color. |
| **Dim down** / **Dim up** | A tap is one step. On a dashboard, holding a button dims for about 3 seconds. On the add-on page, holding keeps dimming until you let go, like the remote. |
| **Rhythm start** | Makes the current time the start of the Auto rhythm schedule. The panel blinks. Auto rhythm does nothing until a start is set. |
| **Correct state** | Opens a view to fix Home Assistant's guess. |

## Tell Home Assistant what you see

Do this any time the card does not match the panel.

1. On the card, select **Correct state**. On the add-on page, open **Settings
   and fixes → Correct the shown state**.
2. Select **Panel is on** or **Panel is off**.
3. Select the mode you can see, or **Mode unknown**.
4. On the card, select **Done**.

This changes only Home Assistant's record. It does not send anything to the
light. A mode press on your remote also updates the record by itself.

## Automations: use commands, not the guess

The safest automations send a command and do not depend on the recorded state:

- `light.toggle` toggles the power.
- `button.press` on a mode button selects that mode, and switches the panel on.
- `philips_skylight.dim` with `direction: down` or `up` dims by one step. Add
  `hold: 3` to dim like a 3-second hold on the remote.

`light.turn_on` and `light.turn_off` decide whether to toggle from the recorded
power. If the record is wrong, they do the wrong thing. `light.turn_on` with an
effect is the exception: it always sends that mode. Do not use the recorded
state as a trigger or a condition. Do not treat it as proof that the panel
changed.

## Troubleshooting

| Problem | What to try |
|---|---|
| The add-on is not in the store | Check that you can open the repository, and that an add-on release exists. Otherwise, use the local installation. |
| No proxy appears | The setup checklist lists the Bluetooth proxies in your ESPHome folder. If none is listed, set up a Bluetooth proxy in ESPHome Device Builder first. |
| Remote presses do not update the dashboard | Check step 3 of the setup checklist. Move the proxy closer to the panel. Then correct the state. |
| The dashboard shows Unknown, or the wrong power or mode | Use **Correct state** and record what you see. |
| The card download says that a control is missing | Turn the Skylight entities back on in **Settings → Devices & services**. |
| Commands do nothing | Check that the proxy is online. Then pair again. |
| Commands stopped after a Home Assistant rebuild or an older backup restore | On the add-on page, use **Settings and fixes → The panel ignores Home Assistant after a backup restore**. It fixes the command counter without pairing again. |
| An update asks for a restart | Restart Home Assistant from the add-on page. |

## Ideas for later

- During setup, offer to link a smart wall switch to the recorded state with an
  automation.
- Notice the power cycle during pairing by itself. The panel sends a Bluetooth
  beacon all the time, so the proxy can tell when its power goes off and comes
  back. Then nobody needs to select **Done**.
- Control several panels separately, with one Home Assistant sender address per
  panel.

## More detail

- [Add-on documentation](philips_skylight/DOCS.md): options, permissions,
  recovery and removal.
- [Dashboard guide](docs/DASHBOARD.md): the compact and full cards, and manual
  card setup.
- [Integration-only guide](docs/INTEGRATION.md): for installs without add-ons.
- [Protocol notes](docs/PROTOCOL.md): how the panel's Bluetooth Mesh commands
  work, and developer instructions.
- [Validation record](docs/VALIDATION.md): what was tested on real hardware.
