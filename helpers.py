"""
Funções auxiliares reutilizadas por múltiplos blueprints.
"""
from pathlib import Path
import re
from functools import wraps

from flask import session, redirect, url_for, flash, abort, request as flask_request
from werkzeug.utils import secure_filename
from flask_login import current_user, logout_user

from extensions import db, logger
from models import (Usuario, Peca, KitUnidade, Conferencia,
                    ConferenciaDetalhe, StatusKit)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


# ─────────────────────────────────────────────
#  AUTENTICAÇÃO / SESSÃO
# ─────────────────────────────────────────────
def usuario_atual():
    return current_user if current_user.is_authenticated else None


def escolas_do_usuario(user):
    if not user or user.escola in (None, '', 'Todas'):
        return None
    return [e.strip() for e in user.escola.split(',')]


def login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            user = current_user
            if not user.ativo:
                logout_user()
                flash('Conta desativada ou não encontrada.', 'danger')
                return redirect(url_for('auth.login'))
            if roles:
                allowed = [roles] if isinstance(roles, str) else list(roles)
                # Role can be Enum or str. Check both.
                role_val = getattr(user.role, 'value', user.role)
                if role_val not in allowed and user.role not in allowed:
                    logger.warning("Acesso negado: user=%s role=%s tentou %s",
                                   user.username, user.role, flask_request.path)
                    abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator





# ─────────────────────────────────────────────
#  ARQUIVOS
# ─────────────────────────────────────────────
def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)


def salvar_upload(arquivo, nome_base, upload_folder):
    """Salva arquivo de upload e retorna o filename, ou None se inválido."""
    if not arquivo or not arquivo.filename:
        return None
    if not allowed_file(arquivo.filename):
        return None
    ext = arquivo.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"{nome_base}.{ext}")
    
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)
    arquivo.save(str(upload_path / filename))
    return filename


# ─────────────────────────────────────────────
#  CÁLCULOS
# ─────────────────────────────────────────────



def _filtrar_detalhes(detalhes, modo):
    if modo == 'faltantes':
        return [d for d in detalhes
                if d.quantidade_encontrada < d.quantidade_esperada_na_epoca]
    return list(detalhes)


def _modo_valido(modo):
    return modo if modo in ('completo', 'faltantes') else 'completo'
