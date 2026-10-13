# Philips Skylight for Home Assistant

> [!WARNING]
> **Work in progress.** If you found this project by chance: I am still
> developing and testing it. You are welcome to try it. Expect parts that do not
> work fully yet, and expect bugs and errors.

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
  "turn on" does nothing, and "turn off" turns it on.
- **Every Skylight in range responds.** All panels of this model use the same
  factory keys. You cannot control two nearby panels separately.
- **Dimming is up or down by one step.** No brightness slider or color
  temperature control exists. Holding a dashboard dim button does not keep
  dimming. Only the physical remote does that.
- **It is tested on one setup.** One owner tested it with the NatureConnect/BioUp
  17.7 × 25.6 inch panel and an ESP32-C3 proxy. Other models are unknown.
- **The add-on needs Home Assistant OS or Supervised.** For Container or Core
  installs, use the [integration-only guide](docs/INTEGRATION.md).

If you want a dependable on/off status for automations, this project cannot
give you one. If you want a remote on your phone and in your dashboard, it
does that well.

## What you need

- Home Assistant OS or Supervised, version 2026.6 or newer.
- A Philips Skylight panel.
- An ESPHome Bluetooth proxy near the panel. The add-on gives you the firmware
  package to add to it. ESPHome 2026.4.5 or newer.

## Install

1. In Home Assistant, open **Settings → Apps → App store → Repositories**. On
   older versions, this menu is called **Add-ons**. Add
   `https://github.com/jphelan82/ha-philips-skylight`.
2. Install **Philips Skylight**. Turn on **Start on boot**, start it, and open
   its web page.
3. If the add-on asks you to restart Home Assistant, restart it.
4. Follow the steps on the add-on page:
   - **Prepare your proxy.** If the add-on finds no compatible proxy, download
     the ESPHome package and add one `packages` line to your proxy's YAML. Keep
     your Wi-Fi, API and board settings. The [package guide](esphome/README.md)
     has the details.
   - **Choose your proxy** and save. If you have one compatible proxy, the
     add-on selects it for you.
   - **Allow remote tracking.** In the proxy's ESPHome integration options,
     turn on **Allow the device to perform Home Assistant actions**. Without
     it, Home Assistant cannot hear your remote.
   - **Pair the transmitter** (first setup only). See [Pairing](#pairing).
   - **Record the starting state.** Look at the panel and tell Home Assistant
     whether it is on or off. See [Tell Home Assistant what you see](#tell-home-assistant-what-you-see).
5. Optional: create a Skylight dashboard, or add the Skylight card to one of
   your dashboards. You can also use the entities in your own cards.

If the add-on is not in the store yet, use the
[local installation](docs/PROTOCOL.md#development-installation).

Already using the Philips Skylight integration? The add-on keeps your light,
settings and pairing. You do not need to pair again.

## Pairing

The panel ignores a new transmitter until you pair it. Pairing is a one-time
step. Updates do not need it.

1. Open **Pair the transmitter on first setup** in the add-on.
2. Switch the panel's mains power off, then on again.
3. Tick the confirmation box and select **Send pairing request** straight away.
4. Wait about ten seconds. The panel blinks.
5. Check that the panel and your original remote both work.
6. Record the starting state again.

On the tested panel, the original remote kept working after pairing. Other
models are untested. If your remote stops working, pair it again with its own
instructions.

To make the panel forget **every** remote, open **Settings → Devices & services →
Philips Skylight → Configure** and choose **Unpair all remotes**. It removes the
original remote, any wall remote and Home Assistant. Afterward, pair each remote
again with its own steps, and pair Home Assistant again with **Pair this
transmitter** in the same dialog. No command removes only one remote.

Removing or reinstalling the add-on does not unpair the panel, because the panel
stores the pairing itself. That leftover pairing does no harm: nothing else
sends as Home Assistant's address.

## Everyday use

| Control | What it does |
|---|---|
| Power tile | Toggles the panel, like the remote's power button. |
| Mode buttons | Refresh, Energize, Focus, Relax, Rest or Auto rhythm. |
| Dim down / Dim up | One step darker or brighter per tap. |
| Correct recorded state | Opens a small panel to fix Home Assistant's guess. |

A blue mode icon shows the mode that Home Assistant thinks is active. The other
mode icons are gray.

## Tell Home Assistant what you see

Do this at first setup. Do it again after a restart, a power cut, pairing, or
any time the dashboard does not match the panel.

1. Look at the panel.
2. In the add-on, use **Record initial state**. On the dashboard card, use
   **Correct recorded state**.
3. Choose **Panel is on** or **Panel is off**.
4. For the mode, you have three choices:
   - Press a mode button on your remote. The mode updates within a few seconds.
   - Choose the mode yourself.
   - Leave it as **Unknown**.
5. Save. On the card, select **Done**.

Saving changes only Home Assistant's record. It does not send anything to the
light. "Unknown" power does not mean off. It means that Home Assistant needs you
to look.

## Automations: use commands, not the guess

The safest automations send a command and do not depend on the recorded state:

- `light.toggle` toggles the power.
- `button.press` on a mode button selects that mode.
- `button.press` on Dim down or Dim up changes the brightness by one step.

`light.turn_on` and `light.turn_off` decide whether to toggle from the recorded
power. If the record is wrong, they do the wrong thing. Do not use the recorded
state as a trigger or a condition. Do not treat it as proof that the panel
changed.

## Troubleshooting

| Problem | What to try |
|---|---|
| The add-on is not in the store | Check that you can open the repository, and that an add-on release exists. Otherwise, use the local installation. |
| No proxy appears | Install the ESPHome package on your proxy and wait for it to reconnect. |
| Remote presses do not update the dashboard | Turn on the proxy's permission to perform Home Assistant actions. Move the proxy closer to the panel. Then correct the recorded state. |
| The dashboard shows Unknown, or the wrong power or mode | Use **Correct recorded state** and record what you see. |
| The card download says that a control is missing | Turn the Skylight entities back on in **Settings → Devices & services**. |
| Commands do nothing | Check that the proxy is connected. Then pair the transmitter again. |
| Commands stopped after a Home Assistant rebuild or an older backup restore | In the add-on, use **Setup and recovery → Panel ignores commands after a rebuild or restore**. It fixes the transmitter's counter without pairing again. |
| An update asks for a restart | Restart Home Assistant from the add-on page. Then correct the recorded state. |

## More detail

- [Add-on documentation](philips_skylight/DOCS.md): options, permissions,
  recovery and removal.
- [Dashboard guide](docs/DASHBOARD.md): the compact and full cards, and manual
  card setup.
- [Integration-only guide](docs/INTEGRATION.md): for installs without add-ons.
- [Protocol notes](docs/PROTOCOL.md): how the panel's Bluetooth Mesh commands
  work, and developer instructions.
- [Validation record](docs/VALIDATION.md): what was tested on real hardware.
