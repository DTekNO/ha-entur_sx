"""API client for Entur Situation Exchange."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any

import aiohttp
import async_timeout

from .const import API_BASE_URL, API_GRAPHQL_URL, CODESPACE_NAMES, STATE_NORMAL, STATUS_EXPIRED, STATUS_PLANNED, STATUS_OPEN

_LOGGER = logging.getLogger(__name__)


class RateLimitTracker:
    """Track API rate limits from response headers."""
    
    def __init__(self):
        """Initialize rate limit tracker."""
        self.allowed: int = 5  # Default: 5 requests per 5-minute rolling window
        self.available: int = 5
        self.used: int = 0
        self.expiry_time: str | None = None
        self.last_request_time: float = 0.0
        self.min_interval_ms: int = 100  # Spike arrest: 1 req per 100ms
        
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
            
        # Log when getting close to limit
        if self.available <= 1:
            _LOGGER.warning(
                "Rate limit nearly exhausted: %d/%d requests remaining until %s",
                self.available,
                self.allowed,
                self.expiry_time
            )
        elif self.available <= 2:
            _LOGGER.info(
                "Rate limit info: %d/%d requests remaining until %s",
                self.available,
                self.allowed,
                self.expiry_time
            )
    
    async def wait_if_needed(self, delay_ms: int = 200) -> None:
        """Wait if necessary to respect spike arrest limits.
        
        Args:
            delay_ms: Minimum milliseconds between requests (default 200ms for safety margin)
        """
        if self.last_request_time > 0:
            elapsed_ms = (time.time() - self.last_request_time) * 1000
            if elapsed_ms < delay_ms:
                wait_ms = delay_ms - elapsed_ms
                _LOGGER.debug("Rate limit: waiting %.0fms before next request", wait_ms)
                await asyncio.sleep(wait_ms / 1000)
        
        self.last_request_time = time.time()
    
    def can_make_request(self) -> bool:
        """Check if we have quota available.
        
        Returns:
            True if we can safely make a request
        """
        return self.available > 0


class EnturSXApiClient:
    """API client for Entur Situation Exchange."""

    def __init__(
        self,
        operator: str | None = None,
        lines: list[str] | None = None,
        lang: str = "no",
    ) -> None:
        """Initialize the API client.
        
        Args:
            operator: Codespace (e.g., "SKY", "SOF")
            lines: List of line IDs to monitor
            lang: Preferred language code ("no" or "en")
        """
        self._operator = operator
        self._lines = lines or []
        self._lang = lang
        self._session: aiohttp.ClientSession | None = None
        self._rate_limiter = RateLimitTracker()

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
        Respects rate limits from API headers (5 req per 5-min rolling window, 200ms between requests).
        
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
            async with async_timeout.timeout(30):
                while page_count < max_pages:
                    # Check rate limit quota before making request (but not for first page)
                    # First page always attempts - we need fresh rate limit info from response
                    if page_count > 0 and not self._rate_limiter.can_make_request():
                        _LOGGER.warning(
                            "Rate limit quota exhausted (%d/%d available). Stopping pagination at page %d.",
                            self._rate_limiter.available,
                            self._rate_limiter.allowed,
                            page_count
                        )
                        break
                    
                    # Wait to respect spike arrest (200ms between requests)
                    # Skip delay before first request in this polling cycle
                    if page_count > 0:
                        await self._rate_limiter.wait_if_needed(delay_ms=200)
                    
                    page_count += 1
                    
                    # Add requestorId parameter for pagination
                    url = f"{self._service_url}&requestorId={requestor_id}" if "?" in self._service_url else f"{self._service_url}?requestorId={requestor_id}"
                    
                    async with self._session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        
                        # Update rate limit tracking from response headers
                        self._rate_limiter.update_from_headers(response.headers)
                        
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
                            
                            _LOGGER.debug(
                                "Retrieved page %d: %d situations (total so far: %d). Rate limit: %d/%d remaining",
                                page_count,
                                len(situations),
                                len(all_situations),
                                self._rate_limiter.available,
                                self._rate_limiter.allowed
                            )

                        # Check for MoreData flag
                        more_data = service_delivery.get("MoreData", False)
                        
                        if more_data:
                            _LOGGER.info(
                                "MoreData=true, fetching next page (page %d, %d situations retrieved so far). Operator: %s. Rate limit: %d/%d",
                                page_count,
                                len(all_situations),
                                self._operator_code or "all",
                                self._rate_limiter.available,
                                self._rate_limiter.allowed
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
