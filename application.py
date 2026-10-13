# WSGI entry point for AWS Elastic Beanstalk
# The repository root is added to PYTHONPATH by Elastic Beanstalk, but the Flask app lives in
# the ``backend/app`` package. To make the import work without requiring ``backend`` to be a
# Python package we prepend the ``backend`` directory to ``sys.path`` before importing.
import sys
import os

# Add the ``backend`` directory (relative to this file) to the module search path.
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_PATH = os.path.join(CURRENT_DIR, "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from app import create_app  # now resolvable because ``backend`` is on sys.path

# Elastic Beanstalk looks for the callable named ``application``.
application = create_app()
