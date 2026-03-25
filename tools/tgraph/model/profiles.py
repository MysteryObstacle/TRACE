from __future__ import annotations

LOGICAL_V1 = "logical.v1"
TAAL_DEFAULT_V1 = "taal.default.v1"
SUPPORTED_PROFILES = {LOGICAL_V1, TAAL_DEFAULT_V1}


def is_supported_profile(profile: str) -> bool:
    return profile in SUPPORTED_PROFILES


def require_supported_profile(profile: str) -> str:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported_profile:{profile}")
    return profile
