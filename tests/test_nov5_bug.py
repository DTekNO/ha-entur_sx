"""Test for November 5th bug where future closed events were prioritized over active open events."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.entur_sx.api import EnturSXApiClient
from custom_components.entur_sx.const import STATUS_EXPIRED, STATUS_OPEN, STATUS_PLANNED


@pytest.mark.asyncio
async def test_nov5_skyss_line1_bug():
    """Test that active (open) disruptions are prioritized over future closed ones.

    This reproduces the bug from Nov 5, 2025 where:
    - A future event (Nov 15) with progress=closed was shown as the primary state
    - An active event (Nov 5 16:59 - Nov 6 02:23) with progress=open was ignored
    """
    # Mock API response simulating the Nov 5 situation
    mock_response = {
        "Siri": {
            "ServiceDelivery": {
                "SituationExchangeDelivery": [
                    {
                        "Situations": {
                            "PtSituationElement": [
                                # Future event with closed progress (bad API data)
                                {
                                    "Progress": "closed",
                                    "ValidityPeriod": [
                                        {
                                            "StartTime": "2025-11-15T15:15:00+01:00",
                                            "EndTime": "2025-11-05T18:51:54.301702294+01:00"  # Invalid: before start
                                        }
                                    ],
                                    "Summary": [{"value": "Nonneseter siste stopp til ca. kl. 17.30"}],
                                    "Description": [{"value": "Siste stopp er Nonneseter ca. kl. 15.30-17.30 pga. Lysfesten. "}],
                                    "Affects": {
                                        "Networks": {
                                            "AffectedNetwork": [
                                                {
                                                    "AffectedLine": [
                                                        {"LineRef": {"value": "SKY:Line:1"}}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                # Active/current event with open progress
                                {
                                    "Progress": "open",
                                    "ValidityPeriod": [
                                        {
                                            "StartTime": "2025-11-05T16:59:00+01:00",
                                            "EndTime": "2025-11-06T02:23:00+01:00"
                                        }
                                    ],
                                    "Summary": [{"value": "Forseinkingar etter driftsstans"}],
                                    "Description": [{"value": "Det er forseinkingar på linje 1 etter driftsstans mellom Bergen busstasjon og Florida."}],
                                    "Affects": {
                                        "Networks": {
                                            "AffectedNetwork": [
                                                {
                                                    "AffectedLine": [
                                                        {"LineRef": {"value": "SKY:Line:1"}}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                # Expired event 1
                                {
                                    "Progress": "closed",
                                    "ValidityPeriod": [
                                        {
                                            "StartTime": "2025-11-05T16:37:00+01:00",
                                            "EndTime": "2025-11-05T21:55:07.660824589+01:00"
                                        }
                                    ],
                                    "Summary": [{"value": "Omkøyring mellom sentrum og Kronstad"}],
                                    "Description": [{"value": "Linje 1 køyrer via Haukeland til/frå Bergen sentrum. Strekninga Kronstad–Bergen busstasjon stengd.Bruk perrong C og D på Bergen busstasjon, og E og F på Kronstad."}],
                                    "Affects": {
                                        "Networks": {
                                            "AffectedNetwork": [
                                                {
                                                    "AffectedLine": [
                                                        {"LineRef": {"value": "SKY:Line:1"}}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                # Expired event 2 (duplicate)
                                {
                                    "Progress": "closed",
                                    "ValidityPeriod": [
                                        {
                                            "StartTime": "2025-11-05T16:37:00+01:00",
                                            "EndTime": "2025-11-05T21:56:31.954671884+01:00"
                                        }
                                    ],
                                    "Summary": [{"value": "Omkøyring mellom sentrum og Kronstad"}],
                                    "Description": [{"value": "Linje 1 køyrer via Haukeland til/frå Bergen sentrum. Strekninga Kronstad–Bergen busstasjon stengd.Bruk perrong C og D på Bergen busstasjon, og E og F på Kronstad."}],
                                    "Affects": {
                                        "Networks": {
                                            "AffectedNetwork": [
                                                {
                                                    "AffectedLine": [
                                                        {"LineRef": {"value": "SKY:Line:1"}}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }

    # Create client
    client = EnturSXApiClient(operator="SKY")

    # Mock session
    mock_session = MagicMock()
    mock_response_obj = AsyncMock()
    mock_response_obj.raise_for_status = MagicMock()
    mock_response_obj.text = AsyncMock(return_value=json.dumps(mock_response))

    mock_session.get = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response_obj),
        __aexit__=AsyncMock()
    ))

    client.set_session(mock_session)

    # Mock datetime to Nov 6, 2025 at 00:00 (after the active event started, before it ended)
    with patch('custom_components.entur_sx.api.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 6, 0, 0, 0)
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Get deviations
        deviations = await client.async_get_deviations()

    # Verify we got data
    assert "SKY:Line:1" in deviations
    line_deviations = deviations["SKY:Line:1"]

    # Should have 4 deviations total
    assert len(line_deviations) == 4

    # Print for debugging
    print("\n=== Deviations sorted by priority ===")
    for i, dev in enumerate(line_deviations):
        print(f"{i}: {dev['status']:<10} | {dev['progress']:<6} | {dev['valid_from']} | {dev['summary']}")

    # The FIRST (index 0) should be the ACTIVE/OPEN one
    first = line_deviations[0]
    assert first["status"] == STATUS_OPEN, f"First deviation should be OPEN, got {first['status']}"
    assert first["summary"] == "Forseinkingar etter driftsstans"
    assert first["progress"] == "open"

    # The future event should be second (PLANNED status)
    second = line_deviations[1]
    assert second["status"] == STATUS_PLANNED, f"Second deviation should be PLANNED (future), got {second['status']}"
    assert second["summary"] == "Nonneseter siste stopp til ca. kl. 17.30"
    assert second["progress"] == "closed"

    # The rest should be EXPIRED
    for i in range(2, 4):
        assert line_deviations[i]["status"] == STATUS_EXPIRED
        assert line_deviations[i]["progress"] == "closed"

    print("\n✅ Test passed: Active disruptions are now prioritized correctly!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_nov5_skyss_line1_bug())

