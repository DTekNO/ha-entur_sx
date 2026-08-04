# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026.8.1]

Alerts now say **who reported them**. When a line shows two near-identical
disruptions, that is usually one real event reported by two publishers — this
release exposes the fields that tell them apart, so a card can show it. Also
hardens the feed parser: a single malformed situation no longer wipes out every
line's data for that update, and the HTML sanitizer no longer turns safely
encoded text into live markup.

### Added
- **🏷️ Publisher and identity attributes**: Line sensors, and every entry in `all_deviations`, now carry `situation_number`, `publisher`, `publisher_name`, `severity`, `report_type` and `created`. This answers the "why am I seeing the same disruption twice?" question — e.g. Skyss line 1033 has carried a Skyss `incident` ("Forseinkingar i sambandet…") alongside a Fjord1-via-GCO `general` message ("Trafikkmelding") for a single emergency-vehicle transport. Both are genuine; they are separate situations from separate publishers. `publisher_name` lets a card label them, and `severity: noImpact` usually marks the redundant advisory if you would rather hide it.
- **🗺️ Six more transport authorities recognised**: `AVI` (Avinor), `BNR` (SJ Nord via Bane NOR), `FIN` (Snelandia), `FLT` (Flytoget), `NOR` (Nordland fylkeskommune) and `VOT` (Vestfold og Telemark) now resolve to names instead of showing a bare 3-letter code. Two of these appear in cross-authority feeds already.

### Fixed
- **🛡️ HTML sanitizer turned encoded text into live markup**: `HTMLParser` decodes character references before handing them over, and the sanitizer echoed them back raw — so an attribute that arrived safely encoded came out as a working event handler (`title="x&quot; onerror=&quot;alert(1)"` → `title="x" onerror="alert(1)"`). Attribute names, values and text are now re-escaped on output. Descriptions are publisher-authored, so this is worth having even though the feed comes via Entur. Verified against the live all-Norway feed: of 971 text fields exactly one changes, and only to encode a bare `&` in an image URL, which renders identically.
- **🧱 One bad situation no longer discards the whole update**: parse errors were caught around the entire loop, so a single malformed situation aborted the pass and threw away every line's data for that cycle. Measured with one corrupted validity period: previously a bad entry early in the feed lost all 33 lines, now only its own line is affected. Errors are logged per situation with the `SituationNumber`.
- **🔑 `ET-Client-Name` was still shared on discovery calls**: 2026.3.3 gave each installation a unique client name because Entur applies rate-limit quota per header value, but the operator- and line-discovery lookups still sent the shared name, so all installations remained pooled for those requests. They now send the installation-unique value too. (These use the journey-planner API, whose limits are much roomier than the 5 req/min SIRI-SX pool, so this was unlikely to have caused visible problems.)
- **🏷️ Stale authority names corrected**: `TRO` is **Svipper** (rebranded from Troms fylkestrafikk), `NSB` is **Vy**, `SOF` is **Kringom**, `VYG` is **Vy Group** (previously "Vy", which collided with NSB), `VYX` is **Vy Express**, `NBU` is **Flybussen Connect**. Norwegian transport authorities rebrand and merge regularly while their codespace tag stays stable for continuity.
- **📝 Malformed HTML edge cases**: valueless attributes no longer become `nowrap="None"`, implicitly-closed siblings are nested correctly (`<ul><li>a<li>b` now yields `<li>a</li><li>b</li>` rather than mis-nested `</li></li>`), and explicitly self-closed tags such as `<br/>` are handled.

### Changed
- **🔍 Unsupported situation types are now visible in logs**: situations that target only `StopPoints` or `VehicleJourneys` rather than a line network — stop closures and single-departure cancellations — are still not turned into sensor data, but they are logged at debug level with what they do affect, instead of being dropped silently. On a typical Skyss feed this is around 4 of 24 situations.
- **🧹 Internal**: per-situation parsing extracted to `_parse_situation()`; `ET-Client-Name` defined once as `ET_CLIENT_NAME` and built once by `async_client_name()`; SIRI JSON field access hardened against the API's `{"value": x}`-versus-bare-scalar and object-versus-array inconsistencies.

### Compatibility
- All new attributes are additive — existing markdown cards, templates and automations continue to work unchanged
- Publisher information comes from the `SituationNumber` codespace prefix, which is present on every situation (verified across the SKY, RUT, ATB and KOL feeds)
- `GCO` has no published name anywhere in Entur's APIs or documentation, so it displays as `GCO`. It is a shared channel that operators publish through on an authority's behalf
- Internal signature change for anyone forking: `async_get_operators()` and `async_get_lines_for_operator()` now take `hass` as their first argument

### Documentation
- **🤖 Agent guidance**: added `CLAUDE.md` and expanded `.github/copilot-instructions.md` with Entur's machine-readable documentation endpoints (`/llms.txt`, `/llms-full.txt`, and `.md` on any page — note these are at the site root, not under `/docs`) plus the API facts that are easy to get wrong, such as `ParticipantRef` not being the publisher and codespace owners living in `authorities` rather than `operators`.

## [2026.7.1]

### Added
- **Per-alert `formatted_content`**: Each deviation in the `all_deviations` attribute now carries its own `formatted_content` field. When used with [ha-alert-card](https://github.com/DTekNO/ha-alert-card), expanding an alert shows only that disruption's detail — dates and description — not all disruptions on the entity.

### Changed
- **Supplementary expansion mode**: The Jinja2 templates (`formatted_content.j2` / `formatted_content_no.j2`) now accept a `per_item` flag. When rendering per-alert content, the travel_tag badge and description body are omitted — the card row already shows these via `image_attribute: travel_tag`. Only the From/To date block is rendered, eliminating redundancy in the expanded view.
- **Recorder exclusion**: `all_deviations` added to `_unrecorded_attributes` — the attribute (which contains embedded HTML) is no longer written to the history database.

### Compatibility
- Works with ha-alert-card `image_attribute: travel_tag` to show the TravelTag badge in each alert row
- Entity-level `formatted_content` is unchanged — existing markdown cards continue to work without any changes

## [2026.3.4]

### Fixed
- **🎨 TravelTag transport mode in summary entity**: The summary sensor's `markdown_active` and `markdown_planned` attributes now show the correct transport mode icon and color in TravelTag badges. Previously the badge always fell back to bus (red) regardless of the actual mode (e.g. tram/Bybanen showed a bus badge). The summary sensor now reuses the already-generated `travel_tag` from each line sensor's live state via the entity registry, falling back to on-the-fly generation with correct mode mapping only if the line sensor is not yet available.

## [2026.3.3]

### Fixed
- **🔑 Unique ET-Client-Name per installation**: Each HA instance now sends a unique `ET-Client-Name` header (`homeassistant-entur-sx-<8-char-uid>`) derived from HA's stable instance UUID. Previously all installations shared the same client name and therefore the same rate-limit quota pool on the Entur API. Each installation now gets its own independent 5 req/min quota.

## [2026.3.2]

### Changed

- **⚡ Quota manager rewrite**: Should now never get 429 Rate limit error


## [2026.03.1]

### Fixed
- **🕐 Timezone Handling**: Fixed "can't subtract offset-naive and offset-aware datetimes" error
  - Properly normalize rate limit expiry times to UTC timezone
  - Ensure all datetime comparisons use timezone-aware datetimes
  - Prevents recurring errors when calculating quota wait times
  - Fixed timestamp calculations to use UTC-aware datetime objects

## [2026.02.4]

### Changed
- **📊 Summary Sensor Attributes**: Simplified summary sensor to focus on separation by status
  - Removed `formatted_content` attribute (combined disruptions)
  - Kept `markdown_active` for active (open) disruptions only
  - Kept `markdown_planned` for planned disruptions only
  - Summary sensor now references line sensors' `travel_tag` attribute for consistency
  - Ensures badges are identical between line sensors and summary views

### Fixed
- **🔧 Template Rendering**: Fixed template error when rendering summary markdown
  - Added required `line_name` and `transport_mode` fields to disruption dictionaries
  - Resolves "dict object has no attribute 'line_name'" error in planned disruptions
- **📊 Summary Sensor State & Attributes**: Fixed calculation of disruptions
  - Removed incorrect check for STATE_NORMAL in first deviation that was filtering out valid disruptions
  - Summary sensor now correctly counts and displays all planned disruptions
  - State now accurately reflects count of all lines with non-expired disruptions (open + planned)
  - Attributes (`planned_disruptions`, `markdown_planned`) now correctly populated

## [2026.02.2]

### Added
- **🛡️ HTML Sanitizer**: Automatic cleanup of malformed HTML from API
  - Fixes unclosed tags in operator-provided descriptions (e.g., `<ul>`, `<b>`, `<li>`)
  - Prevents markdown rendering issues caused by broken HTML
  - Smart inline tag closure when parent block elements close
  - Preserves properly formatted HTML while fixing errors

- **🎨 Enhanced Visual Layout**: Improved disruption display with Home Assistant components
  - Banner-style `<ha-alert>` boxes for visual hierarchy
  - Badge displayed in separate red alert header per transit line
  - Each disruption shown in its own red alert box with summary as title
  - Dates displayed in styled table (bold labels, italic values) within alert
  - Description text contained within alert for proper alignment and background
  - Clear visual separation when multiple disruptions affect same line

### Changed
- **📋 Template-Based Rendering**: Summary sensor now uses Jinja2 templates
  - Consistent rendering between individual line sensors and summary sensor
  - All formatting logic centralized in templates for easier customization
  - Automatic grouping of disruptions by line using `groupby` filter
  - Cleaner Python code without HTML/markdown string concatenation

- **🔧 Badge Display Improvements**: Higher quality badges in summary attributes
  - Increased badge height from 28px to 32px for crisp display at natural size
  - Fixed markdown indentation issues with proper separator formatting
  - One badge per line with all disruptions grouped underneath

- **🎯 Disruption Consolidation**: Multiple disruptions for same line now grouped together
  - Single badge displayed per transit line
  - All disruptions for that line stacked underneath
  - Clear visual hierarchy with horizontal rules between different lines
  - Eliminates duplicate badges for lines with multiple issues

### Fixed
- **⏱️ Rate Limit Compliance**: Increased update interval from 60 to 75 seconds
  - Entur API enforces 5 requests per 5-minute **rolling window** (not fixed window)
  - Previous 60-second interval caused periodic 429 errors after ~5-6 minutes of operation
  - New 75-second interval (300s / 5 = 60s + 15s safety margin) ensures compliance
  - Updated documentation to accurately describe rolling window behavior
  - Fixed incorrect "5 requests per minute" comment in code (actual limit: 5 per 5 minutes)

### Changed
- **💾 Recorder Optimization**: Excluded large attributes from state history
  - Line sensors: `formatted_content` and `entity_picture` excluded from recorder
  - Summary sensor: `markdown_active` and `markdown_planned` excluded from recorder
  - Significantly reduces database size without losing functionality
  - Follows Home Assistant best practices for attributes not suitable for history

## [2026.02.1]

### Added
- **🎨 Entur TravelTag Badges**: Professional transit line badges with official Entur Design System styling
  - Automatically displayed as entity pictures on line sensors
  - 12 transport mode icons: bus, train, tram, ferry, carferry, metro, mobility, bicycle, walk, plane, helicopter, taxi
  - Official Entur brand colors for each transport mode
  - Proportional scaling matching Entur's design (14pt base font, 26.25px icons)
  - Line numbers displayed in badges with dynamic sizing
  
- **📊 Summary Sensor**: Aggregate sensor for all monitored lines
  - Numeric state (0, 1, 2, etc.) showing count of active disruptions
  - Perfect for conditional card visibility using `numeric_state` conditions
  - `markdown_active` attribute: All active disruptions with badges in markdown format
  - `markdown_planned` attribute: All planned disruptions with badges
  - Easy automation: trigger when summary state goes above 0

- **🌍 Automatic Language Support**: Norwegian and English based on Home Assistant settings
  - Automatically detects language from `hass.config.language`
  - Norwegian (no): Supports nb, nn, se language codes
  - English (en): Default for all other languages
  - Locale-aware date formatting:
    - Norwegian: "Mandag, 09. februar kl. 14:30"
    - English: "Monday, 09 February at 14:30"
  - Smart API text selection handling multiple XML language tag formats

- **📝 Rich Markdown Content**: `formatted_content` attribute on all line sensors
  - TravelTag badges with line numbers and transport mode colors
  - Disruption summaries and detailed descriptions
  - Formatted validity periods with locale-aware dates
  - Professional styling matching Entur's design language
  - Ready for use in Home Assistant markdown cards

### Changed
- **Summary sensor state**: Now returns numeric count instead of text (e.g., `0` instead of "Normal service")
- **Date formatting**: Valid from/to timestamps now locale-formatted instead of ISO 8601
- **Language configuration**: Removed manual language setting - now automatically follows Home Assistant's language preference

### Developer Notes
- Added `icon_constants.py`: Transport mode icons and brand colors from Entur Design System
- Added `templates/formatted_content.j2`: English markdown template
- Added `templates/formatted_content_no.j2`: Norwegian markdown template  
- Added `normalize_language()` function in `const.py` for language code mapping
- Created standalone `badge_generator.py` tool for badge design and testing
- Enhanced API client with `_select_text_by_language()` for robust multi-format XML parsing

---

## Release Notes Template

Copy the section below for GitHub releases:

---

## 🎨 Major Update: TravelTag Badges, Summary Sensors & Language Support

This release adds beautiful visual badges, aggregate disruption tracking, and automatic language support to make monitoring Norwegian transit disruptions even better!

### ✨ What's New

**🎨 Entur TravelTag Badges**
- Professional transit line badges automatically appear on all line sensors
- 12 transport modes with official Entur Design System colors and icons
- Perfect proportional scaling matching Entur's design standards
- Line numbers dynamically sized in badges

**📊 Summary Sensor**
- New aggregate sensor shows total active disruptions across all monitored lines
- Numeric state (0, 1, 2, etc.) makes conditional card visibility easy
- Rich markdown attributes (`markdown_active`, `markdown_planned`) with badges for all disrupted lines
- Simple automation: trigger when summaries > 0

**🌍 Automatic Language Support**
- Norwegian and English templates based on your Home Assistant language setting
- Beautiful locale-aware date formatting (e.g., "Mandag, 09. februar kl. 14:30")
- Handles multiple API language tag formats automatically
- No configuration needed - just works!

**📱 Rich Markdown Content**
- New `formatted_content` attribute on every sensor
- Drop into markdown cards for instant professional displays
- TravelTag badges with line info, summaries, and formatted dates
- Perfect for dashboards and notifications

### 🔧 Breaking Changes
- Summary sensor state is now numeric (e.g., `0` not "Normal service") - update conditional cards to use `numeric_state` conditions
- Removed manual language configuration option - now follows HA language automatically

### 📸 Example

```yaml
type: conditional
conditions:
  - condition: numeric_state
    entity: sensor.skyss_disruption_summary
    above: 0
card:
  type: markdown
  title: 🚨 Active Transit Disruptions
  content: |
    {{ state_attr('sensor.skyss_disruption_summary', 'markdown_active') }}
```

### 🙏 Acknowledgments
- Icons and colors from [Entur Design System](https://github.com/entur/design-system) (EUPL-1.2)
- Design inspired by Entur's TravelTag component

**Full Changelog**: See CHANGELOG.md
