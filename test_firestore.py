"""
Test script to diagnose Firestore transaction issues.
Run this locally to see what errors occur.
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from database.firebase import db
from fastapi import HTTPException

def test_basic_operations():
    """Test basic Firestore operations."""
    print("=" * 60)
    print("Testing Firestore Basic Operations")
    print("=" * 60)
    
    # Test 1: List collections
    print("\n1. Testing: List collections")
    try:
        collections = list(db.collections())
        print(f"   ✅ Success! Found {len(collections)} collections")
        for c in collections[:5]:
            print(f"      - {c.id}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        return False
    
    # Test 2: Read from rate_limits
    print("\n2. Testing: Read from rate_limits collection")
    try:
        docs = list(db.collection("rate_limits").limit(5).get())
        print(f"   ✅ Success! Found {len(docs)} documents")
        for doc in docs[:3]:
            print(f"      - {doc.id}: {doc.to_dict()}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        return False
    
    # Test 3: Simple write
    print("\n3. Testing: Simple write operation")
    try:
        test_ref = db.collection("rate_limits").document("_test_simple")
        test_ref.set({"test": True, "timestamp": datetime.now(timezone.utc)})
        print(f"   ✅ Success! Wrote test document")
        test_ref.delete()
        print(f"   ✅ Success! Deleted test document")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        return False
    
    # Test 4: Transaction (the actual problem)
    print("\n4. Testing: Transaction (this is what the limiter uses)")
    try:
        test_uid = "_test_user"
        test_feature = "_test_feature"
        rate_limit_ref = db.collection("rate_limits").document(f"{test_uid}_{test_feature}")
        
        def test_transaction(transaction):
            print("   → Inside transaction: Reading document...")
            doc = rate_limit_ref.get(transaction=transaction)
            print(f"   → Document exists: {doc.exists}")
            
            timestamps = []
            if doc.exists:
                data = doc.to_dict() or {}
                timestamps = data.get("timestamps", [])
                print(f"   → Found {len(timestamps)} existing timestamps")
            
            now = datetime.now(timezone.utc)
            timestamps.append(now)
            print(f"   → Writing {len(timestamps)} timestamps back...")
            transaction.set(rate_limit_ref, {"timestamps": timestamps})
            print(f"   → Transaction complete!")
            return len(timestamps)
        
        result = db.run_transaction(test_transaction)
        print(f"   ✅ Success! Transaction returned: {result}")
        
        # Cleanup
        rate_limit_ref.delete()
        print(f"   ✅ Cleaned up test document")
        
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_basic_operations()
    sys.exit(0 if success else 1)