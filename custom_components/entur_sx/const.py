"""Constants for the Entur Situation Exchange integration."""
DOMAIN = "entur_sx"

# Configuration
CONF_OPERATOR = "operator"
CONF_LINES_TO_CHECK = "lines_to_check"
CONF_LINE_TRANSPORT_MODES = "line_transport_modes"  # Dict mapping line_id -> transport_mode from API
CONF_DEVICE_NAME = "device_name"
CONF_CREATE_SUMMARY_SENSORS = "create_summary_sensors"
CONF_SUMMARY_ICON = "summary_icon"

# Defaults
DEFAULT_DEVICE_NAME = "Entur Disruption"  # Fallback only, translations preferred
DEFAULT_CREATE_SUMMARY_SENSORS = True
DEFAULT_SUMMARY_ICON = "mdi:bus-alert"
DEFAULT_LANG = "en"  # Default to English if HA language cannot be determined
UPDATE_INTERVAL = 120  # seconds - exact 2× the 60s server window; ensures every request lands in its own fresh window


def normalize_language(language_code: str | None) -> str:
    """Normalize Home Assistant language code to 'no' or 'en'.
    
    Args:
        language_code: Language code from Home Assistant (e.g., 'en-US', 'nb-NO', 'nn-NO')
        
    Returns:
        'no' for Norwegian variants (Bokmål, Nynorsk, Sámi), 'en' for all others
    """
    if not language_code:
        return DEFAULT_LANG
    
    language_code = language_code.lower()
    
    # Norwegian: Bokmål (nb), Nynorsk (nn), or Sámi (se)
    if language_code.startswith(("nb", "nn", "se")):
        return "no"
    
    # Default to English for all other languages
    return "en"

# Back-off configuration for rate limiting
BACKOFF_INITIAL = 120  # 2 minutes on first throttle
BACKOFF_MULTIPLIER = 2.5  # Exponential increase
BACKOFF_MAX = 600  # Max 10 minutes
BACKOFF_RESET_AFTER = 1800  # Reset to normal after 30 min of success

# Icon options for summary sensors
SUMMARY_ICON_OPTIONS = [
    "mdi:bus-alert",
    "mdi:bus",
    "mdi:tram",
    "mdi:train",
    "mdi:ferry",
    "mdi:subway-variant",
    "mdi:alert-circle",
    "mdi:transit-connection-variant",
]

# API
API_BASE_URL = "https://api.entur.io/realtime/v1/rest/sx"
API_GRAPHQL_URL = "https://api.entur.io/journey-planner/v3/graphql"

# States
STATE_NORMAL = "Normal service"

# Status values
STATUS_PLANNED = "planned"
STATUS_OPEN = "open"
STATUS_EXPIRED = "expired"

# Codespace to friendly name mapping
#
# WHY THIS MAPPING EXISTS:
# The SIRI-SX API uses 3-letter codespaces (e.g., "SKY", "SOF") to identify regional
# transport authorities. However, Entur's public APIs don't provide a way to map these
# codespaces to user-friendly regional authority names:
#
# - The GraphQL operators/authorities APIs return individual transport company names
#   (e.g., "GulenSkyss AS", "Fjord1 ASA") not regional authority names
# - The Organizations API v3 has the data we need (/v3/codespaces endpoint) but it's
#   an internal/partner API requiring authentication (returns 401 for public access)
# - The official codespace documentation (https://enturas.atlassian.net/wiki/spaces/PUBLIC/pages/637370434/)
#   is the authoritative public source for regional transport authority names
#
# This mapping bridges that gap, allowing users to select their region by name
# (e.g., "Sogn og Fjordane") rather than having to know the codespace identifier.
#
# Sources, cross-checked 2026-08-04:
#   - the "Available data streams" table at developer.entur.no/open-data/realtime.md
#   - the journey-planner GraphQL `authorities` collection (live)
#
# This table is a TIEBREAK, not a correction of the API.  A codespace legitimately
# hosts several authorities — BRA holds both "Brakar" and the small
# "Forsvarsbygg Oscarsborgfergen"; TEL holds "Farte" plus three ferry
# authorities — so there is no single name to read off, and 6 of 24 codespaces
# are ambiguous that way.  Where a canonical authority IS identifiable (its id
# suffix matches the codespace, e.g. SKY:Authority:SKY, or it is the only one),
# the API agrees with this table on 15 of 17 resolvable codespaces.
#
# Do not assume the API is wrong when it differs — it is live and this table is
# a snapshot, so the API is often the MORE current of the two.  Both known
# differences went against the static sources: TRO's sole authority is "Svipper"
# (the current brand; both this table and Entur's own docs table still said
# "Troms fylkestrafikk"), and NBU's is "Flybussen Connect".  Norwegian transport
# authorities rebrand and merge regularly — NSB became Vy, Sogn og Fjordane was
# reorganised into Kringom under Vestland — while the codespace tag is kept
# stable for continuity.  So a mismatch here is far more likely to be this file
# going stale than an error upstream.
#
# Note that async_get_operators() prefers this table over the API name, so a
# wrong or stale entry SUPPRESSES the live value rather than supplementing it.
#
# Names must not embed the 3-letter code: async_get_operators() renders them as
# "{name} ({codespace})".
# The codespace is what's used in the SIRI-SX datasetId parameter, and also the
# prefix of every SituationNumber — see EnturSXApiClient._publisher().
# ET-Client-Name is mandatory on every Entur API call, open or partner, and must
# be "<company>-<application>" (lowercase, no spaces).  Requests without it may
# be rate limited or blocked.  See developer.entur.no/docs/getting-started.md.
#
# Define it ONCE here.  Per-instance calls append a short Home Assistant
# instance id so Entur can attribute rate-limit usage to a single installation;
# the static discovery helpers, which have no hass reference, send the base value.
ET_CLIENT_NAME = "homeassistant-entur-sx"

CODESPACE_NAMES = {
    # Regional transport authorities and national operators
    "AKT": "Agder Kollektivtrafikk",
    "ATB": "AtB",
    "AVI": "Avinor",
    "BNR": "SJ Nord via Bane NOR",
    "BRA": "Brakar",
    "FIN": "Snelandia",
    "FLT": "Flytoget",
    "GOA": "Go-Ahead Norge",
    "INN": "Innlandstrafikk",
    "KOL": "Kolumbus",
    "MOR": "FRAM",
    "NBU": "Flybussen Connect",   # live authority name; docs table says "Connect Bus Flybuss"
    "NOR": "Nordland fylkeskommune",
    "NSB": "Vy",
    "OST": "Østfold kollektivtrafikk",
    "RUT": "Ruter",
    "SJN": "SJ Nord",
    "SKY": "Skyss",
    "SOF": "Kringom",
    "TEL": "Farte",
    "TRO": "Svipper",             # rebranded from Troms fylkestrafikk; sole TRO authority
    "VKT": "VKT",
    "VOT": "Vestfold og Telemark",
    "VYB": "Vy Bus4You",
    "VYG": "Vy Group",
    "VYX": "Vy Express",

    # Codespaces that appear in SIRI-SX but have no published name anywhere.
    #
    # GCO is not resolvable by any means available.  Checked 2026-08-04:
    #   - absent from the 275 operators and 79 authorities in journey-planner
    #   - absent from the vehicles API's codespaces query, whose Codespace type
    #     exposes only codespaceId — there is no name field to query
    #   - absent from the "Available data streams" table above
    #   - zero occurrences in the whole of developer.entur.no (llms-full.txt)
    #   - api.entur.io/organisations/v1/organisations does not exist (404)
    # It *is* a valid datasetId, publishing against SKY, NOR, FIN, KOL and ATB
    # lines — a shared channel operators publish through on an authority's
    # behalf ("Mvh Fjord1 på vegner av Skyss").  Left as the bare code
    # deliberately rather than guessing a company name.
    "CTS": "CTS",
    "GCO": "GCO",
}

