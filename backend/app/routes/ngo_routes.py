"""
NGO Profile Routes.
"""

from flask import Blueprint, g, jsonify, request
from ..models.role import RoleName
from ..services.ngo_service import NGOService
from ..utils.auth_decorators import roles_required

ngo_bp = Blueprint("ngos", __name__, url_prefix="/ngos")


@ngo_bp.route("/me", methods=["GET"])
@roles_required(RoleName.NGO)
def get_current_ngo_profile():
    user = g.current_user
    ngo = user.ngo
    if not ngo:
        return jsonify({
            "status": "error",
            "message": "No NGO profile found for this user.",
        }), 404

    return jsonify({
        "status": "success",
        "data": NGOService.serialize_ngo(ngo),
    }), 200


@ngo_bp.route("", methods=["POST"])
@roles_required(RoleName.NGO)
def create_ngo_profile():
    user = g.current_user
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "status": "error",
            "message": "Request body must be a valid JSON object.",
        }), 400

    data, err_resp, status_code = NGOService.create_ngo(user, payload)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 201
