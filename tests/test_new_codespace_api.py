"""Test the new codespace-based API."""
import asyncio
import sys
sys.path.append("c:\\Users\\jeco\\Dev\\HA\\entur_situation_exchange_custom_integration\\custom_components\\entur_sx")

from api import EnturSXApiClient
import aiohttp


async def test_new_codespace_api():
    """Test the new codespace-based operators and lines."""
    
    async with aiohttp.ClientSession() as session:
        print("=" * 100)
        print("TEST 1: Get operators (codespaces with active SX data)")
        print("=" * 100)
        
        operators = await EnturSXApiClient.async_get_operators(session)
        
        print(f"\nFound {len(operators)} operators:")
        for codespace, display_name in sorted(operators.items()):
            print(f"  {codespace}: {display_name}")
        
        # Test specific codespaces
        print(f"\n\n{'=' * 100}")
        print("TEST 2: Get lines for specific codespaces")
        print('=' * 100)
        
        test_codespaces = ["SKY", "SOF", "RUT"]
        
        for codespace in test_codespaces:
            if codespace in operators:
                print(f"\n\nCodespace: {codespace} ({operators[codespace]})")
                print("-" * 80)
                
                lines = await EnturSXApiClient.async_get_lines_for_operator(session, codespace)
                
                print(f"Found {len(lines)} lines")
                
                if lines:
                    print(f"\nFirst 10 lines:")
                    for i, (line_id, line_name) in enumerate(sorted(lines.items())[:10]):
                        print(f"  {line_id}: {line_name}")
        
        # Test API client initialization
        print(f"\n\n{'=' * 100}")
        print("TEST 3: Initialize API client with codespace")
        print('=' * 100)
        
        client = EnturSXApiClient(operator="SKY")
        client.set_session(session)
        
        print(f"\nClient initialized:")
        print(f"  Operator: {client._operator}")
        print(f"  Operator code: {client._operator_code}")
        print(f"  Service URL: {client._service_url}")
        
        print(f"\n✅ Expected URL: https://api.entur.io/realtime/v1/rest/sx?datasetId=SKY")
        print(f"✅ Actual URL:   {client._service_url}")


if __name__ == "__main__":
    asyncio.run(test_new_codespace_api())
