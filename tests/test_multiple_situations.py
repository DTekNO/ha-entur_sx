"""Test how multiple situations are handled for a single line."""
import asyncio
import aiohttp
import sys
import os

# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(__file__))

# Add the custom_components directory to the path
custom_components_path = os.path.join(parent_dir, 'custom_components')
sys.path.insert(0, custom_components_path)

import importlib.util

# Load const.py
const_path = os.path.join(parent_dir, 'custom_components', 'entur_sx', 'const.py')
spec = importlib.util.spec_from_file_location("entur_sx.const", const_path)
const_module = importlib.util.module_from_spec(spec)
sys.modules['entur_sx.const'] = const_module
spec.loader.exec_module(const_module)

# Load api.py
api_path = os.path.join(parent_dir, 'custom_components', 'entur_sx', 'api.py')
spec = importlib.util.spec_from_file_location("entur_sx.api", api_path)
api_module = importlib.util.module_from_spec(spec)
sys.modules['entur_sx.api'] = api_module
spec.loader.exec_module(api_module)

EnturSXApiClient = api_module.EnturSXApiClient


async def test_multiple_situations():
    """Test how multiple situations for a single line are handled."""
    print("="*80)
    print("TESTING MULTIPLE SITUATIONS FOR SKY:Line:925")
    print("="*80)
    
    # Test with the actual API client
    print("\n\nTEST 1: Using EnturSXApiClient to fetch deviations")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        # Create API client for SKY operator with line 925
        api_client = EnturSXApiClient(
            operator="SKY:Authority:SKY"
        )
        api_client.set_session(session)
        
        print(f"API URL: {api_client._service_url}")
        
        deviations = await api_client.async_get_deviations()
        
        print(f"\nTotal lines with deviations: {len(deviations)}")
        
        for line_id, line_deviations in deviations.items():
            print(f"\n{line_id}: {len(line_deviations)} deviation(s)")
            for i, dev in enumerate(line_deviations, 1):
                print(f"\n  Deviation {i}:")
                print(f"    Status: {dev.get('status', 'N/A')}")
                print(f"    Valid from: {dev.get('valid_from', 'N/A')}")
                print(f"    Valid to: {dev.get('valid_to', 'N/A')}")
                print(f"    Summary: {dev.get('summary', 'N/A')[:100]}...")
                if dev.get('description'):
                    print(f"    Description: {dev.get('description', 'N/A')[:100]}...")
        
        # Test 2: Fetch RAW data from SX API
        print("\n\n" + "="*80)
        print("TEST 2: Fetching RAW SX API data for SKY operator")
        print("-" * 60)
        
        sx_url = "https://api.entur.io/realtime/v1/rest/sx?datasetId=SKY"
        headers = {"Content-Type": "application/json"}
        
        async with session.get(sx_url, headers=headers) as response:
            print(f"Response status: {response.status}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            
            try:
                text = await response.text()
                import json
                data = json.loads(text)
                
                # Navigate to situations
                siri = data.get("Siri", {})
                service_delivery = siri.get("ServiceDelivery", {})
                sx_deliveries = service_delivery.get("SituationExchangeDelivery", [])
                
                print(f"Number of SX deliveries: {len(sx_deliveries)}")
                
                line_925_situations = []
                total_situations = 0
                
                for sx_delivery in sx_deliveries:
                    situations = sx_delivery.get("Situations", {})
                    elements = situations.get("PtSituationElement", [])
                    total_situations += len(elements)
                    
                    for element in elements:
                        # Check if this affects line 925
                        affects = element.get("Affects", {})
                        networks = affects.get("Networks")
                        
                        if not networks:
                            continue
                        
                        # Check each affected line
                        affected_networks = networks.get("AffectedNetwork", [])
                        for network in affected_networks:
                            lines = network.get("AffectedLine", [])
                            for line in lines:
                                line_ref_obj = line.get("LineRef", {})
                                line_ref = line_ref_obj.get("value", "")
                                
                                if "925" in line_ref:
                                    situation_number = element.get("SituationNumber", "N/A")
                                    summaries = element.get("Summary", [])
                                    summary = summaries[0].get("value", "N/A") if summaries else "N/A"
                                    progress = element.get("Progress", "N/A")
                                    validity = element.get("ValidityPeriod", [{}])[0] if element.get("ValidityPeriod") else {}
                                    
                                    line_925_situations.append({
                                        "situation_number": situation_number,
                                        "line_ref": line_ref,
                                        "summary": summary,
                                        "progress": progress,
                                        "start": validity.get("StartTime", "N/A"),
                                        "end": validity.get("EndTime", "N/A")
                                    })
                
                print(f"Total situations in API: {total_situations}")
                print(f"\nFound {len(line_925_situations)} situation(s) affecting line 925 in raw API data:")
                for i, sit in enumerate(line_925_situations, 1):
                    print(f"\n  Situation {i}:")
                    print(f"    Number: {sit['situation_number']}")
                    print(f"    Line Ref: {sit['line_ref']}")
                    print(f"    Progress: {sit['progress']}")
                    print(f"    Start: {sit['start']}")
                    print(f"    End: {sit['end']}")
                    print(f"    Summary: {sit['summary'][:100]}...")
                
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                text = await response.text()
                print(f"Response text (first 500 chars): {text[:500]}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\n📊 ANALYSIS:")
    print("- Check if the API client returns all situations from the raw data")
    print("- If counts don't match, there's a parsing issue in _parse_response()")


if __name__ == "__main__":
    asyncio.run(test_multiple_situations())
