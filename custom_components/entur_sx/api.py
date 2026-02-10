"""API client for Entur Situation Exchange."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from email.utils import parsedate_to_datetime

import aiohttp
import async_timeout

from .const import API_BASE_URL, API_GRAPHQL_URL, CODESPACE_NAMES, STATE_NORMAL, STATUS_EXPIRED, STATUS_PLANNED, STATUS_OPEN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Global quota manager key for hass.data
QUOTA_MANAGER_KEY = "entur_sx_quota_manager"


class GlobalQuotaManager:
    """Centralized quota manager shared across all API clients.
    
    Singleton that enforces 4 requests per 60-second rolling window globally
    across all config entries, coordinators, and config flow requests.
    """
    
    def __init__(self):
        """Initialize global quota manager."""
        # API header tracking (for respecting server-side limits)
        self.allowed: int | None = None
        self.available: int | None = None
        self.used: int | None = None
        self.expiry_time: str | None = None
        self.expiry_datetime: datetime | None = None
        
        # Rolling window tracking (our internal quota: 4 requests per 60 seconds)
        self.request_timestamps: deque = deque(maxlen=4)  # Last 4 request times
        self.window_seconds: float = 60.0  # Rolling window duration
        self.max_requests_per_window: int = 4  # Maximum requests in window
        
        # Lock to prevent race conditions across async requests
        self._lock = asyncio.Lock()
        
        _LOGGER.info("Global Entur API quota manager initialized (4 req/60s limit)")
    
    def update_from_headers(self, headers: dict) -> None:
        """Update rate limit info from response headers.
        
        Args:
            headers: Response headers containing rate-limit-* fields
        """
        if "rate-limit-allowed" in headers:
            self.allowed = int(headers["rate-limit-allowed"])
        if "rate-limit-available" in headers:
            self.available = int(headers["rate-limit-available"])
        if "rate-limit-used" in headers:
            self.used = int(headers["rate-limit-used"])
        if "rate-limit-expiry-time" in headers:
            self.expiry_time = headers["rate-limit-expiry-time"]
            # Parse the expiry time to datetime for calculations
            try:
                self.expiry_datetime = parsedate_to_datetime(self.expiry_time)
            except Exception as err:
                _LOGGER.debug("Could not parse expiry time '%s': %s", self.expiry_time, err)
                self.expiry_datetime = None
        
        # Log rate limit info for monitoring
        if self.available is not None and self.allowed is not None:
            if self.available <= 1:
                _LOGGER.warning(
                    "API rate limit headers show low quota: %d/%d requests remaining until %s",
                    self.available,
                    self.allowed,
                    self.expiry_time or "unknown"
                )
            elif self.available <= 2:
                _LOGGER.info(
                    "API rate limit headers: %d/%d requests remaining until %s",
                    self.available,
                    self.allowed,
                    self.expiry_time or "unknown"
                )
    
    def get_internal_quota_available(self) -> int:
        """Get number of requests available in our internal rolling window.
        
        Returns:
            Number of requests we can make without exceeding 4 per 60 seconds
        """
        now = time.time()
        # Remove timestamps older than 60 seconds
        while self.request_timestamps and (now - self.request_timestamps[0]) > self.window_seconds:
            self.request_timestamps.popleft()
        
        return self.max_requests_per_window - len(self.request_timestamps)
    
    def get_seconds_until_quota_available(self) -> float:
        """Calculate seconds until at least 1 request quota is available.
        
        Returns:
            Seconds to wait, or 0 if quota currently available
        """
        if self.get_internal_quota_available() > 0:
            return 0.0
        
        # We're at limit. Calculate when oldest request will expire from window
        now = time.time()
        oldest_request = self.request_timestamps[0]
        time_until_expiry = self.window_seconds - (now - oldest_request)
        
        # Add 0.5 second safety margin
        return max(0, time_until_expiry + 0.5)
    
    def can_make_request(self) -> tuple[bool, str]:
        """Check if we can make a request based on both internal and API quotas.
        
        Returns:
            Tuple of (can_proceed, reason_if_not)
        """
        # Check internal rolling window quota
        internal_available = self.get_internal_quota_available()
        if internal_available <= 0:
            wait_time = self.get_seconds_until_quota_available()
            return False, f"internal quota exhausted (4 req/60s limit), wait {wait_time:.1f}s"
        
        # Check API header quota (if available)
        if self.available is not None and self.available <= 0:
            return False, f"API header shows no quota ({self.available}/{self.allowed})"
        
        return True, ""
    
    async def wait_for_quota(self) -> None:
        """Wait until request quota is available."""
        wait_time = self.get_seconds_until_quota_available()
        
        if wait_time > 0:
            _LOGGER.info(
                "[GLOBAL QUOTA] %d/4 internal quota used. Waiting %.1f seconds for quota restoration.",
                len(self.request_timestamps),
                wait_time
            )
            await asyncio.sleep(wait_time)
    
    def record_request(self, operator: str | None = None) -> None:
        """Record that a request was made (for rolling window tracking).
        
        Args:
            operator: Optional operator/provider for logging
        """
        self.request_timestamps.append(time.time())
        used = len(self.request_timestamps)
        available = self.max_requests_per_window - used
        
        # Use INFO level so users can see quota manager working
        _LOGGER.info(
            "[GLOBAL QUOTA] Request completed for %s. Quota: %d/4 used, %d remaining",
            operator or "unknown",
            used,
            available
        )
    
    def get_time_since_last_request(self) -> float:
        """Get seconds since last request.
        
        Returns:
            Seconds elapsed since last request, or infinity if no previous request
        """
        if not self.request_timestamps:
            return float('inf')
        return time.time() - self.request_timestamps[-1]


def get_quota_manager(hass: HomeAssistant) -> GlobalQuotaManager:
    """Get or create the global quota manager singleton.
    
    Args:
        hass: Home Assistant instance
        
    Returns:
        The global quota manager instance
    """
    if QUOTA_MANAGER_KEY not in hass.data:
        hass.data[QUOTA_MANAGER_KEY] = GlobalQuotaManager()
    return hass.data[QUOTA_MANAGER_KEY]


class EnturSXApiClient:
    """API client for Entur Situation Exchange."""

    def __init__(
        self,
        hass: HomeAssistant,
        operator: str | None = None,
        lines: list[str] | None = None,
        lang: str = "no",
    ) -> None:
        """Initialize the API client.
        
        Args:
            hass: Home Assistant instance
            operator: Codespace (e.g., "SKY", "SOF")
            lines: List of line IDs to monitor
            lang: Preferred language code ("no" or "en")
        """
        self._hass = hass
        self._operator = operator
        self._lines = lines or []
        self._lang = lang
        self._session: aiohttp.ClientSession | None = None
        
        # Get the global quota manager singleton
        self._quota_manager = get_quota_manager(hass)

        # The operator is now the codespace directly (e.g., "SKY", "SOF")
        # This is what we use for the SIRI-SX datasetId parameter
        self._operator_code = operator if operator else None
        
        if operator:
            self._service_url = f"{API_BASE_URL}?datasetId={operator}"
        else:
            self._service_url = API_BASE_URL

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """Set the aiohttp session."""
        self._session = session

    def _select_text_by_language(self, text_objects: list[dict[str, Any]]) -> str:
        """Select best text from array based on language preference.
        
        The Entur API returns Summary and Description as arrays of objects with:
        - 'value': the text content
        - Language codes in various formats:
          * 'xml:lang' attribute (proper XML syntax, e.g., xml:lang="EN")
          * 'lang' field (lowercase)
          * 'Language' field (mixed case, sometimes inconsistent)
        
        Args:
            text_objects: List of text objects from API (e.g., Summary or Description array)
            
        Returns:
            Selected text string, or empty string if no text available
        """
        if not text_objects:
            return ""
        
        # If only one text available, use it regardless of language
        if len(text_objects) == 1:
            return text_objects[0].get("value", "")
        
        # Try to find text in preferred language
        preferred_lang = self._lang.lower()
        for text_obj in text_objects:
            # Check multiple possible language field names (API is inconsistent):
            # - 'xml:lang' (proper XML attribute syntax)
            # - 'lang' (alternative field name)
            # - 'Language' (another variant)
            lang_code = (
                text_obj.get("xml:lang", "") or 
                text_obj.get("lang", "") or 
                text_obj.get("Language", "")
            ).lower()
            
            if lang_code and lang_code.startswith(preferred_lang):
                return text_obj.get("value", "")
        
        # If preferred language not found:
        # - For Norwegian users: Just use first text (likely Norwegian anyway)
        # - For English users: Try to find any English text before falling back
        if preferred_lang != "no":
            for text_obj in text_objects:
                lang_code = (
                    text_obj.get("xml:lang", "") or 
                    text_obj.get("lang", "") or 
                    text_obj.get("Language", "")
                ).lower()
                if lang_code and lang_code.startswith("en"):
                    return text_obj.get("value", "")
        
        # Fall back to first available text
        return text_objects[0].get("value", "")

    async def async_get_deviations(self) -> dict[str, Any]:
        """Fetch deviation data for configured lines.
        
        Handles pagination when MoreData=true using requestorId to retrieve
        all situations in extreme weather scenarios (flooding, heavy snow).
        Uses smart quota management: allows rapid requests (burst) during pagination
        as long as staying within 4 requests per 60-second rolling window.
        
        Returns:
            Dict mapping line reference to list of deviations with status, e.g.
            {"SKY:Line:1": [{"valid_from": "...", "valid_to": "...", "summary": "...", 
                             "description": "...", "status": "open"}]}
        """
        if not self._session:
            _LOGGER.error("Session not set")
            return {}

        headers = {"Content-Type": "application/json"}
        
        # Generate requestorId for pagination tracking
        requestor_id = str(uuid.uuid4())
        all_situations = []
        page_count = 0
        max_pages = 20  # Safety limit to prevent infinite loops
        data = None  # Initialize to handle early breaks

        try:
            # Timeout must accommodate quota waits: 20 pages with potential 60s waits
            async with async_timeout.timeout(350):
                while page_count < max_pages:
                    # CRITICAL: Check quota through GLOBAL manager before every request
                    # This ensures all API clients, coordinators, and config flows respect the same quota
                    async with self._quota_manager._lock:
                        internal_used = len(self._quota_manager.request_timestamps)
                        can_proceed, reason = self._quota_manager.can_make_request()
                        
                        # Log quota state for debugging (only if we've made requests before)
                        if internal_used > 0:
                            _LOGGER.debug(
                                "[%s] Quota check before page %d: %d/4 requests in last 60s, can_proceed=%s",
                                self._operator_code or "ALL",
                                page_count + 1,
                                internal_used,
                                can_proceed
                            )
                        
                        if not can_proceed:
                            # Release lock before waiting
                            _LOGGER.info(
                                "[%s] Rate limit before page %d: %s. Internal tracker: %d/4 requests in last 60s.",
                                self._operator_code or "ALL",
                                page_count + 1,
                                reason,
                                internal_used
                            )
                    
                    # If we can't proceed, wait outside the lock
                    if not can_proceed:
                        await self._quota_manager.wait_for_quota()
                        _LOGGER.info(
                            "[%s] Quota restored, resuming for page %d",
                            self._operator_code or "ALL",
                            page_count + 1
                        )
                    
                    page_count += 1
                    
                    # Record this request in the GLOBAL quota manager
                    self._quota_manager.record_request(self._operator_code)
                    
                    # Add requestorId parameter for pagination
                    url = f"{self._service_url}&requestorId={requestor_id}" if "?" in self._service_url else f"{self._service_url}?requestorId={requestor_id}"
                    
                    async with self._session.get(url, headers=headers) as response:
                        # Check for 429 rate limit errors
                        if response.status == 429:
                            _LOGGER.error(
                                "⚠️  RATE LIMIT ERROR (429) - API rejected request for %s. "
                                "Page %d of pagination. Time since last request: %.1fs. "
                                "Global quota manager should have prevented this - please report!",
                                self._operator_code or "ALL",
                                page_count,
                                self._quota_manager.get_time_since_last_request()
                            )
                            # Log headers for debugging
                            if "retry-after" in response.headers:
                                _LOGGER.error("  Retry-After header: %s", response.headers["retry-after"])
                            response.raise_for_status()
                        
                        response.raise_for_status()
                        
                        # Update quota manager from response headers
                        self._quota_manager.update_from_headers(response.headers)
                        
                        # API returns JSON but with incorrect content-type header sometimes
                        # Use text() and json.loads() to handle this
                        text = await response.text()
                        import json
                        data = json.loads(text)

                        # Extract situations from this page
                        service_delivery = data.get("Siri", {}).get("ServiceDelivery", {})
                        sx_delivery = service_delivery.get("SituationExchangeDelivery", [])
                        
                        if sx_delivery:
                            situations_obj = sx_delivery[0].get("Situations", {})
                            situations = situations_obj.get("PtSituationElement", [])
                            
                            # Ensure it's a list
                            if not isinstance(situations, list):
                                situations = [situations]
                            
                            all_situations.extend(situations)
                            
                            rate_info = ""
                            if self._quota_manager.available is not None:
                                rate_info = f" API headers: {self._quota_manager.available}/{self._quota_manager.allowed} remaining"
                            
                            _LOGGER.debug(
                                "[%s] Retrieved page %d: %d situations (total so far: %d).%s",
                                self._operator_code or "ALL",
                                page_count,
                                len(situations),
                                len(all_situations),
                                rate_info
                            )

                        # Check for MoreData flag
                        more_data = service_delivery.get("MoreData", False)
                        
                        if more_data:
                            internal_remaining = self._quota_manager.get_internal_quota_available()
                            api_quota_str = f", API: {self._quota_manager.available}/{self._quota_manager.allowed}" if self._quota_manager.available is not None else ""
                            
                            _LOGGER.info(
                                "[%s] MoreData=true, continuing pagination. Page %d: %d situations (total: %d). "
                                "Quota: %d/4 internal%s",
                                self._operator_code or "ALL",
                                page_count,
                                len(situations),
                                len(all_situations),
                                internal_remaining,
                                api_quota_str
                            )
                            # Continue loop to fetch next page with same requestorId
                        else:
                            # No more data, we're done
                            if page_count > 1:
                                _LOGGER.info(
                                    "Pagination complete: retrieved %d situations across %d pages. Operator: %s",
                                    len(all_situations),
                                    page_count,
                                    self._operator_code or "all"
                                )
                            break
                
                if page_count >= max_pages:
                    _LOGGER.warning(
                        "Reached maximum page limit (%d pages) - some disruptions may be missing. "
                        "Retrieved %d situations. Operator: %s",
                        max_pages,
                        len(all_situations),
                        self._operator_code or "all"
                    )

                # Handle case where no data was retrieved (rate limit exhausted, etc.)
                if data is None:
                    _LOGGER.warning(
                        "No data retrieved from API (page_count=%d). Returning empty result. Operator: %s",
                        page_count,
                        self._operator_code or "all"
                    )
                    return {}

                # Reconstruct response with all situations
                if page_count > 1:
                    # Multiple pages - merge all situations
                    data["Siri"]["ServiceDelivery"]["SituationExchangeDelivery"][0]["Situations"]["PtSituationElement"] = all_situations
                    # Set MoreData to false since we've fetched everything
                    data["Siri"]["ServiceDelivery"]["MoreData"] = False
                
                return self._parse_response(data)

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching data from Entur API: %s", err)
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching data from Entur API: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching Entur data: %s", err, exc_info=True)
            raise

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse the Entur API response.
        
        Args:
            data: JSON response from Entur API
            
        Returns:
            Dict mapping line reference to list of situations with status
        """
        allitems_dict = {}
        now_timestamp = datetime.now().timestamp()

        for look_for in self._lines:
            items = []

            try:
                siri = data.get("Siri", {})
                service_delivery = siri.get("ServiceDelivery", {})
                sx_delivery = service_delivery.get("SituationExchangeDelivery", [])

                for sed in sx_delivery:
                    situations = sed.get("Situations", {})
                    elements = situations.get("PtSituationElement", [])

                    for element in elements:
                        progress = element.get("Progress", "")
                        
                        # Lowercase comparison for progress (API sometimes returns lowercase)
                        progress_lower = progress.lower()

                        affects = element.get("Affects", {})
                        networks = affects.get("Networks")

                        if not networks:
                            continue

                        # Get validity period
                        validity_periods = element.get("ValidityPeriod", [])
                        if not validity_periods:
                            continue

                        validity_period = validity_periods[0]
                        start_time = validity_period.get("StartTime")
                        end_time = validity_period.get("EndTime")
                        
                        if not start_time:
                            continue

                        # Determine status based on time and Progress field
                        start_timestamp = datetime.fromisoformat(start_time).timestamp()
                        
                        # Determine status primarily based on time validity
                        if now_timestamp < start_timestamp:
                            # Future event - always planned regardless of progress
                            status = STATUS_PLANNED
                        elif end_time:
                            end_timestamp = datetime.fromisoformat(end_time).timestamp()
                            if now_timestamp > end_timestamp:
                                # Past the end time - expired
                                status = STATUS_EXPIRED
                            else:
                                # Currently active
                                # Check Progress field - if closed, it's been resolved
                                if progress_lower == "closed":
                                    status = STATUS_EXPIRED
                                else:
                                    status = STATUS_OPEN
                        else:
                            # No end time specified
                            # Check Progress field - if closed, treat as expired
                            if progress_lower == "closed":
                                status = STATUS_EXPIRED
                            else:
                                # No end time and not closed - consider it open if started
                                status = STATUS_OPEN

                        # Check if this situation affects our line
                        affected_networks = networks.get("AffectedNetwork", [])
                        for an in affected_networks:
                            affected_lines = an.get("AffectedLine", [])
                            if not affected_lines:
                                continue

                            # Check ALL affected lines, not just the first one
                            for affected_line in affected_lines:
                                line_ref_obj = affected_line.get("LineRef", {})
                                line_ref = line_ref_obj.get("value")

                                if look_for == line_ref:
                                    # Extract summary and description with language selection
                                    summaries = element.get("Summary", [])
                                    descriptions = element.get("Description", [])
                                    
                                    # Ensure they are lists
                                    if not isinstance(summaries, list):
                                        summaries = [summaries] if summaries else []
                                    if not isinstance(descriptions, list):
                                        descriptions = [descriptions] if descriptions else []

                                    summary = self._select_text_by_language(summaries) or STATE_NORMAL
                                    description = self._select_text_by_language(descriptions) or STATE_NORMAL

                                    items.append({
                                        "valid_from": start_time,
                                        "valid_to": end_time,
                                        "summary": summary,
                                        "description": description,
                                        "status": status,
                                        "progress": progress.lower(),  # Normalize to lowercase
                                    })
                                    # Don't break - a situation might affect the same line multiple times
                                    # (though unlikely, we should handle it)

                # Sort by relevance: OPEN first, then PLANNED, then EXPIRED
                # Within each status group, sort by start time (most recent first)
                if items:
                    status_priority = {STATUS_OPEN: 0, STATUS_PLANNED: 1, STATUS_EXPIRED: 2}
                    items.sort(key=lambda x: (status_priority.get(x["status"], 3), -datetime.fromisoformat(x["valid_from"]).timestamp()))
                # If no situations for this line, leave items as empty list
                # The sensor layer will display "Normal service" for empty lists

                allitems_dict[look_for] = items

            except Exception as err:
                _LOGGER.error("Error parsing data for line %s: %s", look_for, err, exc_info=True)
                # Return empty list on error - sensor will show "Normal service"
                allitems_dict[look_for] = []

        _LOGGER.debug("Parsed deviations for %d lines", len(allitems_dict))
        return allitems_dict

    @staticmethod
    async def async_get_operators(session: aiohttp.ClientSession) -> dict[str, str]:
        """Fetch list of operators (codespaces) from Entur GraphQL API.
        
        Extracts all unique 3-letter codespaces from the operators API and maps them
        to friendly names. Falls back to CODESPACE_NAMES constant for better naming.
        
        Returns:
            Dict mapping codespace to display name, e.g. {"SKY": "Skyss (SKY)", "SOF": "Sogn og Fjordane (SOF)"}
        """
        query = """
        query {
          operators {
            id
            name
          }
        }
        """

        headers = {
            "Content-Type": "application/json",
            "ET-Client-Name": "homeassistant-entur-sx",
        }

        try:
            async with async_timeout.timeout(10):
                async with session.post(
                    API_GRAPHQL_URL,
                    json={"query": query},
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    all_operators = data.get("data", {}).get("operators", [])
                    
                    # Extract unique codespaces and find best names
                    codespace_names = {}
                    
                    for operator in all_operators:
                        op_id = operator.get("id", "")
                        op_name = operator.get("name", "")
                        
                        if not op_id:
                            continue
                        
                        # Extract codespace (first part before colon)
                        if ":" in op_id:
                            parts = op_id.split(":")
                            codespace = parts[0]
                            
                            # Only include 3-letter uppercase codespaces
                            if len(codespace) == 3 and codespace.isupper():
                                # Prefer canonical operator names (XXX:Operator:XXX)
                                is_canonical = (len(parts) == 3 and 
                                              parts[0] == parts[2] and 
                                              parts[1] == "Operator")
                                
                                if is_canonical or codespace not in codespace_names:
                                    # Use CODESPACE_NAMES if available, otherwise API name
                                    friendly_name = CODESPACE_NAMES.get(codespace, op_name)
                                    codespace_names[codespace] = friendly_name
                    
                    # Build final operator dict with display names
                    operators = {}
                    for codespace in sorted(codespace_names.keys()):
                        friendly_name = codespace_names[codespace]
                        display_name = f"{friendly_name} ({codespace})"
                        operators[codespace] = display_name
                    
                    _LOGGER.debug("Found %d operators from GraphQL API", len(operators))
                    return operators

        except Exception as err:
            _LOGGER.error("Error fetching operators from GraphQL: %s", err, exc_info=True)
            # Fallback to CODESPACE_NAMES constant
            _LOGGER.info("Falling back to CODESPACE_NAMES constant")
            operators = {}
            for codespace, friendly_name in sorted(CODESPACE_NAMES.items()):
                display_name = f"{friendly_name} ({codespace})"
                operators[codespace] = display_name
            return operators

    @staticmethod
    async def async_get_lines_for_operator(
        session: aiohttp.ClientSession, operator: str
    ) -> dict[str, str]:
        """Fetch list of lines for a specific operator (codespace) from Entur GraphQL API.
        
        Args:
            session: aiohttp session
            operator: Codespace (e.g., "SKY", "SOF")
            
        Returns:
            Dict mapping line ref to line name, e.g. {"SKY:Line:1": "Line 1 - Bergen sentrum"}
        """
        # Query all lines and filter by codespace
        # We can't use authority query since we only have the codespace now
        query = """
        query {
          lines {
            id
            name
            publicCode
            transportMode
            authority {
              id
            }
          }
        }
        """

        headers = {
            "Content-Type": "application/json",
            "ET-Client-Name": "homeassistant-entur-sx",
        }

        try:
            async with async_timeout.timeout(30):
                async with session.post(
                    API_GRAPHQL_URL,
                    json={"query": query},
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    lines = {}
                    all_lines = data.get("data", {}).get("lines", [])
                    
                    # Filter lines by codespace
                    for line in all_lines:
                        line_id = line.get("id", "")
                        
                        # Check if line belongs to this codespace
                        if not line_id.startswith(f"{operator}:"):
                            continue
                        
                        line_name = line.get("name", "")
                        public_code = line.get("publicCode", "")
                        transport_mode = line.get("transportMode", "")
                        
                        # Create a friendly display name
                        display_name = f"{public_code}"
                        if line_name:
                            display_name += f" - {line_name}"
                        if transport_mode:
                            display_name += f" ({transport_mode})"
                        
                        lines[line_id] = display_name

                    _LOGGER.debug("Found %d lines for codespace %s", len(lines), operator)
                    return lines

        except Exception as err:
            _LOGGER.error("Error fetching lines for codespace %s: %s", operator, err, exc_info=True)
            return {}
