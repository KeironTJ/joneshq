from flask import Blueprint

bp = Blueprint('rewards', __name__)

from app.rewards import routes
