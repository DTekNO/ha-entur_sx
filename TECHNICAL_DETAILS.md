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

## Database & Recorder Optimisation

The integration automatically excludes large attributes from recorder history to prevent database bloat.

**Line Sensors — excluded from recorder:**
- `formatted_content` — Markdown-formatted disruption content
- `entity_picture` — Base64-encoded badge SVG

**Summary Sensor — excluded from recorder:**
- `markdown_active` — Formatted active disruptions
- `markdown_planned` — Formatted planned disruptions

**Still recorded:**
- `state` — Current disruption count / status
- All essential attributes: `valid_from`, `valid_to`, `status`, `summary`, etc.

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
