"""
Routes Blueprint Registry.
"""

from flask import Blueprint

# Central API blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")

from .user_routes import user_bp
from .ngo_routes import ngo_bp
from .animal_routes import animal_bp
from .rescue_case_routes import rescue_bp

api_bp.register_blueprint(user_bp)
api_bp.register_blueprint(ngo_bp)
api_bp.register_blueprint(animal_bp)
api_bp.register_blueprint(rescue_bp)
