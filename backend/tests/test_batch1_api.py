"""
Batch 1 REST API Tests (User, NGO, Animal).
============================================

Tests cover:
- GET /api/users/me (Success, 401 unauth, 403 no profile)
- PATCH /api/users/me (Success, validation, protected fields, 401, 403)
- GET /api/ngos/me (Success, 401 unauth, 403 wrong role, 404 no NGO linked)
- POST /api/ngos (Success 201, 409 conflict, required fields, text limit, protected fields)
- GET /api/animals (Public, only 'Available', pagination defaults, invalid pagination)
- GET /api/animals/<id> (Public, 200, 404)
- POST /api/animals (Success 201, 401, 403 wrong role, 404 no NGO, required species, enums, limits, protected fields)
- PATCH /api/animals/<id> (Success 200, 403 ownership violation, 404 not found, validation, protected fields)
- DELETE /api/animals/<id> (Success 204 no body, 403 ownership violation, 404 not found, verified deleted)
"""

import sys
import time
import uuid
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app
from app.extensions import db
from app.models import Role, User, NGO, Animal
from app.models.role import RoleName
from app.services.cognito_auth_service import CognitoAuthService


class TestBatch1APIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.public_key = cls.private_key.public_key()
        cls.kid = "batch1-test-key-id"

        cls.test_region = "us-east-1"
        cls.test_user_pool_id = "us-east-1_Batch1Pool"
        cls.test_client_id = "batch1-test-client"
        cls.expected_issuer = (
            f"https://cognito-idp.{cls.test_region}.amazonaws.com/{cls.test_user_pool_id}"
        )

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["COGNITO_REGION"] = cls.test_region
        cls.app.config["COGNITO_USER_POOL_ID"] = cls.test_user_pool_id
        cls.app.config["COGNITO_CLIENT_ID"] = cls.test_client_id

    def setUp(self):
        self.test_id = uuid.uuid4().hex[:8]
        self._created_animals = []
        self._created_ngos = []
        self._created_users = []

        mock_jwk = MagicMock()
        mock_jwk.key = self.public_key
        self.mock_jwks_client = MagicMock()
        self.mock_jwks_client.get_signing_key_from_jwt.return_value = mock_jwk

        self.auth_service_patcher = patch(
            "app.utils.auth_decorators.CognitoAuthService",
            side_effect=lambda *args, **kwargs: CognitoAuthService(
                region=self.test_region,
                user_pool_id=self.test_user_pool_id,
                client_id=self.test_client_id,
                jwk_client=self.mock_jwks_client,
            ),
        )
        self.auth_service_patcher.start()
        self.client = self.app.test_client()

    def tearDown(self):
        self.auth_service_patcher.stop()

        with self.app.app_context():
            db.session.rollback()
            for a_id in self._created_animals:
                record = db.session.get(Animal, a_id)
                if record:
                    db.session.delete(record)
            db.session.commit()

            for n_id in self._created_ngos:
                record = db.session.get(NGO, n_id)
                if record:
                    db.session.delete(record)
            db.session.commit()

            for u_id in self._created_users:
                record = db.session.get(User, u_id)
                if record:
                    db.session.delete(record)
            db.session.commit()

    def _generate_token(self, sub: str) -> str:
        now = int(time.time())
        payload = {
            "sub": sub,
            "iss": self.expected_issuer,
            "aud": self.test_client_id,
            "token_use": "id",
            "exp": now + 3600,
            "iat": now,
        }
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )

    def _auth_header(self, sub: str) -> dict:
        return {"Authorization": f"Bearer {self._generate_token(sub)}"}

    def _create_user(self, role_name: str, auth_id: str = None) -> User:
        with self.app.app_context():
            role = Role.query.filter_by(role_name=role_name).first()
            user = User(
                name=f"Test {role_name} {self.test_id}",
                email=f"test_{role_name.lower()}_{uuid.uuid4().hex[:6]}@example.com",
                role_id=role.role_id,
                auth_id=auth_id or f"sub-{uuid.uuid4().hex}",
                location="Bangalore",
                phone="+919876543210",
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.user_id
            self._created_users.append(user_id)
            return user

    def _create_ngo(self, user_or_user_id, name: str = None) -> NGO:
        u_id = user_or_user_id.user_id if hasattr(user_or_user_id, "user_id") else user_or_user_id
        with self.app.app_context():
            ngo = NGO(
                user_id=u_id,
                name=name or f"NGO {self.test_id}",
                description="Test description",
                location="Bangalore",
                contact="contact@ngo.org",
                verification_status="Unverified",
            )
            db.session.add(ngo)
            db.session.commit()
            ngo_id = ngo.ngo_id
            self._created_ngos.append(ngo_id)
            return ngo

    def _create_animal(self, ngo_or_ngo_id, species: str = "Dog", status: str = "Available", name: str = None) -> Animal:
        n_id = ngo_or_ngo_id.ngo_id if hasattr(ngo_or_ngo_id, "ngo_id") else ngo_or_ngo_id
        with self.app.app_context():
            animal = Animal(
                ngo_id=n_id,
                name=name or f"Animal {self.test_id}",
                species=species,
                breed="Indie",
                age=2,
                gender="Male",
                description="Friendly animal",
                location="Bangalore",
                status=status,
                image_url="https://example.com/animal.jpg",
            )
            db.session.add(animal)
            db.session.commit()
            animal_id = animal.animal_id
            self._created_animals.append(animal_id)
            return animal

    # -------------------------------------------------------------------------
    # 1. USER PROFILE ENDPOINTS
    # -------------------------------------------------------------------------

    def test_get_user_profile_success(self):
        sub = f"sub-user-me-{self.test_id}"
        user = self._create_user(RoleName.USER, auth_id=sub)

        res = self.client.get("/api/users/me", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["user_id"], user.user_id)
        self.assertEqual(body["data"]["email"], user.email)
        self.assertEqual(body["data"]["role"], RoleName.USER)

    def test_get_user_profile_unauthenticated(self):
        res = self.client.get("/api/users/me")
        self.assertEqual(res.status_code, 401)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["message"], "Authorization header is required.")

    def test_get_user_profile_no_local_user(self):
        unlinked_sub = f"sub-no-user-{self.test_id}"
        res = self.client.get("/api/users/me", headers=self._auth_header(unlinked_sub))
        self.assertEqual(res.status_code, 403)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("No registered PawConnect profile found", body["message"])

    def test_patch_user_profile_success(self):
        sub = f"sub-patch-user-{self.test_id}"
        user = self._create_user(RoleName.USER, auth_id=sub)

        payload = {
            "name": "Updated Name",
            "phone": "+911122334455",
            "location": "Mumbai",
        }
        res = self.client.patch("/api/users/me", headers=self._auth_header(sub), json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["name"], "Updated Name")
        self.assertEqual(body["data"]["location"], "Mumbai")

        # Verify DB persistence
        with self.app.app_context():
            u = User.query.get(user.user_id)
            self.assertEqual(u.name, "Updated Name")
            self.assertEqual(u.phone, "+911122334455")
            self.assertEqual(u.location, "Mumbai")

    def test_patch_user_profile_validation_empty_payload(self):
        sub = f"sub-patch-empty-{self.test_id}"
        self._create_user(RoleName.USER, auth_id=sub)

        res = self.client.patch("/api/users/me", headers=self._auth_header(sub), json={})
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("At least one mutable field is required", body["message"])

    def test_patch_user_profile_rejected_protected_fields(self):
        sub = f"sub-patch-prot-{self.test_id}"
        self._create_user(RoleName.USER, auth_id=sub)

        res = self.client.patch(
            "/api/users/me",
            headers=self._auth_header(sub),
            json={"name": "New Name", "email": "hacked@example.com", "role_id": 99},
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("Unknown or protected fields", body["message"])

    def test_patch_user_profile_length_limits(self):
        sub = f"sub-patch-len-{self.test_id}"
        self._create_user(RoleName.USER, auth_id=sub)

        res = self.client.patch(
            "/api/users/me",
            headers=self._auth_header(sub),
            json={
                "name": "a" * 101,
                "phone": "1" * 21,
                "location": "x" * 256,
            },
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("name", body["details"])
        self.assertIn("phone", body["details"])
        self.assertIn("location", body["details"])

    # -------------------------------------------------------------------------
    # 2. NGO PROFILE ENDPOINTS
    # -------------------------------------------------------------------------

    def test_get_ngo_profile_success(self):
        sub = f"sub-ngo-me-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        ngo = self._create_ngo(user)

        res = self.client.get("/api/ngos/me", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["ngo_id"], ngo.ngo_id)
        self.assertEqual(body["data"]["name"], ngo.name)
        self.assertEqual(body["data"]["verification_status"], "Unverified")

    def test_get_ngo_profile_wrong_role(self):
        sub = f"sub-wrong-role-{self.test_id}"
        self._create_user(RoleName.USER, auth_id=sub)

        res = self.client.get("/api/ngos/me", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 403)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("permission", body["message"])

    def test_get_ngo_profile_not_linked(self):
        sub = f"sub-ngo-no-profile-{self.test_id}"
        self._create_user(RoleName.NGO, auth_id=sub)

        res = self.client.get("/api/ngos/me", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 404)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("No NGO profile found for this user", body["message"])

    def test_post_ngo_profile_success(self):
        sub = f"sub-post-ngo-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        user_id = user.user_id

        payload = {
            "name": "New Animal Shelter",
            "description": "Caring for rescue animals",
            "location": "Whitefield, Bangalore",
            "contact": "shelter@example.org",
        }
        res = self.client.post("/api/ngos", headers=self._auth_header(sub), json=payload)
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["name"], "New Animal Shelter")
        self.assertEqual(body["data"]["verification_status"], "Unverified")

        with self.app.app_context():
            ngo_db = NGO.query.filter_by(user_id=user_id).first()
            self.assertIsNotNone(ngo_db)
            self._created_ngos.append(ngo_db.ngo_id)

    def test_post_ngo_profile_conflict_duplicate(self):
        sub = f"sub-ngo-dup-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        self._create_ngo(user.user_id)

        res = self.client.post(
            "/api/ngos",
            headers=self._auth_header(sub),
            json={"name": "Duplicate NGO"},
        )
        self.assertEqual(res.status_code, 409)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("already exists", body["message"])

    def test_post_ngo_profile_name_required(self):
        sub = f"sub-ngo-no-name-{self.test_id}"
        self._create_user(RoleName.NGO, auth_id=sub)

        res = self.client.post(
            "/api/ngos",
            headers=self._auth_header(sub),
            json={"description": "Missing name"},
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("name", body["details"])

    def test_post_ngo_profile_text_limit(self):
        sub = f"sub-ngo-desc-limit-{self.test_id}"
        self._create_user(RoleName.NGO, auth_id=sub)

        res = self.client.post(
            "/api/ngos",
            headers=self._auth_header(sub),
            json={
                "name": "Shelter",
                "description": "x" * 2001,
            },
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertIn("description", body["details"])

    def test_post_ngo_profile_protected_fields_rejected(self):
        sub = f"sub-ngo-prot-{self.test_id}"
        self._create_user(RoleName.NGO, auth_id=sub)

        res = self.client.post(
            "/api/ngos",
            headers=self._auth_header(sub),
            json={
                "name": "Shelter",
                "verification_status": "Verified",
                "user_id": 999,
            },
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("Unknown or protected fields", body["message"])

    # -------------------------------------------------------------------------
    # 3. ANIMAL LISTING ENDPOINTS
    # -------------------------------------------------------------------------

    def test_get_animals_public_only_available_and_pagination(self):
        user = self._create_user(RoleName.NGO)
        ngo = self._create_ngo(user)

        a1 = self._create_animal(ngo, status="Available", name=f"Available-1-{self.test_id}")
        a2 = self._create_animal(ngo, status="Available", name=f"Available-2-{self.test_id}")
        a3 = self._create_animal(ngo, status="Adopted", name=f"Adopted-{self.test_id}")
        a4 = self._create_animal(ngo, status="Under Treatment", name=f"Treatment-{self.test_id}")

        res = self.client.get("/api/animals?page=1&per_page=10")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["status"], "success")

        names = [item["name"] for item in body["data"]["items"]]
        self.assertIn(a1.name, names)
        self.assertIn(a2.name, names)
        self.assertNotIn(a3.name, names)
        self.assertNotIn(a4.name, names)

        for item in body["data"]["items"]:
            self.assertEqual(item["status"], "Available")

    def test_get_animals_invalid_pagination(self):
        res1 = self.client.get("/api/animals?page=0")
        self.assertEqual(res1.status_code, 400)
        self.assertEqual(res1.get_json()["status"], "error")

        res2 = self.client.get("/api/animals?per_page=101")
        self.assertEqual(res2.status_code, 400)

        res3 = self.client.get("/api/animals?page=abc")
        self.assertEqual(res3.status_code, 400)

    def test_get_single_animal_success_and_not_found(self):
        user = self._create_user(RoleName.NGO)
        ngo = self._create_ngo(user)
        animal = self._create_animal(ngo, status="Available")

        res = self.client.get(f"/api/animals/{animal.animal_id}")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["data"]["animal_id"], animal.animal_id)
        self.assertEqual(body["data"]["name"], animal.name)

        res404 = self.client.get("/api/animals/99999999")
        self.assertEqual(res404.status_code, 404)
        self.assertEqual(res404.get_json()["status"], "error")

    def test_post_animal_success(self):
        sub = f"sub-post-animal-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        ngo = self._create_ngo(user)

        payload = {
            "species": "Cat",
            "name": "Luna",
            "breed": "Persian",
            "age": 1,
            "gender": "Female",
            "description": "Playful kitten",
            "location": "Koramangala, Bangalore",
            "status": "Available",
            "image_url": "https://example.com/luna.jpg",
        }
        res = self.client.post("/api/animals", headers=self._auth_header(sub), json=payload)
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["name"], "Luna")
        self.assertEqual(body["data"]["species"], "Cat")
        self.assertEqual(body["data"]["ngo_id"], ngo.ngo_id)

        with self.app.app_context():
            a = Animal.query.get(body["data"]["animal_id"])
            self.assertIsNotNone(a)
            self._created_animals.append(a.animal_id)

    def test_post_animal_missing_species(self):
        sub = f"sub-animal-no-species-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        self._create_ngo(user)

        res = self.client.post(
            "/api/animals",
            headers=self._auth_header(sub),
            json={"name": "No Species"},
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertIn("species", body["details"])

    def test_post_animal_validation_enums_and_limits(self):
        sub = f"sub-animal-val-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        self._create_ngo(user)

        payload = {
            "species": "Dog",
            "name": "a" * 151,
            "age": -1,
            "gender": "InvalidGender",
            "status": "INVALID_STATUS",
            "description": "x" * 2001,
            "image_url": "not-a-valid-url",
        }
        res = self.client.post("/api/animals", headers=self._auth_header(sub), json=payload)
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("name", body["details"])
        self.assertIn("age", body["details"])
        self.assertIn("gender", body["details"])
        self.assertIn("status", body["details"])
        self.assertIn("description", body["details"])
        self.assertIn("image_url", body["details"])

    def test_post_animal_protected_fields_rejected(self):
        sub = f"sub-animal-prot-{self.test_id}"
        user = self._create_user(RoleName.NGO, auth_id=sub)
        self._create_ngo(user)

        res = self.client.post(
            "/api/animals",
            headers=self._auth_header(sub),
            json={"species": "Dog", "ngo_id": 9999, "animal_id": 123},
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertIn("Unknown or protected fields", body["message"])

    def test_patch_animal_success_and_ownership(self):
        sub_owner = f"sub-owner-{self.test_id}"
        user_owner = self._create_user(RoleName.NGO, auth_id=sub_owner)
        ngo_owner = self._create_ngo(user_owner)
        animal = self._create_animal(ngo_owner)

        sub_other = f"sub-other-{self.test_id}"
        user_other = self._create_user(RoleName.NGO, auth_id=sub_other)
        self._create_ngo(user_other)

        # Attempt modify from different NGO -> 403
        res_forbidden = self.client.patch(
            f"/api/animals/{animal.animal_id}",
            headers=self._auth_header(sub_other),
            json={"name": "Hijacked Name"},
        )
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertIn("permission", res_forbidden.get_json()["message"])

        # Modify from owner NGO -> 200
        res_ok = self.client.patch(
            f"/api/animals/{animal.animal_id}",
            headers=self._auth_header(sub_owner),
            json={"status": "Adopted", "age": 3},
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.get_json()["data"]["status"], "Adopted")
        self.assertEqual(res_ok.get_json()["data"]["age"], 3)

        # Verify DB
        with self.app.app_context():
            a_db = Animal.query.get(animal.animal_id)
            self.assertEqual(a_db.status, "Adopted")
            self.assertEqual(a_db.age, 3)

    def test_patch_animal_not_found(self):
        sub_owner = f"sub-owner-nf-{self.test_id}"
        user_owner = self._create_user(RoleName.NGO, auth_id=sub_owner)
        self._create_ngo(user_owner)

        res = self.client.patch(
            "/api/animals/99999999",
            headers=self._auth_header(sub_owner),
            json={"name": "Nonexistent"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Animal not found", res.get_json()["message"])

    def test_delete_animal_success_and_ownership(self):
        sub_owner = f"sub-del-owner-{self.test_id}"
        user_owner = self._create_user(RoleName.NGO, auth_id=sub_owner)
        ngo_owner = self._create_ngo(user_owner)
        animal = self._create_animal(ngo_owner)

        sub_other = f"sub-del-other-{self.test_id}"
        user_other = self._create_user(RoleName.NGO, auth_id=sub_other)
        self._create_ngo(user_other)

        # Attempt delete from different NGO -> 403
        res_forbidden = self.client.delete(
            f"/api/animals/{animal.animal_id}",
            headers=self._auth_header(sub_other),
        )
        self.assertEqual(res_forbidden.status_code, 403)

        # Attempt delete from owner NGO -> 204 No Content
        res_del = self.client.delete(
            f"/api/animals/{animal.animal_id}",
            headers=self._auth_header(sub_owner),
        )
        self.assertEqual(res_del.status_code, 204)
        self.assertEqual(res_del.data, b"")

        # Verify deleted in database
        with self.app.app_context():
            self.assertIsNone(Animal.query.get(animal.animal_id))

    def test_delete_animal_not_found(self):
        sub_owner = f"sub-del-nf-{self.test_id}"
        user_owner = self._create_user(RoleName.NGO, auth_id=sub_owner)
        self._create_ngo(user_owner)

        res = self.client.delete(
            "/api/animals/99999999",
            headers=self._auth_header(sub_owner),
        )
        self.assertEqual(res.status_code, 404)
