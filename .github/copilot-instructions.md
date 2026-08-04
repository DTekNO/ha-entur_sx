# GitHub Copilot Instructions for Entur SX Integration

## Project Overview

This is a Home Assistant custom integration that monitors real-time transit disruptions from Entur's SIRI-SX API for Norwegian public transport operators.

## Core Architecture

### Components
- **API Client** (`api.py`): Handles communication with Entur SIRI-SX REST API
- **Coordinator** (`coordinator.py`): Manages data updates and disruption tracking
- **Sensors** (`sensor.py`): Two types of sensors:
  - **Line Sensors**: One per monitored line with TravelTag badges
  - **Summary Sensor**: Aggregates all lines with numeric disruption count
- **Config Flow** (`config_flow.py`): UI-based configuration with operator/line discovery
- **Badge Generation** (`sensor.py`): SVG badge creation with Entur Design System styling

### Key Files
- `icon_constants.py`: Transport mode icons (12 modes) and brand colors from Entur Design System
- `templates/formatted_content.j2`: English markdown template with badges
- `templates/formatted_content_no.j2`: Norwegian markdown template with badges
- `const.py`: Constants including `normalize_language()` function

## Coding Conventions

### Language Support
- Always use `normalize_language(hass.config.language)` for automatic language detection
- Language codes: `"no"` (Norwegian: nb, nn, se) or `"en"` (English, default)
- Templates exist for both languages - select using `_async_load_template(hass, lang)`
- Date formatting uses locale-aware functions: `_format_datetime_norwegian()` for Norwegian

### Badge Generation
- Uses `_create_badge_svg(transport_mode, line_name)` to create TravelTag-style badges
- Proportional scaling: base font 14pt, icon 26.25px (1.875×), badge height 31.5px (2.25×)
- Transport modes: bus, train, tram, ferry, carferry, metro, mobility, bicycle, walk, plane, helicopter, taxi
- Colors from `TRANSPORT_COLORS` in `icon_constants.py` (official Entur brand colors)
- Icons from `TRANSPORT_ICONS` as base64-encoded white SVGs

### Attribute structure — read this before changing attributes

Line sensors expose each disruption **twice**: a flat copy of the current one at
the top level, plus the full list in `all_deviations`. Diagram and rationale under
"Line Sensor Attribute Structure" in [TECHNICAL_DETAILS.md](../TECHNICAL_DETAILS.md).

The flat block is **not** redundant — do not "tidy it away". `all_deviations` is
excluded from the recorder, so the flat fields are the only disruption data that
reaches history; templates that iterate over line *entities* read them directly;
and `status`, `valid_from`, `valid_to` and `description` are used in README and
CARD_EXAMPLES, so user dashboards depend on them.

Any new per-disruption field must be added in **both** places — the flat block
and the `all_deviations` items — or it will be missing from whichever the
consumer happens to use.

### Sensor Design
- **Line sensors**: `entity_picture` shows badge, `formatted_content` has markdown with badges
- **Summary sensor**: State is numeric (0, 1, 2, etc.) for easy conditional visibility
- All timestamps formatted with locale awareness
- API text selection handles multiple XML formats: `xml:lang`, `lang`, `<Language>` elements

### Status Types
- `open`: Active disruption happening now
- `planned`: Scheduled future disruption
- `expired`: Disruption that has ended

### API Handling
- Rate limiting with exponential backoff (429 errors)
- Pagination support using `MoreData` flag
- Lowercase-safe progress detection for API variations
- Multi-language text selection with fallback logic in `_select_text_by_language()`

## Important Patterns

### Adding New Features
1. Consider language support from the start - add to both templates
2. Use the summary sensor for aggregate information
3. Maintain the TravelTag badge styling consistency
4. Always provide locale-aware date formatting

### Testing Badge Changes
- Use `badge_generator.py` standalone tool for visual testing
- Outputs to `badge_samples/` directory with HTML preview
- Test all 12 transport modes before integrating

### Configuration
- No language configuration option - always follows HA's language setting
- Device name is user-configurable (used in sensor entity IDs)
- Summary sensor creation is optional (can be disabled)

## Entur documentation — machine-readable

Entur publishes its docs for LLMs. **Prefer these over scraping the HTML site or
guessing at API behaviour.**

| URL | What it is |
|---|---|
| `https://developer.entur.no/llms.txt` | Index of every doc page, ~7 KB — **start here as an agent** |
| `https://developer.entur.no/llms-full.txt` | All documentation in one file, ~200 KB |
| `https://developer.entur.no/<path>.md` | Any page as Markdown, e.g. `/docs/authentication.md` |
| `https://developer.entur.no/docs/getting-started.md` | Human onboarding: service tiers, `ET-Client-Name`, first call |

Entur's own guidance calls `/llms.txt` "the best starting point for any LLM".
`getting-started.md` is written for a person arriving new and its Markdown leaks
raw MDX components, so read it for conventions and use `llms.txt` to find things.

Gotcha: these live at the **site root**, not under `/docs`. `/llms.txt` works;
`/docs/llms.txt` returns 404.

Most useful pages for this integration:
- `/open-data/realtime.md` — the SIRI/GTFS-RT feeds, and the **"Available data
  streams" table**, which is the authoritative list of codespace owners
- `/docs/open-services/journey-planner/rate-limiting.md` — quota rules
- `/apis/api-specs.md` — every OpenAPI/GraphQL spec with download URLs

`ET-Client-Name` is mandatory on every Entur API and must be
`<company>-<application>`, lowercase without spaces; requests without it may be
rate limited or blocked. This integration sends `homeassistant-entur-sx`.

### Verified API facts (checked 2026-08-04)

Do not re-derive these; they are easy to get wrong.

- **`SituationNumber` is always present** and its codespace prefix identifies the
  **publisher** (verified 126/126 situations across SKY, RUT, ATB, KOL). Use it
  for identity and provenance — see `EnturSXApiClient._publisher()`.
- **`ParticipantRef` is NOT the publisher.** It echoes the dataset queried, so
  every situation in the SKY feed says `SKY` even when published by GCO.
- **Two publishers routinely report the same real-world event.** Line 1033 has
  carried both a Skyss `incident` and a Fjord1-via-GCO `general` message for one
  emergency-vehicle transport. Duplicate-looking alerts are usually correct;
  check `situation_number` before assuming a parsing bug. `Severity: noImpact`
  tends to mark the redundant one.
- **Codespace owner = `authorities`, not `operators`.** `operators` returns the
  companies running services, so a codespace's operators include minor ones
  (`BRA` → "Forsvarsbygg Oscarsborgfergen"). The owner is in `authorities`,
  usually where the id suffix matches the codespace (`SKY:Authority:SKY`) or
  where it is the only one. Assume the API is right and `CODESPACE_NAMES` is
  stale — Norwegian authorities rebrand often (NSB→Vy, Troms
  fylkestrafikk→Svipper) while the codespace tag is kept stable.
- **`Affects` may target `Networks`, `StopPoints` or `VehicleJourneys`.** Only
  `Networks` is handled; the other two are logged at debug and skipped.
- **Descriptions can contain HTML** — `<br>` and `<a href>` both occur live. See
  the escaping note in `HTMLSanitizer`: `HTMLParser` decodes character
  references, so anything re-emitted must be re-escaped or encoded text becomes
  live markup.

## Dependencies
- Entur SIRI-SX REST API: https://api.entur.io/realtime/v1/rest/sx
- Entur Design System for icons and colors (EUPL-1.2 licensed)
- Home Assistant core (sensor platform, coordinator pattern)
- Jinja2 for markdown templates

## Common Tasks

### Adding Transport Modes
1. Add icon SVG to `icons/{Mode}_white.svg` (repository root)
2. Update `icon_constants.py` with color in `TRANSPORT_COLORS`
3. Regenerate icon constants or add manually
4. Update detection heuristics in `_detect_transport_mode()`

### Modifying Templates
- Edit both `formatted_content.j2` (English) and `formatted_content_no.j2` (Norwegian)
- Use `{{ badge_markup | safe }}` for badge HTML
- Maintain consistent formatting between languages

### Debugging API Issues
- Enable disruption tracking: `custom_components.entur_sx.coordinator.disruptions: info`
- Check for rate limiting (429 errors) in logs
- Verify operator codes match Entur's authority IDs

## Design Principles
- Automatic over manual: Language from HA, operators/lines from API discovery
- Visual consistency: Follow Entur Design System exactly
- User-friendly: Numeric states for easy automation, clean markdown for display
- Robust: Handle API inconsistencies, rate limits, and missing data gracefully
- Bilingual: Always support Norwegian and English equally
