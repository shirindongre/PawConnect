"""
Animal Listing Service.
"""

from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from ..extensions import db
from ..models import Animal, NGO
from ..utils.validation import (
    ANIMAL_MUTABLE_FIELDS,
    ANIMAL_PROTECTED_FIELDS,
    VALID_ANIMAL_STATUSES,
    VALID_GENDERS,
    check_unexpected_or_protected_fields,
)


class AnimalService:
    @staticmethod
    def serialize_animal(animal: Animal) -> Dict[str, Any]:
        return {
            "animal_id": animal.animal_id,
            "ngo_id": animal.ngo_id,
            "name": animal.name,
            "species": animal.species,
            "breed": animal.breed,
            "age": animal.age,
            "gender": animal.gender,
            "description": animal.description,
            "location": animal.location,
            "status": animal.status,
            "image_url": animal.image_url,
            "created_at": animal.created_at.isoformat() if animal.created_at else None,
        }

    @staticmethod
    def _validate_image_url(url: str) -> bool:
        """Validate that url is a non-empty string and a valid absolute URL (http/https)."""
        if not isinstance(url, str):
            return False
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)

    @staticmethod
    def list_public_animals(page_raw: Any, per_page_raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Public list of animals with status='Available'.
        Returns: (data, error_response_dict, status_code)
        """
        try:
            page = int(page_raw) if page_raw is not None else 1
            per_page = int(per_page_raw) if per_page_raw is not None else 20
        except (ValueError, TypeError):
            return None, {"status": "error", "message": "Invalid pagination parameters."}, 400

        if page < 1:
            return None, {"status": "error", "message": "Page must be greater than or equal to 1."}, 400
        if per_page < 1 or per_page > 100:
            return None, {"status": "error", "message": "Per page must be between 1 and 100."}, 400

        query = Animal.query.filter_by(status="Available").order_by(Animal.created_at.desc(), Animal.animal_id.desc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "items": [AnimalService.serialize_animal(a) for a in items],
            "page": page,
            "per_page": per_page,
            "total": total,
        }, None, 200

    @staticmethod
    def get_animal_by_id(animal_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        animal = Animal.query.get(animal_id)
        if not animal:
            return None, {"status": "error", "message": "Animal not found."}, 404
        return AnimalService.serialize_animal(animal), None, 200

    @staticmethod
    def create_animal(ngo: NGO, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Create a new animal for the NGO.
        Returns: (data, error_response_dict, status_code)
        """
        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        field_error = check_unexpected_or_protected_fields(payload, ANIMAL_MUTABLE_FIELDS, ANIMAL_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        details = {}

        # species is required
        if "species" not in payload:
            details["species"] = "Species is required."
        else:
            species_val = payload["species"]
            if not isinstance(species_val, str) or not species_val.strip():
                details["species"] = "Species must be a non-empty string."
            elif len(species_val) > 100:
                details["species"] = "Species must not exceed 100 characters."

        # name (optional)
        if "name" in payload:
            name_val = payload["name"]
            if name_val is not None:
                if not isinstance(name_val, str):
                    details["name"] = "Name must be a string."
                elif len(name_val) > 150:
                    details["name"] = "Name must not exceed 150 characters."

        # breed (optional)
        if "breed" in payload:
            breed_val = payload["breed"]
            if breed_val is not None:
                if not isinstance(breed_val, str):
                    details["breed"] = "Breed must be a string."
                elif len(breed_val) > 100:
                    details["breed"] = "Breed must not exceed 100 characters."

        # age (optional)
        if "age" in payload:
            age_val = payload["age"]
            if age_val is not None:
                if not isinstance(age_val, int) or isinstance(age_val, bool):
                    details["age"] = "Age must be an integer."
                elif age_val < 0:
                    details["age"] = "Age must be greater than or equal to 0."

        # gender (optional)
        if "gender" in payload:
            gender_val = payload["gender"]
            if gender_val is not None:
                if gender_val not in VALID_GENDERS:
                    details["gender"] = f"Gender must be one of: {', '.join(sorted(VALID_GENDERS))}."

        # description (optional)
        if "description" in payload:
            desc_val = payload["description"]
            if desc_val is not None:
                if not isinstance(desc_val, str):
                    details["description"] = "Description must be a string."
                elif len(desc_val) > 2000:
                    details["description"] = "Description must not exceed 2000 characters."

        # location (optional)
        if "location" in payload:
            loc_val = payload["location"]
            if loc_val is not None:
                if not isinstance(loc_val, str):
                    details["location"] = "Location must be a string."
                elif len(loc_val) > 255:
                    details["location"] = "Location must not exceed 255 characters."

        # status (optional, defaults to 'Available')
        if "status" in payload:
            status_val = payload["status"]
            if status_val is not None:
                if status_val not in VALID_ANIMAL_STATUSES:
                    details["status"] = f"Status must be one of: {', '.join(sorted(VALID_ANIMAL_STATUSES))}."

        # image_url (optional)
        if "image_url" in payload:
            img_val = payload["image_url"]
            if img_val is not None:
                if not isinstance(img_val, str):
                    details["image_url"] = "Image URL must be a string."
                elif len(img_val) > 2048:
                    details["image_url"] = "Image URL must not exceed 2048 characters."
                elif not AnimalService._validate_image_url(img_val):
                    details["image_url"] = "Image URL must be a valid absolute HTTP or HTTPS URL."

        if details:
            return None, {
                "status": "error",
                "message": "Validation failed.",
                "details": details,
            }, 400

        animal = Animal(
            ngo_id=ngo.ngo_id,
            species=payload["species"].strip(),
            name=payload.get("name").strip() if isinstance(payload.get("name"), str) else payload.get("name"),
            breed=payload.get("breed").strip() if isinstance(payload.get("breed"), str) else payload.get("breed"),
            age=payload.get("age"),
            gender=payload.get("gender"),
            description=payload.get("description").strip() if isinstance(payload.get("description"), str) else payload.get("description"),
            location=payload.get("location").strip() if isinstance(payload.get("location"), str) else payload.get("location"),
            status=payload.get("status") if payload.get("status") else "Available",
            image_url=payload.get("image_url").strip() if isinstance(payload.get("image_url"), str) else payload.get("image_url"),
        )
        db.session.add(animal)
        db.session.commit()

        return AnimalService.serialize_animal(animal), None, 201

    @staticmethod
    def update_animal(animal: Animal, ngo: NGO, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Update an animal listing.
        Enforces ownership before updating.
        Returns: (data, error_response_dict, status_code)
        """
        # Ownership check
        if animal.ngo_id != ngo.ngo_id:
            return None, {"status": "error", "message": "You do not have permission to modify this animal."}, 403

        if not isinstance(payload, dict):
            return None, {"status": "error", "message": "Request body must be a JSON object."}, 400

        field_error = check_unexpected_or_protected_fields(payload, ANIMAL_MUTABLE_FIELDS, ANIMAL_PROTECTED_FIELDS)
        if field_error:
            return None, {"status": "error", "message": field_error}, 400

        provided_fields = [k for k in payload.keys() if k in ANIMAL_MUTABLE_FIELDS]
        if not provided_fields:
            return None, {"status": "error", "message": "At least one mutable field is required."}, 400

        details = {}

        if "species" in payload:
            species_val = payload["species"]
            if not isinstance(species_val, str) or not species_val.strip():
                details["species"] = "Species must be a non-empty string."
            elif len(species_val) > 100:
                details["species"] = "Species must not exceed 100 characters."

        if "name" in payload:
            name_val = payload["name"]
            if name_val is not None:
                if not isinstance(name_val, str):
                    details["name"] = "Name must be a string."
                elif len(name_val) > 150:
                    details["name"] = "Name must not exceed 150 characters."

        if "breed" in payload:
            breed_val = payload["breed"]
            if breed_val is not None:
                if not isinstance(breed_val, str):
                    details["breed"] = "Breed must be a string."
                elif len(breed_val) > 100:
                    details["breed"] = "Breed must not exceed 100 characters."

        if "age" in payload:
            age_val = payload["age"]
            if age_val is not None:
                if not isinstance(age_val, int) or isinstance(age_val, bool):
                    details["age"] = "Age must be an integer."
                elif age_val < 0:
                    details["age"] = "Age must be greater than or equal to 0."

        if "gender" in payload:
            gender_val = payload["gender"]
            if gender_val is not None:
                if gender_val not in VALID_GENDERS:
                    details["gender"] = f"Gender must be one of: {', '.join(sorted(VALID_GENDERS))}."

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

        if "status" in payload:
            status_val = payload["status"]
            if status_val is not None:
                if status_val not in VALID_ANIMAL_STATUSES:
                    details["status"] = f"Status must be one of: {', '.join(sorted(VALID_ANIMAL_STATUSES))}."

        if "image_url" in payload:
            img_val = payload["image_url"]
            if img_val is not None:
                if not isinstance(img_val, str):
                    details["image_url"] = "Image URL must be a string."
                elif len(img_val) > 2048:
                    details["image_url"] = "Image URL must not exceed 2048 characters."
                elif not AnimalService._validate_image_url(img_val):
                    details["image_url"] = "Image URL must be a valid absolute HTTP or HTTPS URL."

        if details:
            return None, {
                "status": "error",
                "message": "Validation failed.",
                "details": details,
            }, 400

        # Apply only supplied fields
        if "species" in payload:
            animal.species = payload["species"].strip()
        if "name" in payload:
            animal.name = payload["name"].strip() if isinstance(payload["name"], str) else payload["name"]
        if "breed" in payload:
            animal.breed = payload["breed"].strip() if isinstance(payload["breed"], str) else payload["breed"]
        if "age" in payload:
            animal.age = payload["age"]
        if "gender" in payload:
            animal.gender = payload["gender"]
        if "description" in payload:
            animal.description = payload["description"].strip() if isinstance(payload["description"], str) else payload["description"]
        if "location" in payload:
            animal.location = payload["location"].strip() if isinstance(payload["location"], str) else payload["location"]
        if "status" in payload:
            animal.status = payload["status"]
        if "image_url" in payload:
            animal.image_url = payload["image_url"].strip() if isinstance(payload["image_url"], str) else payload["image_url"]

        db.session.commit()

        return AnimalService.serialize_animal(animal), None, 200

    @staticmethod
    def delete_animal(animal: Animal, ngo: NGO) -> Tuple[bool, Optional[Dict[str, Any]], int]:
        """
        Hard delete an animal listing.
        Enforces ownership before deletion.
        Returns: (success, error_response_dict, status_code)
        """
        if animal.ngo_id != ngo.ngo_id:
            return False, {"status": "error", "message": "You do not have permission to modify this animal."}, 403

        db.session.delete(animal)
        db.session.commit()

        return True, None, 204
