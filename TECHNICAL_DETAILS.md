# Technical Details — Entur Situation Exchange

This document covers implementation details for developers or advanced users who want to understand how the integration handles API quota, error recovery, and database impact.

---

## Rate Limiting and Throttle Handling

### Entur API Rate Limits

The Entur SIRI-SX API enforces rate limits using **fixed 60-second windows**, per `ET-Client-Name`:
- **5 requests per 60-second window** — each installation gets its own independent quota
- Response headers report the current state: `rate-limit-available`, `rate-limit-allowed`, `rate-limit-expiry-time`
- The API also enforces spike arrest: minimum 100 ms between requests

The integration reads these headers on every response and tracks remaining quota locally, so it never needs to guess.

### Unique Client Identity

Each HA installation sends a unique `ET-Client-Name` header of the form `homeassistant-entur-sx-<8-char-uid>`, derived from HA's stable instance UUID (persisted across restarts). This gives every installation its own independent quota pool on the Entur API.

### Normal Operation

- Polls every **120 seconds** — exactly 2× the 60-second server window, so every request lands in its own fresh quota window
- Remaining quota is decremented locally after each request and corrected by the server on the next response
- A `WARNING` is logged if the server value differs from the local prediction (indicates something unexpected consumed quota)

### If Rate Limited (429 Error)

1. **Smart Back-off**: Automatically increases polling interval
   - First throttle: waits 2 minutes before retry
   - Repeated throttles: exponentially increases to max 10 minutes
   - Resets to normal (120 s) after 30 minutes of successful polling

2. **State Preservation**: Sensors **stay available** showing last known data
   - No "unavailable" state during cooldown period
   - Prevents unwanted automation triggers

3. **Automatic Recovery**: Resumes normal polling once the API accepts requests again

### Log Messages

```
WARNING: Rate limit hit (429 Too Many Requests) - throttle event #1. Applying 120 second back-off. Will retry after cooldown. Preserving last known state to keep sensors available.

INFO: API access recovered after throttling (back-off ended)

WARNING: [GLOBAL QUOTA] Server corrected quota: 4 → 2/5   ← unexpected quota consumption
```

---

## Line Sensor Attribute Structure

A line sensor exposes the same disruption data at two levels: a **flat copy of the
current disruption** at the top, and the **full list** in `all_deviations`. This
is deliberate (see below), but it is the most common source of confusion, so:

```
sensor.<device>_disruption_<line_ref>
│
├─ state ────── "Trafikkmelding"          ← summary of the current OPEN disruption
│
└─ attributes
   │
   ├─ ① THE CURRENT ONE ......... flat copy of all_deviations[0]
   │     valid_from   valid_to   summary   description   status   progress
   │     situation_number   publisher   publisher_name
   │     severity   report_type   created
   │
   ├─ ② THE FULL LIST
   │     all_deviations: [ ─────────────────────────── one entry per situation
   │       { ...the same 12 fields as ①...
   │         formatted_content }   ← THIS alert only, no description
   │       { ... }
   │     ]
   │
   ├─ ③ COUNTS
   │     total_deviations: 3
   │     deviations_by_status: {open: 2, expired: 1}   ← only present when >1
   │
   ├─ ④ ENTITY-LEVEL (not per-disruption)
   │     line_ref      SKY:Line:1033
   │     travel_tag    the badge SVG
   │     formatted_content   ← ALL alerts concatenated, badge + descriptions
   │
   └─ ⑤ HA STANDARD
         entity_picture   icon   friendly_name
```

### Which layer to use

| You are… | Use |
|---|---|
| showing a summary across all lines in a markdown card | the **summary sensor's** `markdown_active` / `markdown_planned` |
| rendering one line in a markdown card | ④ `formatted_content` |
| building a card that lists each disruption (e.g. ha-alert-card) | ② `all_deviations`, and each item's own `formatted_content` |
| writing a one-line template or automation condition | ① — e.g. `state_attr(e,'status') == 'open'` |
| plotting or querying history | ① only — ② is not recorded, see below |

### Why ① exists — it is not redundant

Both levels have been present since the first commit; ① is not legacy residue
left over from before `all_deviations` existed. Three things depend on it:

1. **History.** `all_deviations` is excluded from the recorder, ① is not. The
   flat fields are the only disruption data that accumulates in the database, so
   removing them would leave no history at all.
2. **Iterating over entities rather than disruptions.** A template that loops
   over line sensors and prints one line each reads `state_attr(line,
   'description')` directly. Via ② that becomes
   `state_attr(line,'all_deviations')[0].description`, which is both noisier and
   fragile when the list is empty. `CARD_EXAMPLES.md` uses the flat form.
3. **Published surface.** `status`, `valid_from`, `valid_to` and `description`
   appear in README and CARD_EXAMPLES examples, so user dashboards and
   automations depend on them.

### Ordering

`all_deviations` is sorted by status — `open`, then `planned`, then `expired` —
and by newest `valid_from` within each group. So `[0]`, and therefore ①, is the
most recent open disruption when one exists. An expired situation sorts last even
if it is the most informative.

### `state` is computed separately from ①

`state` takes the first `open` disruption that is **also inside its validity
window**, falling back to `STATE_NORMAL`. ① is simply `all_deviations[0]` with no
window check. They agree almost always, but a situation whose `progress` is still
`open` after its `valid_to` has passed will appear in ① and not in `state`.

### Two flavours of `formatted_content`

| | Where | Contains |
|---|---|---|
| entity-level | ④ | badge image + **every** alert, each with title, dates **and** description |
| per-alert | inside each ② item | **just that one** alert: title + dates, **no** description, no badge |

The per-alert form omits the description on purpose: ha-alert-card already shows
the summary in the collapsed row and the badge via `image_attribute: travel_tag`,
so repeating them in the expanded view is redundant. The templates take a
`per_item` flag to switch between the two.

---

## Database & Recorder Optimisation

The integration automatically excludes large attributes from recorder history to prevent database bloat.

**Line Sensors — excluded from recorder:**
- `formatted_content` — Markdown-formatted disruption content
- `all_deviations` — The full per-disruption list, which embeds HTML
- `entity_picture` — Base64-encoded badge SVG
- `travel_tag` — Base64-encoded TravelTag badge SVG

**Summary Sensor — excluded from recorder:**
- `markdown_active` — Formatted active disruptions
- `markdown_planned` — Formatted planned disruptions

**Still recorded:**
- `state` — Current disruption count / status
- The flat current-disruption attributes (① above): `valid_from`, `valid_to`, `status`, `summary`, `description`, `progress`, `situation_number`, `publisher`, `severity`, `report_type`, `created`
- `line_ref`, `total_deviations`, `deviations_by_status`

All excluded attributes remain fully available in real-time via `state_attr()`, dashboard cards, and automations — they just don't accumulate history in the database.

---

## Disruption Tracking Log

The integration maintains a separate logger (`custom_components.entur_sx.coordinator.disruptions`) that records when disruptions appear and disappear. This is useful for:

- Tracking patterns in what disruptions are published to the API
- Comparing with operator websites to identify missing disruptions
- Monitoring the reliability of the Entur data feed

### Enabling

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.entur_sx.coordinator.disruptions: info
```

Restart Home Assistant after making changes.

### Log output

```
INFO [custom_components.entur_sx.coordinator.disruptions] [2025-12-06 20:15:00] NEW disruption on SKY:Line:1 (status: open) - Det er forseinkingar på linja... - valid from: 2025-12-06T18:30:00+01:00

INFO [custom_components.entur_sx.coordinator.disruptions] [2025-12-06 21:45:00] REMOVED disruption from SKY:Line:1 (was: open) - Det er forseinkingar på linja...
```

> **Note**: On startup/reload all currently active disruptions are logged at DEBUG (not INFO) to avoid flooding the log with disruptions that were already known before the restart.

### Persistent log file (optional)

```yaml
logger:
  default: info
  logs:
    custom_components.entur_sx.coordinator.disruptions: info
  filters:
    custom_components.entur_sx.coordinator.disruptions:
      - "/config/entur_sx_disruptions.log"
```

Requires Home Assistant 2023.4 or later.

---

## API Details

- **Base URL**: `https://api.entur.io/realtime/v1/rest/sx`
- **Protocol**: SIRI-SX (Situation Exchange), JSON response
- **Auth**: None required (public API, rate-limited by `ET-Client-Name`)
- **Pagination**: Supported via `requestorId` + `MoreData` flag (used automatically during extreme-weather events with many situations)
- **Quota headers**: `rate-limit-allowed`, `rate-limit-available`, `rate-limit-used`, `rate-limit-expiry-time`, `rate-limit-range`
