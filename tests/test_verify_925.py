"""Verify we capture both deviations for line 925 as shown on skyss.no."""
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


async def verify_line_925_deviations():
    """Verify we get both deviations for line 925."""
    print("="*80)
    print("VERIFICATION: Line 925 Deviations (skyss.no shows 2)")
    print("="*80)
    
    async with aiohttp.ClientSession() as session:
        # Test with API client
        print("\n\nUsing EnturSXApiClient:")
        print("-" * 60)
        
        api_client = EnturSXApiClient(
            operator="SKY:Authority:SKY"
        )
        api_client.set_session(session)
        
        deviations = await api_client.async_get_deviations()
        
        line_925_devs = deviations.get("SKY:Line:925", [])
        print(f"API Client found: {len(line_925_devs)} deviation(s)")
        
        for i, dev in enumerate(line_925_devs, 1):
            print(f"\n  Deviation {i}:")
            print(f"    Status: {dev.get('status')}")
            print(f"    Valid from: {dev.get('valid_from')}")
            print(f"    Valid to: {dev.get('valid_to')}")
            print(f"    Summary: {dev.get('summary', '')[:100]}...")
        
        # Now check raw API
        print("\n\n" + "="*80)
        print("Raw API Check:")
        print("-" * 60)
        
        sx_url = "https://api.entur.io/realtime/v1/rest/sx?datasetId=SKY"
        headers = {"Content-Type": "application/json"}
        
        async with session.get(sx_url, headers=headers) as response:
            text = await response.text()
            import json
            data = json.loads(text)
            
            # Navigate to situations
            siri = data.get("Siri", {})
            service_delivery = siri.get("ServiceDelivery", {})
            sx_deliveries = service_delivery.get("SituationExchangeDelivery", [])
            
            line_925_situations = []
            
            for sx_delivery in sx_deliveries:
                situations = sx_delivery.get("Situations", {})
                elements = situations.get("PtSituationElement", [])
                
                for element in elements:
                    # Check if this affects line 925
                    affects = element.get("Affects", {})
                    networks = affects.get("Networks")
                    
                    if not networks:
                        continue
                    
                    # Check all affected lines
                    affected_networks = networks.get("AffectedNetwork", [])
                    for network in affected_networks:
                        lines = network.get("AffectedLine", [])
                        for line in lines:
                            line_ref_obj = line.get("LineRef", {})
                            line_ref = line_ref_obj.get("value", "")
                            
                            if line_ref == "SKY:Line:925":
                                situation_number = element.get("SituationNumber", {}).get("value", "N/A")
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
                                break  # Found this line, no need to check more lines in this network
            
            print(f"Raw API found: {len(line_925_situations)} situation(s) for SKY:Line:925")
            
            for i, sit in enumerate(line_925_situations, 1):
                print(f"\n  Situation {i}:")
                print(f"    Number: {sit['situation_number']}")
                print(f"    Progress: {sit['progress']}")
                print(f"    Start: {sit['start']}")
                print(f"    End: {sit['end']}")
                print(f"    Summary: {sit['summary'][:100]}...")
        
        print("\n" + "="*80)
        print("VERIFICATION RESULT:")
        print("="*80)
        
        if len(line_925_devs) == 2 and len(line_925_situations) == 2:
            print("✅ SUCCESS - Both API client and raw API found 2 deviations!")
            print("   Matches skyss.no report of 2 deviations.")
        elif len(line_925_devs) == len(line_925_situations):
            print(f"⚠️  PARTIAL - Found {len(line_925_devs)} deviation(s) (skyss.no shows 2)")
            print("   API client and raw parsing agree, but count may be different.")
        else:
            print(f"❌ MISMATCH - API client: {len(line_925_devs)}, Raw API: {len(line_925_situations)}")
            print("   There's a parsing issue in the API client!")
        
        print(f"\n   Expected: 2 deviations (per skyss.no)")
        print(f"   API Client: {len(line_925_devs)} deviation(s)")
        print(f"   Raw API: {len(line_925_situations)} situation(s)")


if __name__ == "__main__":
    asyncio.run(verify_line_925_deviations())
