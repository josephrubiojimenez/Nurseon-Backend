"""
Firebase connection health check and diagnostics.
"""
import logging
from datetime import datetime, timezone
from database.firebase import db

logger = logging.getLogger("firebase_health")

def check_firebase_connection() -> dict:
    """
    Check if Firebase Firestore is accessible and working.
    Returns a diagnostic report.
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connected": False,
        "can_read": False,
        "can_write": False,
        "error": None,
        "details": {}
    }
    
    try:
        # Test 1: Basic connection - try to list collections
        logger.info("Testing Firebase connection...")
        collections = list(db.collections())
        result["connected"] = True
        result["details"]["collections_count"] = len(collections)
        result["details"]["collections"] = [c.id for c in collections[:10]]  # First 10
        
        # Test 2: Try to read from rate_limits collection
        logger.info("Testing read access to rate_limits...")
        test_doc = db.collection("rate_limits").limit(1).get()
        result["can_read"] = True
        result["details"]["rate_limits_readable"] = True
        
        # Test 3: Try a test write (create and immediately delete)
        logger.info("Testing write access to rate_limits...")
        test_ref = db.collection("rate_limits").document("_health_check_test")
        test_ref.set({
            "test": True,
            "timestamp": datetime.now(timezone.utc),
            "timestamps": [datetime.now(timezone.utc)]
        })
        test_ref.delete()
        result["can_write"] = True
        result["details"]["rate_limits_writable"] = True
        
        logger.info("✅ Firebase connection healthy")
        
    except Exception as e:
        error_msg = str(e)
        result["error"] = error_msg
        logger.error(f"❌ Firebase connection failed: {error_msg}", exc_info=True)
        
        # Categorize the error
        if "permission" in error_msg.lower() or "denied" in error_msg.lower():
            result["details"]["error_type"] = "permission_denied"
            result["details"]["suggestion"] = "Check Firestore security rules and service account permissions"
        elif "not found" in error_msg.lower() or "missing" in error_msg.lower():
            result["details"]["error_type"] = "not_found"
            result["details"]["suggestion"] = "Check Firebase project ID and database URL"
        elif "timeout" in error_msg.lower() or "unavailable" in error_msg.lower():
            result["details"]["error_type"] = "network_error"
            result["details"]["suggestion"] = "Check network connectivity and Firebase status"
        elif "credential" in error_msg.lower() or "auth" in error_msg.lower():
            result["details"]["error_type"] = "authentication_error"
            result["details"]["suggestion"] = "Check service account key file"
        else:
            result["details"]["error_type"] = "unknown"
            result["details"]["suggestion"] = "Check Firebase console for more details"
    
    return result


def log_firebase_status():
    """
    Log Firebase connection status on startup.
    Call this in your app startup to verify Firebase is working.
    """
    logger.info("=" * 60)
    logger.info("Firebase Connection Diagnostic")
    logger.info("=" * 60)
    
    result = check_firebase_connection()
    
    logger.info(f"Timestamp: {result['timestamp']}")
    logger.info(f"Connected: {result['connected']}")
    logger.info(f"Can Read: {result['can_read']}")
    logger.info(f"Can Write: {result['can_write']}")
    
    if result['error']:
        logger.error(f"Error: {result['error']}")
        if 'details' in result and 'suggestion' in result['details']:
            logger.error(f"Suggestion: {result['details']['suggestion']}")
    else:
        logger.info("✅ All Firebase checks passed")
    
    logger.info("=" * 60)
    
    return result