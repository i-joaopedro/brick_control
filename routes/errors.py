from flask import Blueprint, render_template
from extensions import logger, db

bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('erros/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    logger.error(f'Server Error: {error}')
    db.session.rollback()
    return render_template('erros/500.html'), 500

@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template('erros/403.html'), 403
