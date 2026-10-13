"""
Rescue Case API tests – Batch 2A.
Covers the six contracted endpoints with success, validation, auth, and visibility scenarios.
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
from app.models import Role, User, NGO, RescueCase
from app.models.role import RoleName
from app.services.cognito_auth_service import CognitoAuthService


class TestRescueCaseAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # RSA keys for JWT signing
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        cls.kid = "rescue-case-test-key"
        cls.test_region = "us-east-1"
        cls.test_user_pool_id = "us-east-1_RescuePool"
        cls.test_client_id = "rescue-test-client"
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["COGNITO_REGION"] = cls.test_region
        cls.app.config["COGNITO_USER_POOL_ID"] = cls.test_user_pool_id
        cls.app.config["COGNITO_CLIENT_ID"] = cls.test_client_id

    def setUp(self):
        # token helpers
        self._created_users = []
        self._created_ngos = []
        self._created_cases = []

        mock_jwk = MagicMock()
        mock_jwk.key = self.public_key
        self.mock_jwks_client = MagicMock()
        self.mock_jwks_client.get_signing_key_from_jwt.return_value = mock_jwk

        self.auth_service_patcher = patch(
            "app.utils.auth_decorators.CognitoAuthService",
            side_effect=lambda *a, **kw: CognitoAuthService(
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
            for case_id in self._created_cases:
                rc = db.session.get(RescueCase, case_id)
                if rc:
                    db.session.delete(rc)
            db.session.commit()
            for ngo_id in self._created_ngos:
                n = db.session.get(NGO, ngo_id)
                if n:
                    db.session.delete(n)
            db.session.commit()
            for user_id in self._created_users:
                u = db.session.get(User, user_id)
                if u:
                    db.session.delete(u)
            db.session.commit()

    # ----------- helpers ---------------------------------------------------
    def _generate_token(self, sub: str) -> str:
        now = int(time.time())
        payload = {
            "sub": sub,
            "iss": f"https://cognito-idp.{self.test_region}.amazonaws.com/{self.test_user_pool_id}",
            "aud": self.test_client_id,
            "token_use": "id",
            "exp": now + 3600,
            "iat": now,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": self.kid})

    def _auth_header(self, sub: str) -> dict:
        return {"Authorization": f"Bearer {self._generate_token(sub)}"}

    def _create_user(self, role_name: str, auth_id: str = None) -> User:
        with self.app.app_context():
            role = Role.query.filter_by(role_name=role_name).first()
            user = User(
                name=f"Test {role_name} {uuid.uuid4().hex[:6]}",
                email=f"{role_name.lower()}_{uuid.uuid4().hex[:6]}@example.com",
                role_id=role.role_id,
                auth_id=auth_id or f"sub-{uuid.uuid4().hex}",
                location="Bangalore",
                phone="+919876543210",
            )
            db.session.add(user)
            db.session.commit()
            self._created_users.append(user.user_id)
            return user

    def _create_ngo(self, user_or_id, name: str = None) -> NGO:
        user_id = user_or_id.user_id if hasattr(user_or_id, "user_id") else user_or_id
        with self.app.app_context():
            ngo = NGO(
                user_id=user_id,
                name=name or f"NGO {uuid.uuid4().hex[:6]}",
                description="Test NGO",
                location="Bangalore",
                contact="contact@ngo.org",
                verification_status="Unverified",
            )
            db.session.add(ngo)
            db.session.commit()
            self._created_ngos.append(ngo.ngo_id)
            return ngo

    def _create_rescue_case(self, reporter_sub: str, payload: dict) -> RescueCase:
        # Use the POST endpoint for realism
        res = self.client.post(
            "/api/rescue-cases",
            headers=self._auth_header(reporter_sub),
            json=payload,
        )
        self.assertEqual(res.status_code, 201)
        case_id = res.get_json()["data"]["case_id"]
        with self.app.app_context():
            rc = RescueCase.query.get(case_id)
            self._created_cases.append(rc.case_id)
            return rc

    # ----------- tests ----------------------------------------------------
    def test_post_rescue_case_success(self):
        sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        user = self._create_user(RoleName.USER, auth_id=sub)
        payload = {"location": "Some Street 123"}
        res = self.client.post(
            "/api/rescue-cases",
            headers=self._auth_header(sub),
            json=payload,
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()["data"]
        self.assertEqual(data["reported_by"], user.user_id)
        self.assertIsNone(data["assigned_ngo"])
        self.assertEqual(data["status"], "Reported")
        self._created_cases.append(data["case_id"])

    def test_post_rescue_case_missing_location(self):
        sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        res = self.client.post(
            "/api/rescue-cases",
            headers=self._auth_header(sub),
            json={"description": "Missing location"},
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertEqual(body["status"], "error")
        self.assertIn("location", body["details"])

    def test_post_rescue_case_protected_fields(self):
        sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        payload = {"location": "Place", "reported_by": 999, "assigned_ngo": 1}
        res = self.client.post(
            "/api/rescue-cases",
            headers=self._auth_header(sub),
            json=payload,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("protected", res.get_json()["message"].lower())

    def test_get_rescue_cases_list_visibility_user(self):
        # Reporter creates two cases, one stays reported, another progresses
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        reporter = self._create_user(RoleName.USER, auth_id=reporter_sub)
        case1 = self._create_rescue_case(reporter_sub, {"location": "Loc1"})
        case2 = self._create_rescue_case(reporter_sub, {"location": "Loc2"})
        # Advance case2 status to Under Review (allowed by reporter)
        self.client.patch(
            f"/api/rescue-cases/{case2.case_id}",
            headers=self._auth_header(reporter_sub),
            json={"location": "Loc2-updated"},
        )
        # List as reporter – should see both cases
        res = self.client.get(
            "/api/rescue-cases",
            headers=self._auth_header(reporter_sub),
        )
        self.assertEqual(res.status_code, 200)
        items = res.get_json()["data"]["items"]
        ids = {i["case_id"] for i in items}
        self.assertIn(case1.case_id, ids)
        self.assertIn(case2.case_id, ids)

    def test_get_rescue_cases_list_visibility_ngo(self):
        # NGO user with profile sees unassigned + own assigned
        ngo_user_sub = f"sub-ngo-{uuid.uuid4().hex[:6]}"
        ngo_user = self._create_user(RoleName.NGO, auth_id=ngo_user_sub)
        ngo = self._create_ngo(ngo_user)
        # Create case reported by a regular user (unassigned)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case_unassigned = self._create_rescue_case(reporter_sub, {"location": "Public"})
        # Create case assigned to this NGO via assign endpoint
        case_assigned = self._create_rescue_case(reporter_sub, {"location": "Public2"})
        self.client.post(
            f"/api/rescue-cases/{case_assigned.case_id}/assign",
            headers=self._auth_header(ngo_user_sub),
        )
        # Another NGO's case (should be invisible)
        other_ngo_user_sub = f"sub-other-ngo-{uuid.uuid4().hex[:6]}"
        other_user = self._create_user(RoleName.NGO, auth_id=other_ngo_user_sub)
        other_ngo = self._create_ngo(other_user)
        other_case = self._create_rescue_case(reporter_sub, {"location": "Other"})
        self.client.post(
            f"/api/rescue-cases/{other_case.case_id}/assign",
            headers=self._auth_header(other_ngo_user_sub),
        )
        # List as first NGO – should see unassigned and its own assigned only
        res = self.client.get(
            "/api/rescue-cases",
            headers=self._auth_header(ngo_user_sub),
        )
        self.assertEqual(res.status_code, 200)
        ids = {i["case_id"] for i in res.get_json()["data"]["items"]}
        self.assertIn(case_unassigned.case_id, ids)
        self.assertIn(case_assigned.case_id, ids)
        self.assertNotIn(other_case.case_id, ids)

    def test_get_rescue_case_detail_not_found(self):
        sub = f"sub-user-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        res = self.client.get("/api/rescue-cases/9999999", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json()["status"], "error")

    def test_patch_rescue_case_success_reporter(self):
        sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        case = self._create_rescue_case(sub, {"location": "Old"})
        payload = {"location": "New Location", "description": "Updated"}
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}",
            headers=self._auth_header(sub),
            json=payload,
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertEqual(data["location"], "New Location")
        self.assertEqual(data["description"], "Updated")

    def test_patch_rescue_case_unauthorized_other_user(self):
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        other_sub = f"sub-other-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        self._create_user(RoleName.USER, auth_id=other_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Loc"})
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}",
            headers=self._auth_header(other_sub),
            json={"location": "Hack"},
        )
        self.assertEqual(res.status_code, 403)

    def test_patch_rescue_case_after_status_advanced_forbidden(self):
        sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        case = self._create_rescue_case(sub, {"location": "Loc"})
        # Reporter updates status to Under Review via status endpoint (allowed transition)
        self.client.patch(
            f"/api/rescue-cases/{case.case_id}/status",
            headers=self._auth_header(sub),
            json={"status": "Under Review"},
        )
        # Now attempt to patch mutable fields – should be forbidden (reporter no longer owner for updates)
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}",
            headers=self._auth_header(sub),
            json={"location": "New"},
        )
        self.assertEqual(res.status_code, 403)

    def test_assign_rescue_case_success(self):
        ngo_user_sub = f"sub-ngo-{uuid.uuid4().hex[:6]}"
        ngo_user = self._create_user(RoleName.NGO, auth_id=ngo_user_sub)
        self._create_ngo(ngo_user)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Place"})
        res = self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo_user_sub),
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        # Query the assigned NGO inside an application context to avoid RuntimeError
        with self.app.app_context():
            expected_ngo_id = NGO.query.filter_by(user_id=ngo_user.user_id).first().ngo_id
        self.assertEqual(data["assigned_ngo"], expected_ngo_id)
        self.assertEqual(data["status"], "NGO Assigned")

    def test_assign_rescue_case_already_assigned_to_other(self):
        # Create two NGOs
        ngo1_sub = f"sub-ngo1-{uuid.uuid4().hex[:6]}"
        ngo1_user = self._create_user(RoleName.NGO, auth_id=ngo1_sub)
        ngo1 = self._create_ngo(ngo1_user)
        ngo2_sub = f"sub-ngo2-{uuid.uuid4().hex[:6]}"
        ngo2_user = self._create_user(RoleName.NGO, auth_id=ngo2_sub)
        self._create_ngo(ngo2_user)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Place"})
        # First NGO claims it
        self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo1_sub),
        )
        # Second NGO attempts assignment – should get 409
        res = self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo2_sub),
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("already assigned", res.get_json()["message"].lower())

    def test_status_transition_allowed(self):
        # Reporter creates case, NGO claims, then NGO moves through allowed statuses
        ngo_sub = f"sub-ngo-{uuid.uuid4().hex[:6]}"
        ngo_user = self._create_user(RoleName.NGO, auth_id=ngo_sub)
        self._create_ngo(ngo_user)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Place"})
        # Assign to NGO
        self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo_sub),
        )
        # Valid transition: NGO Assigned -> Rescued
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}/status",
            headers=self._auth_header(ngo_sub),
            json={"status": "Rescued"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["data"]["status"], "Rescued")
        # Next valid: Rescued -> Under Treatment / Foster
        res2 = self.client.patch(
            f"/api/rescue-cases/{case.case_id}/status",
            headers=self._auth_header(ngo_sub),
            json={"status": "Under Treatment / Foster"},
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()["data"]["status"], "Under Treatment / Foster")

    def test_status_transition_invalid(self):
        ngo_sub = f"sub-ngo-{uuid.uuid4().hex[:6]}"
        ngo_user = self._create_user(RoleName.NGO, auth_id=ngo_sub)
        self._create_ngo(ngo_user)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Place"})
        # Assign the case to the NGO so the NGO is authorized
        assign_res = self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo_sub),
        )
        self.assertEqual(assign_res.status_code, 200)
        # Attempt illegal transition: NGO Assigned -> Under Review (not allowed)
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}/status",
            headers=self._auth_header(ngo_sub),
            json={"status": "Under Review"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid status transition", res.get_json()["message"].lower())

    def test_status_patch_unauthorized_wrong_ngo(self):
        # Two NGOs, case assigned to first, second tries to change status
        ngo1_sub = f"sub-ngo1-{uuid.uuid4().hex[:6]}"
        ngo1_user = self._create_user(RoleName.NGO, auth_id=ngo1_sub)
        self._create_ngo(ngo1_user)
        ngo2_sub = f"sub-ngo2-{uuid.uuid4().hex[:6]}"
        ngo2_user = self._create_user(RoleName.NGO, auth_id=ngo2_sub)
        self._create_ngo(ngo2_user)
        reporter_sub = f"sub-reporter-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=reporter_sub)
        case = self._create_rescue_case(reporter_sub, {"location": "Place"})
        # Assign to first NGO
        self.client.post(
            f"/api/rescue-cases/{case.case_id}/assign",
            headers=self._auth_header(ngo1_sub),
        )
        # Second NGO attempts status change
        res = self.client.patch(
            f"/api/rescue-cases/{case.case_id}/status",
            headers=self._auth_header(ngo2_sub),
            json={"status": "Rescued"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("permission", res.get_json()["message"].lower())

    def test_pagination_invalid(self):
        sub = f"sub-user-{uuid.uuid4().hex[:6]}"
        self._create_user(RoleName.USER, auth_id=sub)
        res = self.client.get("/api/rescue-cases?page=0", headers=self._auth_header(sub))
        self.assertEqual(res.status_code, 400)
        res2 = self.client.get("/api/rescue-cases?per_page=0", headers=self._auth_header(sub))
        self.assertEqual(res2.status_code, 400)
        res3 = self.client.get("/api/rescue-cases?page=abc", headers=self._auth_header(sub))
        self.assertEqual(res3.status_code, 400)

    def test_health_endpoint(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["status"], "success")
        self.assertIn("running", body["message"].lower())

    def test_migration_head(self):
        # Simple check that Flask-Migrate can report current head without error
        from flask import current_app
        with self.app.app_context():
            from flask_migrate import upgrade, migrate, stamp, init
            # 'current' command is not directly exposed; we just ensure migrations are importable
            self.assertIsNotNone(migrate)

if __name__ == "__main__":
    unittest.main()
