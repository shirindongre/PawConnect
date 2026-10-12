"""
REST API Validation Utilities for PawConnect (Batch 1).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

# Canonical enum values
VALID_GENDERS: Set[str] = {"Male", "Female", "Other"}
VALID_ANIMAL_STATUSES: Set[str] = {"Available", "Adopted", "Under Treatment", "Foster"}

# User constraints
USER_MUTABLE_FIELDS = {"name", "phone", "location"}
USER_PROTECTED_FIELDS = {"user_id", "email", "role_id", "auth_id", "created_at"}

# NGO constraints
NGO_MUTABLE_FIELDS = {"name", "description", "location", "contact"}
NGO_PROTECTED_FIELDS = {"ngo_id", "user_id", "verification_status"}

# Animal constraints
ANIMAL_MUTABLE_FIELDS = {
    "name",
    "species",
    "breed",
    "age",
    "gender",
    "description",
    "location",
    "status",
    "image_url",
}
ANIMAL_PROTECTED_FIELDS = {"animal_id", "ngo_id", "created_at"}


def check_unexpected_or_protected_fields(
    payload: Dict[str, Any],
    allowed_mutable: Set[str],
    protected_fields: Set[str],
) -> Optional[str]:
    """
    Check if payload contains unexpected or protected fields.
    Returns error message if any found, else None.
    """
    payload_keys = set(payload.keys())
    
    # Check for explicitly protected fields
    found_protected = payload_keys.intersection(protected_fields)
    if found_protected:
        sorted_keys = ", ".join(sorted(found_protected))
        return f"Unknown or protected fields: {sorted_keys}"

    # Check for any unexpected fields not in allowed_mutable
    unexpected = payload_keys - allowed_mutable
    if unexpected:
        sorted_keys = ", ".join(sorted(unexpected))
        return f"Unknown or protected fields: {sorted_keys}"

    return None

# Rescue Case constraints
# Canonical status strings (must match docs/API.md §5.3)
VALID_RESCUE_STATUSES: set[str] = {
    "Reported",
    "Under Review",
    "NGO Assigned",
    "Rescued",
    "Under Treatment / Foster",
    "Adoption Available",
    "Adopted / Resolved",
}

# Urgency levels
VALID_URGENCY_LEVELS: set[str] = {"Low", "Medium", "High", "Critical"}

# Mutable and protected fields for RescueCase API
RESCUE_MUTABLE_FIELDS = {
    "animal_type",
    "condition",
    "location",
    "description",
    "urgency",
    "image_url",
}
RESCUE_PROTECTED_FIELDS = {
    "case_id",
    "reported_by",
    "assigned_ngo",
    "status",
    "created_at",
    "updated_at",
}
