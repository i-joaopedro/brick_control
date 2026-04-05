"""
Ponto de entrada da aplicação Brick Control.
Cria o app Flask, configura extensões e registra blueprints.
"""
import os
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash

from extensions import db, migrate, csrf, limiter, login_manager, mail


def create_app(test_config=None):
    app = Flask(__name__)

    # ── Configuração ──────────────────────────
    _secret = os.environ.get('SECRET_KEY')
    _debug  = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    if not _secret:
        if _debug:
            _secret = 'dev-only-insecure-key'
        else:
            raise RuntimeError("SECRET_KEY não definida.")
    app.config['SECRET_KEY']                  = _secret
    app.config['SQLALCHEMY_DATABASE_URI']     = os.environ.get('DATABASE_URL', 'sqlite:///lego_pro.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER']               = os.path.join('static', 'uploads')
    app.config['MAX_CONTENT_LENGTH']          = 5 * 1024 * 1024
    app.config['WTF_CSRF_ENABLED']            = True
    app.config['PERMANENT_SESSION_LIFETIME']  = timedelta(hours=8)

    # Configuração de E-mail
    app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

    # Sobrescreve com config de teste, se fornecido
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s',
                        handlers=[logging.StreamHandler()])

    # ── Extensões ─────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from models import Usuario
        return db.session.get(Usuario, int(user_id))

    # ── Context processor ─────────────────────
    @app.context_processor
    def inject_globals():
        return {'now': datetime.now()}

    # ── Blueprints ────────────────────────────
    from routes.auth       import bp as auth_bp
    from routes.main       import bp as main_bp
    from routes.admin      import bp as admin_bp
    from routes.auxiliar   import bp as auxiliar_bp
    from routes.relatorios import bp as relatorios_bp
    from routes.errors import bp as errors_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auxiliar_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(errors_bp)

    @app.errorhandler(413)
    def too_large(e):
        flash('Arquivo muito grande. Limite: 5 MB.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    @app.errorhandler(429)
    def rate_limited(e):
        flash('Muitas tentativas. Aguarde um momento.', 'warning')
        return redirect(url_for('auth.login'))

    return app


app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug)
