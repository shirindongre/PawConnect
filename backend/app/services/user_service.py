"""
User Profile Service.
"""

from typing import Any, Dict, Optional, Tuple
from ..extensions import db
from ..models import User
from ..utils.validation import (
    USER_MUTABLE_FIELDS,
    USER_PROTECTED_FIELDS,
    check_unexpected_or_protected_fields,
)


class UserService:
    @staticmethod
    def serialize_user(user: User) -> Dict[str, Any]:
        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "location": user.location,
            "role": user.role.role_name if user.role else None,
        }

    @staticmethod
    def update_user_profile(user: User, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Validates and updates user profile fields.
        Returns: (data, error_response_dict, status_code)
        """
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        # Check protected/unknown fields
        field_error = check_unexpected_or_protected_fields(payload, USER_MUTABLE_FIELDS, USER_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        # Must contain at least one mutable field
        provided_fields = [k for k in payload.keys() if k in USER_MUTABLE_FIELDS]
        if not provided_fields:
            return None, {"status": "error", "message": "At least one mutable field is required."}, 400

        details = {}

        if "name" in payload:
            name_val = payload["name"]
            if not isinstance(name_val, str) or not name_val.strip():
                details["name"] = "Name must be a non-empty string."
            elif len(name_val) > 100:
                details["name"] = "Name must not exceed 100 characters."

        if "phone" in payload:
            phone_val = payload["phone"]
            if phone_val is not None:
                if not isinstance(phone_val, str):
                    details["phone"] = "Phone must be a string."
                elif len(phone_val) > 20:
                    details["phone"] = "Phone must not exceed 20 characters."

        if "location" in payload:
            loc_val = payload["location"]
            if loc_val is not None:
                if not isinstance(loc_val, str):
                    details["location"] = "Location must be a string."
                elif len(loc_val) > 255:
                    details["location"] = "Location must not exceed 255 characters."

        if details:
            return None, {
                "status": "error",
                "message": "Validation failed.",
                "details": details,
            }, 400

        # Apply updates
        if "name" in payload:
            user.name = payload["name"].strip()
        if "phone" in payload:
            user.phone = payload["phone"].strip() if isinstance(payload["phone"], str) else payload["phone"]
        if "location" in payload:
            user.location = payload["location"].strip() if isinstance(payload["location"], str) else payload["location"]

        db.session.commit()

        return UserService.serialize_user(user), None, 200
