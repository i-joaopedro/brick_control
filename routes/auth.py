"""
Blueprint de autenticação: login, logout, perfil.
"""
import re
from datetime import datetime, timezone

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app)
from flask_login import current_user, login_user, logout_user
from flask_mail import Message

from extensions import db, limiter, mail
from models import Usuario, Role
from helpers import usuario_atual, login_required
from forms.auth_forms import LoginForm, RequestResetForm, ResetPasswordForm
from services.user_service import validar_senha

bp = Blueprint('auth', __name__)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Recuperação de Senha - Brick Control',
                  sender=current_app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    
    # Link completo para o reset
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    
    msg.body = f'''Para redefinir sua senha no Brick Control, clique no link abaixo:

{reset_url}

Se você não solicitou esta alteração, ignore este e-mail.
O link expirará em 30 minutos.
'''
    # Versão HTML do e-mail
    msg.html = render_template('auth/email_reset.html', user=user, reset_url=reset_url)
    mail.send(msg)


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        # Busca por username OU email
        user = Usuario.query.filter(
            (Usuario.username == identifier) | (Usuario.email == identifier)
        ).first()
        
        if user and user.ativo and user.check_password(form.password.data):
            login_user(user, remember=False)
            user.ultimo_login = datetime.now(timezone.utc)
            db.session.commit()
            dest = {'admin': 'admin.dashboard', 'pedagogo': 'admin.dashboard_pedagogo',
                    'auxiliar': 'auxiliar.dashboard_auxiliar'}.get(user.role.value, 'auth.login')
            flash(f'Bem-vindo, {user.nome_display}!', 'success')
            return redirect(url_for(dest))
        
        flash('Usuário/E-mail ou senha inválidos.', 'danger')
    return render_template('login.html', form=form)


@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data).first()
        if user:
            try:
                send_reset_email(user)
                flash('Um e-mail foi enviado com instruções para redefinir sua senha.', 'info')
                return redirect(url_for('auth.login'))
            except Exception as e:
                print(f"ERRO AO ENVIAR E-MAIL: {e}")
                flash('Erro ao enviar e-mail. Verifique a configuração do servidor SMTP.', 'danger')
    return render_template('auth/reset_request.html', title='Recuperar Senha', form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = Usuario.verify_reset_token(token)
    if user is None:
        flash('O link de recuperação é inválido ou expirou.', 'warning')
        return redirect(url_for('auth.reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Sua senha foi alterada! Você já pode fazer login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', title='Nova Senha', form=form)


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
