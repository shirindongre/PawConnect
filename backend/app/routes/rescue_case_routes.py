"""
Rescue Case API routes – Batch 2A.
"""

from flask import Blueprint, g, jsonify, request
from ..models.role import RoleName
from ..models.rescue_case import RescueCase
from ..services.rescue_case_service import RescueCaseService
from ..utils.auth_decorators import cognito_required, roles_required

rescue_bp = Blueprint("rescue_cases", __name__, url_prefix="/rescue-cases")
rescue_bp.strict_slashes = False

# 1. POST /api/rescue-cases
@rescue_bp.route("/", methods=["POST"], strict_slashes=False)
@cognito_required(require_pawconnect_user=True)
def create_rescue_case():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "Request body must be a valid JSON object."}), 400
    data, err_resp, status = RescueCaseService.create_case(payload)
    if err_resp:
        return jsonify(err_resp), status
    return jsonify({"status": "success", "data": data}), status

# 2. GET /api/rescue-cases (list)
@rescue_bp.route("", methods=["GET"])
@cognito_required(require_pawconnect_user=True)
def list_rescue_cases():
    page = request.args.get("page")
    per_page = request.args.get("per_page")
    data, err_resp, status = RescueCaseService.list_cases(page, per_page)
    if err_resp:
        return jsonify(err_resp), status
    return jsonify({"status": "success", "data": data}), status

# Helper: visibility check for a single case object
def _can_view_case(user, case_obj):
    role = user.role.role_name if user.role else None
    if role == RoleName.NGO:
        # NGOs must have a profile (decorator ensures auth, but profile may be missing)
        ngo = getattr(user, "ngo", None)
        if ngo is None:
            return False, ("No NGO profile found for this user.", 404)
        # NGOs may view unassigned cases or those assigned to their own NGO
        if case_obj.assigned_ngo is None or case_obj.assigned_ngo == ngo.ngo_id:
            return True, None
        return False, ("You do not have permission to view this rescue case.", 403)
    else:
        # Regular users can view only cases they reported
        if case_obj.reported_by == user.user_id:
            return True, None
        return False, ("You do not have permission to view this rescue case.", 403)

# 3. GET /api/rescue-cases/<int:case_id>
@rescue_bp.route("/<int:case_id>", methods=["GET"])
@cognito_required(require_pawconnect_user=True)
def get_rescue_case(case_id: int):
    case_dict, err_resp, status = RescueCaseService.get_case(case_id)
    if err_resp:
        return jsonify(err_resp), status
    # Retrieve the ORM object for visibility checking
    orm_case = RescueCase.query.get(case_id)
    can_view, err = _can_view_case(g.current_user, orm_case)
    if not can_view:
        message, code = err
        return jsonify({"status": "error", "message": message}), code
    return jsonify({"status": "success", "data": case_dict}), 200

# 4. PATCH /api/rescue-cases/<int:case_id>
@rescue_bp.route("/<int:case_id>", methods=["PATCH"])
@cognito_required(require_pawconnect_user=True)
def update_rescue_case(case_id: int):
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "Request body must be a valid JSON object."}), 400
    case_obj = RescueCase.query.get(case_id)
    if not case_obj:
        return jsonify({"status": "error", "message": "Rescue case not found."}), 404
    data, err_resp, status = RescueCaseService.update_case(case_obj, payload)
    if err_resp:
        return jsonify(err_resp), status
    return jsonify({"status": "success", "data": data}), status

# 5. POST /api/rescue-cases/<int:case_id>/assign
@rescue_bp.route("/<int:case_id>/assign", methods=["POST"])
@roles_required(RoleName.NGO)
def assign_rescue_case(case_id: int):
    case_obj = RescueCase.query.get(case_id)
    if not case_obj:
        return jsonify({"status": "error", "message": "Rescue case not found."}), 404
    data, err_resp, status = RescueCaseService.assign_case(case_obj)
    if err_resp:
        return jsonify(err_resp), status
    return jsonify({"status": "success", "message": "Rescue case successfully assigned to NGO.", "data": data}), status

# 6. PATCH /api/rescue-cases/<int:case_id>/status
@rescue_bp.route("/<int:case_id>/status", methods=["PATCH"])
@cognito_required(require_pawconnect_user=True)
def update_rescue_case_status(case_id: int):
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "Request body must be a valid JSON object."}), 400
    case_obj = RescueCase.query.get(case_id)
    if not case_obj:
        return jsonify({"status": "error", "message": "Rescue case not found."}), 404
    data, err_resp, status = RescueCaseService.update_status(case_obj, payload)
    if err_resp:
        return jsonify(err_resp), status
    return jsonify({"status": "success", "data": data}), status
