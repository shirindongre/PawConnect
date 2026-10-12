"""
Animal Listing Routes.
"""

from flask import Blueprint, g, jsonify, request
from ..models import Animal
from ..models.role import RoleName
from ..services.animal_service import AnimalService
from ..utils.auth_decorators import roles_required

animal_bp = Blueprint("animals", __name__, url_prefix="/animals")


@animal_bp.route("", methods=["GET"])
def list_animals():
    page = request.args.get("page")
    per_page = request.args.get("per_page")
    data, err_resp, status_code = AnimalService.list_public_animals(page, per_page)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 200


@animal_bp.route("/<int:animal_id>", methods=["GET"])
def get_animal(animal_id: int):
    data, err_resp, status_code = AnimalService.get_animal_by_id(animal_id)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 200


@animal_bp.route("", methods=["POST"])
@roles_required(RoleName.NGO)
def create_animal():
    user = g.current_user
    ngo = user.ngo
    if not ngo:
        return jsonify({
            "status": "error",
            "message": "No NGO profile found for this user.",
        }), 404

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "status": "error",
            "message": "Request body must be a valid JSON object.",
        }), 400

    data, err_resp, status_code = AnimalService.create_animal(ngo, payload)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 201


@animal_bp.route("/<int:animal_id>", methods=["PATCH"])
@roles_required(RoleName.NGO)
def update_animal(animal_id: int):
    user = g.current_user
    ngo = user.ngo
    if not ngo:
        return jsonify({
            "status": "error",
            "message": "No NGO profile found for this user.",
        }), 404

    animal = Animal.query.get(animal_id)
    if not animal:
        return jsonify({
            "status": "error",
            "message": "Animal not found.",
        }), 404

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "status": "error",
            "message": "Request body must be a valid JSON object.",
        }), 400

    data, err_resp, status_code = AnimalService.update_animal(animal, ngo, payload)
    if err_resp:
        return jsonify(err_resp), status_code

    return jsonify({
        "status": "success",
        "data": data,
    }), 200


@animal_bp.route("/<int:animal_id>", methods=["DELETE"])
@roles_required(RoleName.NGO)
def delete_animal(animal_id: int):
    user = g.current_user
    ngo = user.ngo
    if not ngo:
        return jsonify({
            "status": "error",
            "message": "No NGO profile found for this user.",
        }), 404

    animal = Animal.query.get(animal_id)
    if not animal:
        return jsonify({
            "status": "error",
            "message": "Animal not found.",
        }), 404

    success, err_resp, status_code = AnimalService.delete_animal(animal, ngo)
    if err_resp:
        return jsonify(err_resp), status_code

    # 204 No Content has empty response body
    return "", 204
