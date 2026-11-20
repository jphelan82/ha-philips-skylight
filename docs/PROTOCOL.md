# Philips Skylight: Bluetooth Mesh protocol

This document contains protocol research, implementation notes and developer
instructions moved out of the README files. For installation and everyday use,
start with the [end-user README](../README.md).

The skylight is a Philips LED Skylight Ceiling Panel (NatureConnect, BioUp, 17.7 x 25.6 in). Philips sells it as remote-only: no app, no Hue, no Matter, no Wi-Fi. Inside, it runs standard Bluetooth Mesh, and its remote uses factory-default keys. This file records what we decoded on 2026-10-12 and 2026-10-13, so Home Assistant can send the same commands as the remote. It also records what another owner found on 2026-11-09: the panel reports its power when asked, and a Vita-Up panel has a UV command.

## The hardware

| Part | What we found |
|---|---|
| Panel radio | Bluetooth Low Energy (BLE) Mesh module, address prefix `4C:3C:8F`. That prefix belongs to Shenzhen Jingxun Technology. The panel advertises the name `BK_MESH_light`, which points to a Beken chip. |
| Panel beacon | The panel always sends the "unprovisioned device" beacon (service `0x1827`), even after pairing. Ignore it. The panel is on the default network from the start, and it relays the remote's packets. |
| Remote | A battery mesh node. The remote in this file sends from mesh address `0x7FFF` to `0xFFFF` (all nodes). Other remotes use other addresses: a Vita-Up remote sends from `0x54E5` ([issue 10](https://github.com/jphelan82/ha-philips-skylight/issues/10)). Its BLE address for the proxy advert is `AA:AA:AA:00:00:02`. The ESPHome proxy reports its command packets under `FF:FF:FF:FF:FF:FF`. |
| FCC ID | `2AGBW929004709X`, 2402 to 2480 MHz. |

## The keys

Both keys are factory defaults. Every unit of this model very likely uses the same pair.

| Key | Value | How we know |
|---|---|---|
| Network key (NetKey) | `11111111111111111111111111111111` | The remote's 64-bit network ID is `c7cd5342d1544cd5`. The mesh function k3 of this key gives exactly that ID. |
| Application key (AppKey) | `00000000000000000000000000000000` | Its 6-bit key ID matches (`0x38`), and it decrypts every captured command with a valid message check. |
| IV index | `0` | From the remote's secure network beacon. |

## The commands

Each command is a vendor message with company ID `0x0211` (Telink Semiconductor). The bytes below are the decrypted access payload. `TT` is a transaction number. The remote counts it up by one per press, from `0x80` to `0xFF`, and then wraps back to `0x80`.

| Button | Payload | Notes |
|---|---|---|
| On/off | `C8 11 02 TT 03 01 41` | A toggle. We have not found separate on and off codes yet. |
| Dim down, tap | `C8 11 02 TT 01 00 14 41` | `0x14` is 20, likely a 20 percent step. |
| Dim up, tap | `C8 11 02 TT 01 01 14 41` | |
| Dim down, hold | `C8 11 02 TT 01 02 14 41` | The remote repeats it about every 0.6 s while held. |
| Dim up, hold | `C8 11 02 TT 01 03 14 41` | Same repeat as dim down. |
| Refresh | `C9 11 02 TT 04 FF 01 41` | `C9` is the scene command. |
| Energize | `C9 11 02 TT 04 FF 02 41` | |
| Focus | `C9 11 02 TT 04 FF 03 41` | |
| Relax | `C9 11 02 TT 04 FF 04 41` | |
| Rest | `C9 11 02 TT 04 FF 05 41` | |
| Auto rhythm | `C9 11 02 TT 04 FF 06 41` | |
| Set auto rhythm start (hold Auto rhythm and Relax together) | `E0 11 02 TT 00` | Opcode `E0` with one parameter byte. The remote sent it three times in about a second, each with a new `TT`, and the panel relayed each one. The panel blinks. The manual says this sets the current time as the start of the Auto rhythm schedule. One command from `0x7FFE` is enough. Captured and tested 2026-10-13. |
| Vita-Up UV-B on/off | `E0 11 02 TT 01` | A toggle on the Vita-Up remote. It uses the same opcode `E0` as the rhythm start. Only the last byte differs. Two owners captured it. See [Vita-Up UV](#vita-up-uv). |
| Pair (hold on/off 10 s after power-on) | `CF 11 02 TT 01 11 11 11 11 11 11` | The remote repeats it about twice a second, with a new `TT` each time, for the whole hold. Six `11` parameter bytes follow `01`. The complete access payload is 11 bytes. Home Assistant sends it the same way: twice a second for 10 seconds, 20 requests. A capture on 2026-10-12 showed the remote's hold at about two requests a second. |
| Unpair all (no remote gesture known) | `CF 11 02 TT 02 11 11 11 11 11 11` | The pairing request with `02` in place of `01`. Inside the pairing window, it makes the panel blink and forget every paired sender. Outside the window, it switches the panel off and changes no pairing. Tested 2026-10-13. |
| Nothing found | `CF 11 02 TT 00 11 11 11 11 11 11` | No visible effect and no change to pairing, both right after power-on and at other times. Tested 2026-10-13. |

Every `C8` and `C9` command ends in `0x41`. It is very likely a Bluetooth Mesh
transition time: one step of 1 second. The panel's own status reply used the
same `0x41` for a 1-second fade on 2026-11-09. See
[Generic OnOff Set](#generic-onoff-set).

Auto rhythm (`C9 … 06`) is a mode: it makes the panel follow its daily
schedule. It does nothing until a schedule start is set. Any other mode button
takes the panel off the schedule until Auto rhythm is pressed again.

A mode command (`C9`) also turns an off panel on, in that mode. On 2026-10-13,
with the panel off, one Relax command from `0x7FFE` turned it on in Relax. The
other five modes were not tested from off.

## Power status

The panel answers a standard Bluetooth Mesh Generic OnOff Get. This is the one
way that Home Assistant can read the panel. roy1uno found it and reported it in
[pull request 9](https://github.com/jphelan82/ha-philips-skylight/pull/9) on
2026-11-09.

| Message | Payload | Sender to destination |
|---|---|---|
| Generic OnOff Get | `82 01` | Home Assistant `0x7FFE` to `0xFFFF` (all nodes) |
| Generic OnOff Status, off | `82 04 00` | The panel's own unicast address to `0x7FFE` |
| Generic OnOff Status, on | `82 04 01` | The panel's own unicast address to `0x7FFE` |

- Both messages are standard Mesh messages, not Telink vendor messages. The Get
  has no `TT` byte. The same factory keys encrypt both.
- The panel sends the status to the address that asked. So the integration
  hears it only because the proxy hears the panel.
- Each panel answers from its own mesh address, and the address differs
  between panels. roy1uno's panel answered from `0x3CC2`. The panel in this
  file answered from `0x1676`. So the integration accepts a status from any
  unicast address (`0x0001` through `0x7FFF`) except its own.
- The Mesh standard also has a long status form: present power, target power
  and remaining transition time (5 bytes). The panel sends it in reply to a
  Generic OnOff Set. The integration uses the present power, because the
  panel can name a target that it never reaches. See
  [Generic OnOff Set](#generic-onoff-set).
- The status has no request number. A status that arrives late cannot be
  matched to its Get with certainty. So the integration counts a status only
  inside a 3-second window after its Get, and only if no toggle or mode
  command went out after the Get.
- If the panel has no mains power, it cannot answer. Silence does not mean off.
- The panel misses some questions, even with mains power. On 2026-11-09 the
  panel in this file answered 8 of 11 questions. The cause is unknown. One
  guess: the proxy is still sending the Get, three times over about 300 ms,
  when the panel answers, so the proxy does not hear the answer. So the
  integration asks a second time if the first Get gets no answer. It also
  logs a status that arrives after the 3-second wait, to learn whether the
  missed answers are lost or only late.
- Each Get uses one sequence number from the sender's 24-bit counter, which
  holds about 16.7 million. A Get every 30 seconds uses about 1 million a year.
  A Get once a minute, with retries, uses about 657,000 a year, so the
  counter lasts about 25 years. The owner chose once a minute on 2026-11-09.
  By then this transmitter had used 5,120 numbers.

roy1uno tested the exchange on their own panel on 2026-11-09, with an
ESP32-S3 proxy (Heltec WiFi LoRa 32 V3) and ESPHome 2026.10.2. A Get
corrected a deliberately wrong record in both directions: off to on, and on to
off. A Get 5 seconds after a toggle also worked.

The panel in this file passed nine tests on 2026-11-09, with the ESP32-C3
proxy. They cover a refresh, a wrong record in both directions, Home Assistant
and remote toggles, fast toggles, the regular check, a proxy outage, a
restart, and the modes and dimming. A mains power cut was not tested. The
[validation record](VALIDATION.md#power-status-branch-power-status) has the
details.

### Generic OnOff Set

A standard Generic OnOff Server also accepts Generic OnOff Set (`82 02`, with
an answer) and Set Unacknowledged (`82 03`, no answer). Each one carries the
wanted power (`00` or `01`) and a transaction byte. On 2026-11-09 the panel in
this file was on, and Home Assistant sent it "off" five ways. The owner
watched the panel. It did not change for any of them:

| Sent | Destination | Panel's reply |
|---|---|---|
| `82 03 00 TT`, no answer asked | `0xFFFF` | none |
| `82 02 00 TT` | `0xFFFF`, twice | `82 04 01 00 41` |
| `82 02 00 TT 00 00`, transition and delay 0 | `0xFFFF` | `82 04 01 00 41` |
| `82 02 00 TT` | `0x1676`, the panel | `82 04 01 00 41` |
| `82 02 00 TT` | `0x1677` | none |

The reply `82 04 01 00 41` means: present power on, target power off, 1 second
left. It ignores the transition time of 0 that Home Assistant asked for. A Get
12 seconds later still answered `82 04 01`, on. So the panel's standard on/off
server accepts the Set and reports the light, but the light does not follow
it. The panel has no second element at `0x1677`. Home Assistant keeps the
captured toggle for power, and it toggles only when the reported power differs
from the wanted power. The test code was not kept.

Another owner got a different result outside the factory mesh. Before using
this project, that owner provisioned a Vita-Up panel into a mesh of their own,
with their own keys and bound models. There, a Generic OnOff Set from `0x7FFF`
switched the panel on. The test in this file used the factory keys and asked
for off. Nobody knows which difference matters: the keys, the bound models, or
on against off. In the same mesh, the l-carta/skylight-remote format of the
mode and dim commands did nothing. That format has `00` where this file has
`FF` (mode) or `14` (dim step), no closing `0x41`, and `TT` below `0x80`. Reported
in [issue 5](https://github.com/jphelan82/ha-philips-skylight/issues/5) on
2026-10-29.

### Other standard lighting messages

Later on 2026-11-09, a temporary probe sent the panel every standard Get in
the table below, to `0xFFFF`. The panel answered from `0x1676`. Values are
little-endian. A question without an answer was asked at least twice, so it is
very likely unsupported.

| Get | Opcode | Reply, panel on at full brightness | Meaning |
|---|---|---|---|
| Generic OnOff | `82 01` | `82 04 01` | on |
| Generic Level | `82 05` | `82 08 00 00 00 00 01` | level 0, never changes |
| Generic OnPowerUp | `82 11` | `82 12 00` | "stay off", although the panel turns on when power returns |
| Time | `82 37` | `5d 00 00 00 00 00` | clock not set |
| Scene | `82 41` | `5e 00 00 00` | current scene 0, none |
| Light Lightness | `82 4b` | `82 4e ff ff` | 65535, a counter of dim commands, not the real brightness |
| Light Lightness Linear | `82 4f` | `82 52 00 00` | 0, never changes |
| Light Lightness Last | `82 53` | `82 54 ff ff` | follows the counter |
| Light Lightness Default | `82 55` | `82 56 00 00` | 0 |
| Light Lightness Range | `82 57` | `82 58 00 00 00 00 00` | 0 to 0 |
| Light CTL | `82 5d` | `82 60 ff ff a0 28` | brightness 65535, 10,400 K |
| Light CTL Temperature | `82 61` | `82 66 a0 28 00 00 a0 28 00 00 01` | 10,400 K |
| Light CTL Temperature Range | `82 62` | `82 63 00 00 00 00 00` | 0 to 0 |
| Light CTL Default | `82 67` | `82 68 00 00 00 00 00 00` | 0 |
| Light HSL | `82 6d` | `82 78 cc cc 00 00 00 00` | lightness 52428, hue 0, saturation 0 |

No answer came to Generic Default Transition Time (`82 0d`), Generic Power
Level (`82 15`), Scene Register (`82 44`), Scheduler (`82 48`), Light xyL
(`82 83`) or Light LC Mode (`82 91`).

**The mode cannot be read.** The probe selected each of the six modes, waited
3 seconds, and asked again. Every value stayed the same in all six modes. The
color temperature read 10,400 K even in Relax and Rest, which are clearly
warmer. With the panel off, Light Lightness and the CTL brightness read 0.

**No vendor message reports the mode either.** On 2026-11-16, a temporary
probe logged every message from any sender other than Home Assistant and the
remote. It found these facts:

- The panel sends nothing by itself. In 4 minutes, the only messages were its
  answers to the power check once a minute.
- The panel does not answer a mode command. After a Focus command (`C9`) from
  Home Assistant, it sent nothing.
- No bare vendor opcode gets an answer. The probe sent 52 opcodes, each as
  `XX 11 02 TT` with no more bytes: `CA` to `CE`, `D0` to `DF` and `E1` to
  `FF`. It waited 2 seconds after each one. None got an answer.
- Untried sub-commands of the known commands get no answer. The probe sent
  `C8 11 02 TT` and `C9 11 02 TT` alone, `C8 11 02 TT` with `00`, `02`, `04` or
  `05`, `C9 11 02 TT` with `00`, `01`, `02`, `03` or `05`, and
  `E0 11 02 TT 02`. It waited 4 seconds after each one. None got an answer.
  Nobody recorded a visible effect. The panel stayed on.

The probe never sent `C0` to `C7`, because Telink's own firmware keeps that
range for functions such as a network reset. It never sent `CF` (pairing) or
the UV command either. The test code was not kept.

**Light Lightness is a counter, not the real brightness.** The value moves
with the remote's dim commands, but it knows nothing about the light. Measured
on 2026-11-09:

- It counts in whole percent from 1 to 100. A dim command with step byte N,
  the byte after the direction (`0x14` from the remote), moves it by exactly
  N − 1 points. So the remote's taps move it 19 points each: 100, 81, 62, 43,
  24, 5, then 1. Steps of 2, 3, 5, 8, 10, 49, 50, 60 and 100 all followed the
  same rule.
- Power off sets it to 0. A mode command does not change it. With the panel
  off, then on in each of the six modes, it read 0 the whole time.
- So after a mode command, the value and the light disagree. At a reported
  25 %, Relax and then Energize left the value at 25 %, and the owner saw the
  panel at full brightness.

**The light follows only the remote's own step.** The owner watched while
Home Assistant sent dim commands. Three taps with `0x14` dimmed the light three
times. A tap with `0x0A` did nothing visible. Step `0x64` down made the light
slightly brighter, and step `0x32` up then did nothing visible. So the step
byte changes the counter, but the light uses its own fixed steps.

**Light Lightness Set does not change the light.** In Auto rhythm, a Set to
50 % (`82 4c 00 80 TT`) and then 100 % changed the reported value, but the
owner saw no change. In Energize, a Set to 20 % (`82 4c 33 33 TT`) made the
panel report exactly 20 %, and the light stayed at full brightness. A Set to
100 % then put the reported value back.

**Two calibration runs with a light sensor.** An Aqara FP300 presence sensor
in the same room measured the light in the dark, 45 seconds after each
command, first with its light sampling on Low and then on High. Both runs gave
the same readings:

| Command | Office reading |
|---|---|
| Panel off | 0 to 1 lux |
| Energize, Focus | 8 lux |
| Relax, Rest, Auto rhythm | 2 lux |
| From Energize at full: `0x14` taps down until the reading dropped | 3 taps, to 2 lux |
| From the bottom after 8 taps down: `0x14` taps up until it rose | 8 taps, to 8 lux |
| One tap down with `0x14`, `0x0A`, `0x28` or `0x02`, from Energize at full | no change seen |

The sensor reported only those two levels in the dark, so it did not show the
light's separate steps. The light has more than the counter's five steps between
full and the bottom: three taps crossed the boundary going down, and eight
taps were needed to cross it again going up. Each mode also has its own
brightness, and a mode command resets the light to it.

**A brightness slider is parked.** Without a value that matches the light,
Home Assistant can only count the remote's taps blind. Nobody knows how many
steps the light has, and every mode command resets it. The dim buttons stay as
they are.

## Vita-Up UV

The Vita-Up model is a different model from the BioUp panel in this file. It
adds a UV-B (ultraviolet B) light, and its remote has a UV control. The BioUp
remote has no UV control. The BioUp model does not support the UV command. See
the test result at the end of this section.

The UV command is `E0 11 02 TT 01`, a toggle. On and off send the same
bytes. Two owners captured it from a Skylight Daylight Lamp Vita-Up Large
(`929004709601`):

- roy1uno, the author of
  [pull request 9](https://github.com/jphelan82/ha-philips-skylight/pull/9),
  on 2026-11-09. The owner pressed only the UV button, many times.
- The owner who wrote
  [issue 10](https://github.com/jphelan82/ha-philips-skylight/issues/10), on
  2026-11-19. That owner pressed Relax once, then the UV button four times:
  on, off, on, off. The transaction bytes ran `EE`, `EF`, `F0`, `F1`. The remote
  sent from `0x54E5`. The UV stayed on when the owner selected another mode.

Since integration 0.7.0, a **Toggle Vita Up** button sends this command. Nobody
has tested the button on a panel. The button starts disabled, because only
Vita-Up panels have the UV light. It is not on the Skylight card. A remote
press of the UV button shows as `toggle_vita_up` in `last_command`, and changes
no recorded power or mode.

The panel does not report the UV state, so Home Assistant cannot show it.
Untested on a Vita-Up panel:

- Does the panel accept the command from `0x7FFE`?
- Does power off, or the panel's 8-hour auto-off, also switch the UV off?
- Does the panel switch the UV off by itself after a set time?

**The BioUp model does not support the UV command.** On 2026-11-20, Home
Assistant, with integration 0.7.0, sent one Toggle Vita Up from `0x7FFE` to the
BioUp panel in this file. The panel was on in Auto rhythm. The owner watched
it, and nothing changed. The panel sends no reply, so nobody knows whether it
received the command or ignored it. Its other controls still worked: a Relax
command 30 seconds later switched the panel to Relax.

## Pairing

- The panel ignores every sender that is not paired. `0x7FFE` did nothing
  until it sent the pairing request. On 2026-10-13, after an unpair all, the
  remote also did nothing until it paired again.
- Unpair all removes Home Assistant too, and does not pair it again. On
  2026-10-15, right after an unpair-all burst from Home Assistant, the panel
  ignored a Home Assistant toggle and the wall remote.
- After its mains power returns, the panel can take up to about 30 seconds to
  light up again. It accepts `CF … 01` and `CF … 02` only for a short time after
  that. A burst sent several seconds after the owner reported "back on" still
  worked. How long the window stays open was not measured.
- Send the pairing request as a short burst, like the remote's 10-second hold.
  A long stream makes the panel drop the other remote. See
  [Paired senders](#paired-senders).

## Rules for sending from Home Assistant

- **Never send as the remote's address `0x7FFF`.**
  A mesh node drops any packet whose sequence number is not higher than the last one from the same sender. If Home Assistant sends as `0x7FFF` with a high sequence number, the panel ignores the real remote until the remote catches up. Use a separate unicast address, such as `0x7FFE`, and keep its own sequence counter.
- **Store the sequence counter.** It must only go up, across restarts.
- **Ask for the power, not the mode.** The panel reports its power when it gets a Generic OnOff Get. See [Power status](#power-status). Nobody knows how to read the mode. Home Assistant tracks the mode from its own commands and from the remote's presses, which it can decrypt.
- **Keep the Get rare.** Each Get uses a sequence number, and the counter never goes back. The integration asks after setup, 5 seconds after a toggle, after a proxy outage, after a pairing burst, and once a minute.

## Tracking external controls

The integration accepts recognized, authenticated access commands addressed to
`0xFFFF` from external unicast senders (`0x0001` through `0x7FFF`). It excludes
its own `0x7FFE` sender even when those packets return through a panel relay.
A power toggle flips a known power state. A scene command records the mode and
records power as on. A dim tap or hold, the rhythm start and the Vita-Up UV
toggle (both `E0`) update only
the last command. A toggle or dim command leaves unknown power unknown. A
remote toggle makes Home Assistant ask the panel for its power 5 seconds later.
No other receive event sends a command.

A Generic OnOff Status addressed to `0x7FFE` is not a remote command. The
integration handles it apart from the commands above. See
[Power status](#power-status).

Duplicate identities use sender and Mesh sequence; rapid repeats with new Mesh
sequences use sender and complete access payload, including transaction byte.
Interleaved remotes and buttons do not reset each other's filtering. Repeated
dim holds at the captured 0.6-second cadence remain accepted.

Factory keys authenticate the protocol, but do not prove that a remote is paired
to this particular panel. Other compatible remotes within radio range can also
change the assumed state. Software tests cover other sender addresses. On the
panel, Home Assistant tracked the owner's one remote (`0x7FFF`). Another
owner's remote sends from `0x54E5`, and that owner's Home Assistant tracked it.

## Open questions

- Do other panels pair the same way? We tested only this panel. Do not replace the factory network or send as `0x7FFF`.
- Can one sender be removed alone? `CF … 02` removes every sender, and `CF … 00` does nothing. Other values, and a remote gesture for unpairing, are untested.
- How long does the pairing window stay open after the panel lights up again?
- Is two the real limit of paired senders, and what happens with a third? Two senders work together. The owner reports a limit of two. A third was never tested.
- Why does a long stream of pairing requests drop the other remote? A short burst does not. One guess: each accepted request counts as a new pairing in one of only two places.
- Do the other five modes turn an off panel on, as Relax does? Untested.
- Do separate on and off codes exist? The standard Generic OnOff Set does not switch the light. See [Generic OnOff Set](#generic-onoff-set). Vendor candidates are untested: `C8 11 02 TT 03 00 41` and `C8 11 02 TT 03 02 41`.
- Does every panel answer the Generic OnOff Get? Two panels have answered so far, from `0x3CC2` and `0x1676`.
- Why does the panel miss about one Get in four? See [Power status](#power-status).
- Why does the check right after a Core restart miss more often? It missed both questions once on 2026-11-09, while the proxy connection was new. The once-a-minute check fixed the power a minute later.
- Can any message read the mode? No standard Get and no vendor message tried so far reports it. Untried: vendor opcodes `C0` to `C7`, which can hold a network reset, and longer payloads. See [Other standard lighting messages](#other-standard-lighting-messages).
- How does a Vita-Up panel report its UV state, and what limits does it put on UV? See [Vita-Up UV](#vita-up-uv).
- How many dim steps does the light have between full and its lowest level, and are they equal? The light follows only the remote's `0x14` step, and each mode resets the brightness. Light Lightness cannot answer this, because it only counts commands. See [Other standard lighting messages](#other-standard-lighting-messages).

## Paired senders

The owner's setup has one remote (`0x7FFF`), mounted on the wall and usable in
the hand. Together with Home Assistant (`0x7FFE`), that makes two paired
senders, and both work together. The owner reports that the panel accepts at
most two.

The way Home Assistant pairs matters. Each test started from a clean unpair all.
A row without a date is from 2026-10-13:

| Order | Home Assistant's request | Result |
|---|---|---|
| Remote, then Home Assistant | A stream, 3 a second, for up to 90 seconds | The remote stopped working. Seen three times. |
| Remote, then Home Assistant | One burst of 30 over 10 seconds | Both work. |
| Remote, then Home Assistant (2026-10-15) | One burst of 30 over 10 seconds | The remote stopped working. Pairing the remote again, alone, brought it back, and Home Assistant kept working. |
| Remote, then Home Assistant (2026-10-15, integration 0.3.3) | One burst of 20 over 10 seconds, 2 a second | The remote stopped working. |
| Home Assistant, then remote (2026-10-15) | Either burst | Both work. Seen twice, each time by pairing the remote again after Home Assistant. |

The remote's own pairing hold is also a 10-second burst, at about two requests
a second. On 2026-10-12, Home Assistant paired with a 10-second burst too, and
the remote kept working. Since integration 0.3.3, Home Assistant sends two a
second as well.

The 2026-10-15 result fits one explanation: the panel keeps its two newest
pairings, and Home Assistant's burst sometimes counts twice. Then Home Assistant
holds both places, and the remote is pushed out. Pairing the remote again pushes
out one of Home Assistant's two, and both work. This is not proven.

Since add-on 0.4.23 and integration 0.3.4, setup pairs Home Assistant first and
the remote second. Nobody knows why "remote, then Home Assistant" worked on
2026-10-13 but not on 2026-10-15. One difference: the proxy was rebuilt on
2026-10-15 with a newer ESPHome Device Builder and Skylight firmware 2. Nobody
has measured whether that changes how many times each request goes out.

On 2026-10-16, the remote's pairing packets from the 2026-10-12 capture were
compared field by field with the packet that the integration builds. They
match in everything except the sender address: destination `0xFFFF`, TTL 5,
31-byte adverts, the same keys, and the same command bytes. Both raise the
sequence number and `TT` by one per request. The remote's hold sent 32 requests
in 15.4 seconds. So the packet is not the cause of the dropped remote. Two
differences remain untested: the sender address, and the number of radio
copies of each request.

The panel relays packets with TTL 4, from paired and unpaired senders alike. On
2026-10-13 it relayed the remote's toggles after the remote had been dropped,
but it did not act on them. A relay shows only that the panel heard a packet.
It does not show that the panel accepted it.

## Capture setup

The proxy, an ESP32-C3, did the capture. At ESPHome's default scan settings it listens 30 ms of every 320 ms, and it missed most single presses. On 2026-10-12 its config got `esp32_ble_tracker` scan interval and window of 1100 ms each. After that it caught every press. It dropped off Wi-Fi once, for about 18 seconds, right after the change. It stayed up for the rest of the session. Separately, the proxy's connection to Home Assistant broke about every five minutes, day and night. The cause is ESPHome's Wi-Fi roaming, not the scan window. Every five minutes, ESPHome scanned for a stronger access point and switched to it. On 2026-10-13 the proxy logged a roam to a stronger access point at 11:07:22. Home Assistant's connection then stayed dead for 45 seconds before it noticed, and a command sent in that time was lost. The package now sets `wifi: post_connect_roaming: false`. The backup of the old config is `/config/esphome/<proxy>.yaml.bak-20261012` on the server.

Home Assistant's `bluetooth/subscribe_advertisements` feed does not help. It sends a device only when the device first appears or disappears, not on each advert. The 2026-10-12 capture polled the Bluetooth diagnostics instead, about twice a second. From 2026-10-13, `tools/capture.py` reads the proxy's own log of raw adverts instead. That catches every advert the proxy hears.

The proxy does not hear its own transmissions. The panel's relay shows that it heard a Home Assistant command, not that it acted on it. The relay is the same packet from `AA:AA:AA:00:00:01` with TTL 4.

## Files

- `tools/meshdec.py` decrypts a capture log. Run `uv run --with cryptography python meshdec.py 11111111111111111111111111111111 capture-2026-10-12.log`.
- `tools/capture-2026-10-12.log` holds the raw mesh adverts from the session, with the panel's constant beacon removed.
- `tools/capture.py` connects to the proxy's ESPHome API as a second client, reads its `recv raw` log lines and prints each decoded mesh command. It only listens. Run `.venv/bin/python tools/capture.py . 192.0.2.10 240` for a four-minute capture. It needs `aioesphomeapi`. If the proxy's API has an encryption key, put the key in the `ESPHOME_API_KEY` environment variable first. Run only one copy at a time. Each copy streams every advert over Wi-Fi. On 2026-10-13, three copies at once overloaded the proxy, and a Home Assistant toggle was lost.
- `tools/capture-2026-10-13-rhythm.log` holds the decoded commands from the Auto rhythm session: Auto rhythm alone, the Auto rhythm and Relax combination (`E0`), then single mode presses.

## Implementation and packaging

The Home Assistant add-on installs and manages the bundled native integration.
The integration owns command encoding, authenticated reception and the durable
Mesh sequence counter. The add-on uses Home Assistant's native API and does not
create another transmitter or counter. Its Supervisor ingress panel handles
setup, firmware downloads and explicit pairing. The dashboard uses standard
Home Assistant cards and native light, button, select and switch entities.

The light supports the six captured effects and relative dim commands. A
**Set auto rhythm start** button sends `E0`. **Configure** on the integration
offers pairing and unpair all, and so do the `pair_transmitter` and
`unpair_all_remotes` actions. Separate
on/off BLE commands remain unverified: HA's normal on/off actions decide whether
to send the captured toggle using synchronized power. Same-state requests do
nothing. Uncertain toggle requests are never automatically retried. If the
power is unknown, an on or off action asks the panel first. The
`refresh_power` action asks the panel on demand. The panel reports power only.
The mode stays assumed, and an exact dim increment remains unmeasured.

Existing integration users retain their entity IDs, config entry, pairing and
sequence Store. A long proxy outage clears the recorded power and mode. Home
Assistant then asks the panel for its power, after a restart too.
State-correction entities change only the recorded power and mode. The view
switch changes only the dashboard mode. Neither path transmits a BLE command.

Retain the sequence Store across removal or reinstallation. Never reset it,
restore an older counter, or run another sender using `0x7FFE`. Commands go to every
panel in range, but only panels paired with `0x7FFE` obey them. Only one
integration entry is supported. Separate control of several panels needs one
sender address per panel, each paired with its own panel. That needs panels on separate circuits,
because one power cycle opens the pairing window of every panel on it. Permissions, code backup/rollback and removal procedures are in
the [add-on documentation](../philips_skylight/DOCS.md).

Physically verified on this panel: power toggle, the Rest, Energize and Relax
modes, a mode turning an off panel on, relative dimming, Set auto rhythm
start, unpair all, pairing again, and the remote and Home Assistant paired together. Keep that evidence separate
from broader software coverage; see the [validation record](VALIDATION.md).

The firmware adapts
[NicoIIT's MIT-licensed BLE advertising component](https://github.com/NicoIIT/esphome-ble_adv_proxy),
retaining its license and attribution. It uses non-connectable Mesh advertisements,
GAP completion callbacks and a 20 ms advertising interval. Its upstream commit
and local transport changes are recorded in the
[component notes](../esphome/components/ble_adv_proxy/README.md).

## Development installation

Supervisor repository installation needs an accessible repository with the
add-on release on its default branch. Before publishing a release, copy the
`philips_skylight` folder from this checkout to Home Assistant's `/addons`
directory, reload the app store, and install **Philips Skylight** from
**Local apps/add-ons**. The add-on currently uses Supervisor source builds.

To publish prebuilt images, push a tag that matches the `config.yaml` version,
for example `v0.2.5`. The `Publish add-on images` workflow then pushes
`ghcr.io/jphelan82/{amd64,aarch64}-philips-skylight` to the GitHub container
registry. The workflow stops if the tag and the version differ. Supervisor
keeps building from source until `config.yaml` gets this line:

```yaml
image: "ghcr.io/jphelan82/{arch}-philips-skylight"
```

Add that line only after the first images exist and the people who install the
add-on can read the package.

The native integration can also be installed independently through manual
installation or HACS; see the [integration-only guide](INTEGRATION.md).

## Source layout and developer checks

The native integration in `custom_components/philips_skylight` and the firmware
in `esphome` are canonical. `tools/dashboard_card.py` generates the standard
dashboard card. Run `python tools/sync_addon.py` to generate the card and bundle
the integration and firmware into the add-on's self-contained build context.
Its `--check` option verifies parity without modifying files.

The integration's `const.EFFECTS` lists the six modes once. The card generator
reads it directly. The add-on keeps its own copy, and the real-platform test
fails if that copy, or any add-on unique ID, differs from the integration.

Use Python 3.14 for the complete Home Assistant suite:

```sh
python -m pip install homeassistant==2026.6.0 pytest pytest-asyncio pytest-aiohttp ruff
python tools/sync_addon.py --check
python -m pytest -q
ruff check .
```

The Home Assistant dependency supplies PyYAML for card generation; it is also
declared in the project's development test extras. The add-on runtime does not
need PyYAML. Add-on-only tests can run on Python 3.12 with `pytest addon_tests`
when their HTTP/test dependencies are installed.

CI checks generated card and bundle consistency, tests the software on Linux,
and builds amd64/aarch64 containers. It also runs Home Assistant's `hassfest`
check, the HACS (Home Assistant Community Store) validator, and the add-on
linter. If the firmware changes, CI compiles it for an ESP32-C3 with ESPHome
2026.4.5, using the placeholder node in `.github/esphome/ci-node.yaml`. Tests
cover real remote capture authentication,
sequence reservations, native HA entities and reconfiguration, state-only
correction, safe dashboard action targets, installer rollback, ingress/session
access and native API reconnects. The macOS Python 3.14 interpreter-finalization
caveat and physical acceptance results are in the [validation notes](VALIDATION.md).
