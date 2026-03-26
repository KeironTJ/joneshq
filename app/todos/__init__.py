from flask import Blueprint

bp = Blueprint('todos', __name__)

from app.todos import routes
