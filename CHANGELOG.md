# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
