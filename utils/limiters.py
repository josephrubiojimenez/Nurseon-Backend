import logging
from fastapi import HTTPException
from database.firebase import db

logger = logging.getLogger("feature_limiters")

USE_FALLBACK_AFTER_FAILURES = 2

_consecutive_failures = 0
_fallback_enabled = False


def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    global _consecutive_failures
    global _fallback_enabled

    try:

        from utils.limiters_simple import enforce_feature_limit_simple

        remaining = enforce_feature_limit_simple(
            uid,
            feature_name,
            max_limit,
        )

        _consecutive_failures = 0

        return remaining

    except HTTPException:
        raise

    except Exception as e:

        _consecutive_failures += 1

        logger.exception(
            "Primary limiter failed: %s",
            str(e),
        )

        if _consecutive_failures >= USE_FALLBACK_AFTER_FAILURES:

            if not _fallback_enabled:
                logger.warning(
                    "Switching to fallback rate limiter."
                )
                _fallback_enabled = True

            try:

                from utils.limiters_fallback import (
                    enforce_feature_limit_fallback,
                )

                return enforce_feature_limit_fallback(
                    uid,
                    feature_name,
                    max_limit,
                )

            except Exception:

                logger.exception(
                    "Fallback limiter also failed."
                )

        logger.warning(
            "All limiters failed. Allowing request."
        )

        return max_limit


def check_rate_limit_status(
    uid: str,
    feature_name: str,
    max_limit: int,
) -> dict:
    
    try:

        from utils.limiters_simple import (
            check_rate_limit_status_simple,
        )

        return check_rate_limit_status_simple(
            uid,
            feature_name,
            max_limit,
        )

    except Exception:

        logger.exception(
            "Failed to check rate limit status."
        )

        return {
            "available": True,
            "remaining": max_limit,
            "used": 0,
            "reset_at": None,
        }