"""
Instâncias das extensões Flask — importadas por app.py e pelos blueprints.
Separadas para evitar imports circulares.
"""
from logging import getLogger
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail

db      = SQLAlchemy()
migrate = Migrate()
csrf    = CSRFProtect()
limiter = Limiter(get_remote_address, default_limits=[], storage_uri='memory://')
login_manager = LoginManager()
mail    = Mail()
logger  = getLogger(__name__)
