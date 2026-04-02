"""
Simulation script for complex onboarding.
"""
import asyncio
from examples.complex_onboarding import onboarding_flow, Profile, Identity
from src.runtime import db, mcp

# Inject mock runtime globals into the generated module
import examples.complex_onboarding as ob
ob.db = db
ob.mcp = mcp

async def run_simulation():
    print("Starting AXON Simulation: Complex Onboarding")
    print("-" * 40)

    ident = {
        'fullName': 'John Doe',
        'idNumber': 'ABC-123',
        'country': 'USA'
    }

    inputs = {
        'userEmail': 'john@example.com',
        'age': 25,
        'ident': ident
    }

    try:
        profile = await onboarding_flow(inputs)
        print("\nSUCCESS!")
        print(f"Profile Created: {profile}")
        print(f"User in DB: {db['users'].data}")
    except Exception as e:
        print(f"\nFAULT: {e}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
