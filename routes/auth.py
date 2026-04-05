"""
Blueprint de autenticação: login, logout, perfil.
"""
import re
from datetime import datetime, timezone

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from flask_login import current_user, login_user, logout_user

from extensions import db, limiter
from models import Usuario, Role
from helpers import usuario_atual, login_required
from forms.auth_forms import LoginForm
from services.user_service import validar_senha

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data.strip()).first()
        if user and user.ativo and user.check_password(form.password.data):
            login_user(user, remember=False)
            user.ultimo_login = datetime.now(timezone.utc)
            db.session.commit()
            dest = {'admin': 'admin.dashboard', 'pedagogo': 'admin.dashboard_pedagogo',
                    'auxiliar': 'auxiliar.dashboard_auxiliar'}.get(user.role.value, 'auth.login')
            flash(f'Bem-vindo, {user.nome_display}!', 'success')
            return redirect(url_for(dest))
        
        # LOGS DE FALHA (VISÍVEIS PARA NÓS)
        if not user:
            print(f"DEBUG: Login falhou - Usuário '{form.username.data}' não encontrado.")
        elif not user.ativo:
            print(f"DEBUG: Login falhou - Usuário '{user.username}' está inativo.")
        else:
            print(f"DEBUG: Login falhou - Senha incorreta para o usuário '{user.username}'.")
            
        flash('Usuário ou senha inválidos.', 'danger')
    elif request.method == 'POST':
        # CASO DE ERRO DE VALIDAÇÃO OU CSRF
        print(f"DEBUG: Login falhou - Erros de formulário: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'danger')
    return render_template('login.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/perfil', methods=['GET', 'POST'])
@login_required()
def perfil():
    user = usuario_atual()
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'dados':
            nome  = request.form.get('nome_exibicao', '').strip()
            email = request.form.get('email', '').strip()
            if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                flash('E-mail inválido.', 'danger')
            else:
                user.nome_exibicao = nome or None
                user.email         = email or None
                db.session.commit()
                flash('Perfil atualizado!', 'success')
        elif acao == 'senha':
            senha_atual  = request.form.get('senha_atual', '')
            nova         = request.form.get('nova_senha', '')
            confirmacao  = request.form.get('confirmacao', '')
            if not user.check_password(senha_atual):
                flash('Senha atual incorreta.', 'danger')
            elif nova != confirmacao:
                flash('As senhas não coincidem.', 'danger')
            else:
                erro = validar_senha(nova)
                if erro:
                    flash(erro, 'danger')
                else:
                    user.set_password(nova)
                    db.session.commit()
                    flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('auth.perfil'))
    return render_template('perfil.html', user=user)
