"""
Rescue Case Service – Batch 2A implementation.
Provides business‑logic operations for the RescueCase model, mirroring the
behaviour described in `docs/API.md`.
"""

from typing import Any, Dict, Optional, Tuple, List
from flask import g
from ..extensions import db
from ..models.rescue_case import RescueCase
from ..utils.validation import (
    RESCUE_MUTABLE_FIELDS,
    RESCUE_PROTECTED_FIELDS,
    VALID_RESCUE_STATUSES,
    VALID_URGENCY_LEVELS,
    check_unexpected_or_protected_fields,
)


class RescueCaseService:
    @staticmethod
    def serialize_case(case: RescueCase) -> Dict[str, Any]:
        """Return a JSON‑serialisable representation of a RescueCase."""
        return {
            "case_id": case.case_id,
            "reported_by": case.reported_by,
            "assigned_ngo": case.assigned_ngo,
            "animal_type": case.animal_type,
            "condition": case.condition,
            "location": case.location,
            "description": case.description,
            "urgency": case.urgency,
            "image_url": case.image_url,
            "status": case.status,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        }

    # ---------------------------------------------------------------------
    # Creation
    # ---------------------------------------------------------------------
    @staticmethod
    def create_case(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """Create a new rescue case.
        The caller must be a Cognito‑authenticated user (enforced by the route).
        """
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        # Reject protected/unknown fields
        field_error = check_unexpected_or_protected_fields(payload, RESCUE_MUTABLE_FIELDS, RESCUE_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        # Validate required fields (location is mandatory)
        details: Dict[str, str] = {}
        if "location" not in payload or not isinstance(payload["location"], str) or not payload["location"].strip():
            details["location"] = "Location is required and must be a non‑empty string."
        else:
            if len(payload["location"]) > 255:
                details["location"] = "Location must not exceed 255 characters."

        # Optional fields validation (lengths, enums)
        if "animal_type" in payload:
            val = payload["animal_type"]
            if val is not None and (not isinstance(val, str) or len(val) > 100):
                details["animal_type"] = "Animal type must be a string up to 100 characters."
        if "condition" in payload:
            val = payload["condition"]
            if val is not None and (not isinstance(val, str) or len(val) > 2000):
                details["condition"] = "Condition must be a string up to 2000 characters."
        if "description" in payload:
            val = payload["description"]
            if val is not None and (not isinstance(val, str) or len(val) > 2000):
                details["description"] = "Description must be a string up to 2000 characters."
        if "urgency" in payload:
            val = payload["urgency"]
            if val is not None:
                if not isinstance(val, str) or val not in VALID_URGENCY_LEVELS:
                    details["urgency"] = f"Urgency must be one of: {', '.join(sorted(VALID_URGENCY_LEVELS))}."
        if "image_url" in payload:
            val = payload["image_url"]
            if val is not None:
                if not isinstance(val, str) or len(val) > 2048:
                    details["image_url"] = "Image URL must be a string up to 2048 characters."
                # Basic absolute URL check (http/https)
                if isinstance(val, str) and not (val.startswith("http://") or val.startswith("https://")):
                    details["image_url"] = "Image URL must be an absolute HTTP/HTTPS URL."

        if details:
            return None, {"status": "error", "message": "Validation failed.", "details": details}, 400

        # Build model instance – server‑managed fields are set automatically
        case = RescueCase(
            reported_by=g.current_user.user_id,
            assigned_ngo=None,
            location=payload["location"].strip(),
            animal_type=payload.get("animal_type").strip() if isinstance(payload.get("animal_type"), str) else payload.get("animal_type"),
            condition=payload.get("condition").strip() if isinstance(payload.get("condition"), str) else payload.get("condition"),
            description=payload.get("description").strip() if isinstance(payload.get("description"), str) else payload.get("description"),
            urgency=payload.get("urgency"),
            image_url=payload.get("image_url").strip() if isinstance(payload.get("image_url"), str) else payload.get("image_url"),
        )
        db.session.add(case)
        db.session.commit()
        return RescueCaseService.serialize_case(case), None, 201

    # ---------------------------------------------------------------------
    # Listing – respects visibility rules defined in the contract.
    # ---------------------------------------------------------------------
    @staticmethod
    def list_cases(page_raw: Any, per_page_raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        try:
            page = int(page_raw) if page_raw is not None else 1
            per_page = int(per_page_raw) if per_page_raw is not None else 20
        except (ValueError, TypeError):
            return None, {"status": "error", "message": "Invalid pagination parameters."}, 400
        if page < 1:
            return None, {"status": "error", "message": "Page must be >= 1."}, 400
        if per_page < 1 or per_page > 100:
            return None, {"status": "error", "message": "per_page must be between 1 and 100."}, 400

        user = g.current_user
        role = user.role.role_name if user.role else None

        query = RescueCase.query
        # Apply visibility filters
        if role == "NGO":
            # Must have an NGO profile – route validator already ensures it.
            ngo_id = user.ngo.ngo_id if getattr(user, "ngo", None) else None
            if ngo_id is None:
                return None, {"status": "error", "message": "No NGO profile found for this user."}, 404
            # Unassigned + own assigned
            query = query.filter(
                (RescueCase.assigned_ngo == None) | (RescueCase.assigned_ngo == ngo_id)  # noqa: E711
            )
        else:
            # Regular users see only their own reported cases
            query = query.filter(RescueCase.reported_by == user.user_id)

        total = query.count()
        items = (
            query.order_by(RescueCase.created_at.desc(), RescueCase.case_id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        data = {
            "items": [RescueCaseService.serialize_case(c) for c in items],
            "page": page,
            "per_page": per_page,
            "total": total,
        }
        return data, None, 200

    # ---------------------------------------------------------------------
    # Detail retrieval – visibility same as list (implemented in route).
    # ---------------------------------------------------------------------
    @staticmethod
    def get_case(case_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        case = RescueCase.query.get(case_id)
        if not case:
            return None, {"status": "error", "message": "Rescue case not found."}, 404
        return RescueCaseService.serialize_case(case), None, 200

    # ---------------------------------------------------------------------
    # Updates – reporter (while status == Reported) or assigned NGO.
    # ---------------------------------------------------------------------
    @staticmethod
    def update_case(case: RescueCase, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400
        field_error = check_unexpected_or_protected_fields(payload, RESCUE_MUTABLE_FIELDS, RESCUE_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400
        if not payload:
            return None, {"status": "error", "message": "At least one mutable field is required."}, 400

        user = g.current_user
        role = user.role.role_name if user.role else None
        # Authorization checks
        if case.reported_by == user.user_id and case.status == "Reported":
            # Reporter allowed – no further ownership checks needed
            pass
        elif role == "NGO" and getattr(user, "ngo", None) and case.assigned_ngo == user.ngo.ngo_id:
            # Assigned NGO allowed
            pass
        else:
            return None, {"status": "error", "message": "You do not have permission to modify this rescue case."}, 403

        # Validate fields (similar to create)
        details: Dict[str, str] = {}
        if "location" in payload:
            val = payload["location"]
            if not isinstance(val, str) or not val.strip():
                details["location"] = "Location must be a non‑empty string."
            elif len(val) > 255:
                details["location"] = "Location must not exceed 255 characters."
        if "animal_type" in payload:
            val = payload["animal_type"]
            if val is not None and (not isinstance(val, str) or len(val) > 100):
                details["animal_type"] = "Animal type must be a string up to 100 characters."
        if "condition" in payload:
            val = payload["condition"]
            if val is not None and (not isinstance(val, str) or len(val) > 2000):
                details["condition"] = "Condition must be a string up to 2000 characters."
        if "description" in payload:
            val = payload["description"]
            if val is not None and (not isinstance(val, str) or len(val) > 2000):
                details["description"] = "Description must be a string up to 2000 characters."
        if "urgency" in payload:
            val = payload["urgency"]
            if val is not None and (not isinstance(val, str) or val not in VALID_URGENCY_LEVELS):
                details["urgency"] = f"Urgency must be one of: {', '.join(sorted(VALID_URGENCY_LEVELS))}."
        if "image_url" in payload:
            val = payload["image_url"]
            if val is not None:
                if not isinstance(val, str) or len(val) > 2048:
                    details["image_url"] = "Image URL must be a string up to 2048 characters."
                elif not (val.startswith("http://") or val.startswith("https://")):
                    details["image_url"] = "Image URL must be an absolute HTTP/HTTPS URL."
        if details:
            return None, {"status": "error", "message": "Validation failed.", "details": details}, 400

        # Apply updates
        for field in RESCUE_MUTABLE_FIELDS:
            if field in payload:
                setattr(case, field, payload[field].strip() if isinstance(payload[field], str) else payload[field])
        db.session.commit()
        return RescueCaseService.serialize_case(case), None, 200

    # ---------------------------------------------------------------------
    # Assignment – only NGOs with a profile can claim an unassigned case.
    # ---------------------------------------------------------------------
    @staticmethod
    def assign_case(case: RescueCase) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        user = g.current_user
        if not getattr(user, "ngo", None):
            return None, {"status": "error", "message": "No NGO profile found for this user."}, 404
        if case.assigned_ngo is None:
            case.assigned_ngo = user.ngo.ngo_id
            case.status = "NGO Assigned"
            db.session.commit()
            return RescueCaseService.serialize_case(case), None, 200
        elif case.assigned_ngo == user.ngo.ngo_id:
            # Idempotent – already assigned to caller's NGO
            return RescueCaseService.serialize_case(case), None, 200
        else:
            return None, {"status": "error", "message": "Case is already assigned to another NGO."}, 409

    # ---------------------------------------------------------------------
    # Status transition – enforce transition table.
    # ---------------------------------------------------------------------
    @staticmethod
    def update_status(case: RescueCase, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400
        if "status" not in payload:
            return None, {"status": "error", "message": "'status' field is required."}, 400
        new_status = payload["status"]
        if not isinstance(new_status, str) or new_status not in VALID_RESCUE_STATUSES:
            return None, {"status": "error", "message": f"Status must be one of: {', '.join(sorted(VALID_RESCUE_STATUSES))}."}, 400

        user = g.current_user
        if not getattr(user, "ngo", None) or case.assigned_ngo != user.ngo.ngo_id:
            return None, {"status": "error", "message": "You do not have permission to modify status for this rescue case."}, 403

        # Transition table – hard coded according to docs/API.md §5.4
        allowed = {
            "Reported": {"Under Review", "NGO Assigned"},
            "Under Review": {"NGO Assigned"},
            "NGO Assigned": {"Rescued"},
            "Rescued": {"Under Treatment / Foster"},
            "Under Treatment / Foster": {"Adoption Available", "Adopted / Resolved"},
            "Adoption Available": {"Adopted / Resolved"},
        }
        current = case.status
        if new_status == current:
            # Idempotent – return success
            return RescueCaseService.serialize_case(case), None, 200
        if current not in allowed or new_status not in allowed[current]:
            return None, {"status": "error", "message": f"Invalid status transition from '{current}' to '{new_status}'."}, 400
        case.status = new_status
        db.session.commit()
        return RescueCaseService.serialize_case(case), None, 200
