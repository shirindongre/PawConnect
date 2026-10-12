"""
User Profile Routes.
"""

from flask import Blueprint, g, jsonify, request
from ..services.user_service import UserService
from ..utils.auth_decorators import cognito_required

user_bp = Blueprint("users", __name__, url_prefix="/users")


@user_bp.route("/me", methods=["GET"])
@cognito_required(require_pawconnect_user=True)
def get_current_user_profile():
    user = g.current_user
    return jsonify({
        "status": "success",
        "data": UserService.serialize_user(user),
    }), 200


@user_bp.route("/me", methods=["PATCH"])
@cognito_required(require_pawconnect_user=True)
def update_current_user_profile():
    user = g.current_user
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "status": "error",
            "message": "Request body must be a valid JSON object.",
        }), 400

    data, err_resp, status_code = UserService.update_user_profile(user, payload)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 200
