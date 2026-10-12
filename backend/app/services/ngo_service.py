"""
NGO Profile Service.
"""

from typing import Any, Dict, Optional, Tuple
from ..extensions import db
from ..models import NGO, User
from ..utils.validation import (
    NGO_MUTABLE_FIELDS,
    NGO_PROTECTED_FIELDS,
    check_unexpected_or_protected_fields,
)


class NGOService:
    @staticmethod
    def serialize_ngo(ngo: NGO) -> Dict[str, Any]:
        return {
            "ngo_id": ngo.ngo_id,
            "name": ngo.name,
            "description": ngo.description,
            "location": ngo.location,
            "contact": ngo.contact,
            "verification_status": ngo.verification_status,
        }

    @staticmethod
    def create_ngo(user: User, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Creates an NGO profile for the given user.
        Returns: (data, error_response_dict, status_code)
        """
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        # Check if user already owns an NGO
        if user.ngo is not None:
            return None, {"status": "error", "message": "An NGO profile already exists for this user."}, 409

        # Check protected/unknown fields
        field_error = check_unexpected_or_protected_fields(payload, NGO_MUTABLE_FIELDS, NGO_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        details = {}

        # name is required
        if "name" not in payload:
            details["name"] = "Name is required."
        else:
            name_val = payload["name"]
            if not isinstance(name_val, str) or not name_val.strip():
                details["name"] = "Name must be a non-empty string."
            elif len(name_val) > 255:
                details["name"] = "Name must not exceed 255 characters."

        # Optional fields validation
        if "description" in payload:
            desc_val = payload["description"]
            if desc_val is not None:
                if not isinstance(desc_val, str):
                    details["description"] = "Description must be a string."
                elif len(desc_val) > 2000:
                    details["description"] = "Description must not exceed 2000 characters."

        if "location" in payload:
            loc_val = payload["location"]
            if loc_val is not None:
                if not isinstance(loc_val, str):
                    details["location"] = "Location must be a string."
                elif len(loc_val) > 255:
                    details["location"] = "Location must not exceed 255 characters."

        if "contact" in payload:
            contact_val = payload["contact"]
            if contact_val is not None:
                if not isinstance(contact_val, str):
                    details["contact"] = "Contact must be a string."
                elif len(contact_val) > 255:
                    details["contact"] = "Contact must not exceed 255 characters."

        if details:
            return None, {
                "status": "error",
                "message": "Validation failed.",
                "details": details,
            }, 400

        ngo = NGO(
            user_id=user.user_id,
            name=payload["name"].strip(),
            description=payload.get("description").strip() if isinstance(payload.get("description"), str) else payload.get("description"),
            location=payload.get("location").strip() if isinstance(payload.get("location"), str) else payload.get("location"),
            contact=payload.get("contact").strip() if isinstance(payload.get("contact"), str) else payload.get("contact"),
            verification_status="Unverified",
        )
        db.session.add(ngo)
        db.session.commit()

        return NGOService.serialize_ngo(ngo), None, 201

    @staticmethod
    def update_ngo(ngo: NGO, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Updates an NGO profile.
        Returns: (data, error_response_dict, status_code)
        """
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        field_error = check_unexpected_or_protected_fields(payload, NGO_MUTABLE_FIELDS, NGO_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        provided_fields = [k for k in payload.keys() if k in NGO_MUTABLE_FIELDS]
        if not provided_fields:
            return None, {"status": "error", "message": "At least one mutable field is required."}, 400

        details = {}

        if "name" in payload:
            name_val = payload["name"]
            if not isinstance(name_val, str) or not name_val.strip():
                details["name"] = "Name must be a non-empty string."
            elif len(name_val) > 255:
                details["name"] = "Name must not exceed 255 characters."

        if "description" in payload:
            desc_val = payload["description"]
            if desc_val is not None:
                if not isinstance(desc_val, str):
                    details["description"] = "Description must be a string."
                elif len(desc_val) > 2000:
                    details["description"] = "Description must not exceed 2000 characters."

        if "location" in payload:
            loc_val = payload["location"]
            if loc_val is not None:
                if not isinstance(loc_val, str):
                    details["location"] = "Location must be a string."
                elif len(loc_val) > 255:
                    details["location"] = "Location must not exceed 255 characters."

        if "contact" in payload:
            contact_val = payload["contact"]
            if contact_val is not None:
                if not isinstance(contact_val, str):
                    details["contact"] = "Contact must be a string."
                elif len(contact_val) > 255:
                    details["contact"] = "Contact must not exceed 255 characters."

        if details:
            return None, {
                "status": "error",
                "message": "Validation failed.",
                "details": details,
            }, 400

        if "name" in payload:
            ngo.name = payload["name"].strip()
        if "description" in payload:
            ngo.description = payload["description"].strip() if isinstance(payload["description"], str) else payload["description"]
        if "location" in payload:
            ngo.location = payload["location"].strip() if isinstance(payload["location"], str) else payload["location"]
        if "contact" in payload:
            ngo.contact = payload["contact"].strip() if isinstance(payload["contact"], str) else payload["contact"]

        db.session.commit()

        return NGOService.serialize_ngo(ngo), None, 200
