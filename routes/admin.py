"""
Blueprint admin: dashboards, escolas, peças, modelos, unidades, usuários, etiquetas.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, abort, jsonify, current_app)

from extensions import db, logger
from models import (Usuario, Peca, KitModelo, ComposicaoKit, KitUnidade,
                    Escola, Conferencia, Role, StatusKit)
from services.dashboard_service import calcular_stats, calcular_ranking_perdas, get_cidades_data
from services.user_service import validar_senha
from forms.admin_forms import UsuarioForm, EscolaForm, PecaForm, ModeloForm, KitUnidadeForm
from flask_login import current_user
from helpers import (usuario_atual, escolas_do_usuario, login_required,
                     allowed_file, salvar_upload)

bp = Blueprint('admin', __name__)

# ─── DASHBOARDS ───────────────────────────────
@bp.route('/admin/dashboard')
@login_required(roles='admin')
def dashboard():
    cidade_filtro = request.args.get('cidade', '').strip()
    escolas_obj   = Escola.query.filter_by(ativo=True).order_by(Escola.cidade, Escola.nome).all()
    cidades       = sorted({e.cidade or 'Sem cidade' for e in escolas_obj})
    if cidade_filtro:
        nomes = [e.nome for e in escolas_obj if (e.cidade or 'Sem cidade') == cidade_filtro]
        unidades = KitUnidade.query.filter(KitUnidade.escola.in_(nomes)).all()
    else:
        unidades = KitUnidade.query.all()
    modelos = KitModelo.query.all()
    total, completos, incompletos, pendentes = calcular_stats(unidades)
    # Replace dictionary aggregation with service
    cidades_data = get_cidades_data(escolas_obj, unidades)
    return render_template('admin/dashboard.html',
                           modelos=modelos, unidades=unidades,
                           total=total, completos=completos,
                           incompletos=incompletos, pendentes=pendentes,
                           escolas_distintas=len({u.escola for u in unidades}),
                           cidades=cidades, cidades_data=dict(cidades_data),
                           cidade_filtro=cidade_filtro)


@bp.route('/pedagogo/dashboard')
@login_required(roles='pedagogo')
def dashboard_pedagogo():
    user   = usuario_atual()
    acesso = escolas_do_usuario(user)
    if acesso is None:
        unidades    = KitUnidade.query.all()
        escolas_obj = Escola.query.filter_by(ativo=True).order_by(Escola.nome).all()
    else:
        unidades    = KitUnidade.query.filter(KitUnidade.escola.in_(acesso)).all()
        escolas_obj = Escola.query.filter(Escola.nome.in_(acesso)).order_by(Escola.nome).all()
    total, completos, incompletos, pendentes = calcular_stats(unidades)
    kit_ids      = [u.id for u in unidades]
    ultimas_confs = []
    if kit_ids:
        ultimas_confs = (Conferencia.query
                         .filter(Conferencia.kit_unidade_id.in_(kit_ids))
                         .order_by(Conferencia.data_conferencia.desc())
                         .limit(10).all())
    return render_template('pedagogo/dashboard.html',
                           unidades=unidades, escolas_obj=escolas_obj,
                           total=total, completos=completos,
                           incompletos=incompletos, pendentes=pendentes,
                           ultimas_confs=ultimas_confs,
                           ranking_perdas=calcular_ranking_perdas(unidades))

# ─── USUÁRIOS ─────────────────────────────────
@bp.route('/admin/usuarios')
@login_required(roles='admin')
def gerenciar_usuarios():
    return render_template('admin/usuarios.html',
                           usuarios=Usuario.query.order_by(Usuario.username).all())


@bp.route('/admin/usuario/novo', methods=['GET', 'POST'])
@login_required(roles='admin')
def novo_usuario():
    escolas_lista = Escola.query.filter_by(ativo=True).order_by(Escola.nome).all()
    if request.method == 'POST':
        username      = request.form.get('username', '').strip()
        senha         = request.form.get('password', '')
        senha_confirm = request.form.get('password_confirm', '')
        role          = request.form.get('role', 'auxiliar')
        
        if not username or not senha:
            flash('Usuário e senha são obrigatórios.', 'danger')
            return redirect(url_for('admin.novo_usuario'))
        if senha != senha_confirm:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('admin.novo_usuario'))
            
        erro = validar_senha(senha)
        if erro:
            flash(erro, 'danger')
            return redirect(url_for('admin.novo_usuario'))
            
        if Usuario.query.filter_by(username=username).first():
            flash(f'O usuário "{username}" já existe.', 'danger')
            return redirect(url_for('admin.novo_usuario'))
            
        if role == 'pedagogo':
            sels  = request.form.getlist('escolas_pedagogo')
            escola = ', '.join(sels) if sels else 'Todas'
        else:
            escola = request.form.get('escola_unica', '').strip() or 'Todas'

        ativo = 'ativo' in request.form
        try:
            role_enum = Role(role)
        except ValueError:
            flash(f'Cargo inválido: {role}.', 'danger')
            return redirect(url_for('admin.novo_usuario'))
        novo = Usuario(username=username, role=role_enum, escola=escola, ativo=ativo)
        novo.set_password(senha)
        db.session.add(novo)
        db.session.commit()
        flash(f'Usuário {username} cadastrado!', 'success')
        return redirect(url_for('admin.gerenciar_usuarios'))
    return render_template('admin/form_usuario.html', usuario=None, escolas_lista=escolas_lista)


@bp.route('/admin/usuario/<int:uid>/editar', methods=['GET', 'POST'])
@login_required(roles='admin')
def editar_usuario(uid):
    user          = db.get_or_404(Usuario, uid)
    escolas_lista = Escola.query.filter_by(ativo=True).order_by(Escola.nome).all()
    if request.method == 'POST':
        role_str  = request.form.get('role', user.role.value)
        try:
            user.role = Role(role_str)
        except ValueError:
            flash(f'Cargo inválido: {role_str}.', 'danger')
            return redirect(url_for('admin.editar_usuario', uid=uid))
        if role_str == 'pedagogo':
            sels        = request.form.getlist('escolas_pedagogo')
            user.escola = ', '.join(sels) if sels else 'Todas'
        else:
            user.escola = request.form.get('escola_unica', '').strip() or 'Todas'

        user.ativo = 'ativo' in request.form
        nova_senha = request.form.get('nova_senha', '').strip()

        if nova_senha:
            if nova_senha != request.form.get('nova_senha_confirm', '').strip():
                flash('As senhas não coincidem.', 'danger')
                return redirect(url_for('admin.editar_usuario', uid=uid))
            erro = validar_senha(nova_senha)
            if erro:
                flash(erro, 'danger')
                return redirect(url_for('admin.editar_usuario', uid=uid))
            user.set_password(nova_senha)

        db.session.commit()
        flash(f'Usuário {user.username} atualizado!', 'success')
        return redirect(url_for('admin.gerenciar_usuarios'))
    return render_template('admin/form_usuario.html', usuario=user, escolas_lista=escolas_lista)


@bp.route('/admin/usuario/<int:uid>/toggle', methods=['POST'])
@login_required(roles='admin')
def toggle_usuario(uid):
    user = db.get_or_404(Usuario, uid)
    if user.id == current_user.id:
        flash('Você não pode desativar sua própria conta.', 'danger')
        return redirect(url_for('admin.gerenciar_usuarios'))
    user.ativo = not user.ativo
    db.session.commit()
    flash(f'Usuário {user.username} {"ativado" if user.ativo else "desativado"}.', 'info')
    return redirect(url_for('admin.gerenciar_usuarios'))


@bp.route('/admin/usuario/<int:uid>/deletar', methods=['POST'])
@login_required(roles='admin')
def deletar_usuario(uid):
    user = db.get_or_404(Usuario, uid)
    if user.id == current_user.id:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('admin.gerenciar_usuarios'))
    if user.role == Role.admin:
        if Usuario.query.filter_by(role=Role.admin).count() <= 1:
            flash('Não é possível excluir o único administrador.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuário "{username}" excluído.', 'success')
    return redirect(url_for('admin.gerenciar_usuarios'))

# ─── ESCOLAS ──────────────────────────────────
@bp.route('/admin/escolas')
@login_required(roles=['admin', 'pedagogo'])
def lista_escolas():
    user   = usuario_atual()
    acesso = escolas_do_usuario(user)
    if acesso:
        escolas_obj = Escola.query.filter(Escola.nome.in_(acesso)).order_by(Escola.nome).all()
    else:
        escolas_obj = Escola.query.order_by(Escola.nome).all()
    escolas_raw = db.session.query(
        KitUnidade.escola,
        db.func.count(KitUnidade.id).label('total'),
        db.func.sum(db.case((KitUnidade.status_atual == StatusKit.completo, 1), else_=0)).label('completos')
    ).group_by(KitUnidade.escola).all()
    stats = {e[0]: {'total': e[1], 'completos': e[2] or 0} for e in escolas_raw}
    return render_template('admin/lista_escolas.html', escolas_obj=escolas_obj, stats=stats)


@bp.route('/admin/escola/nova', methods=['GET', 'POST'])
@login_required(roles='admin')
def nova_escola():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Nome da escola é obrigatório.', 'danger')
            return redirect(url_for('admin.nova_escola'))
        if Escola.query.filter_by(nome=nome).first():
            flash(f'Escola "{nome}" já está cadastrada.', 'danger')
            return redirect(url_for('admin.nova_escola'))
        db.session.add(Escola(nome=nome,
                               cidade=request.form.get('cidade', '').strip(),
                               responsavel=request.form.get('responsavel', '').strip(),
                               telefone=request.form.get('telefone', '').strip()))
        db.session.commit()
        flash(f'Escola "{nome}" cadastrada!', 'success')
        return redirect(url_for('admin.lista_escolas'))
    return render_template('admin/form_escola.html', escola=None)


@bp.route('/admin/escola/<int:eid>/editar', methods=['GET', 'POST'])
@login_required(roles='admin')
def editar_escola(eid):
    escola = db.get_or_404(Escola, eid)
    if request.method == 'POST':
        nome_antigo = escola.nome
        escola.nome        = request.form.get('nome', escola.nome).strip()
        escola.cidade      = request.form.get('cidade', '').strip()
        escola.responsavel = request.form.get('responsavel', '').strip()
        escola.telefone    = request.form.get('telefone', '').strip()
        escola.ativo       = 'ativo' in request.form
        if escola.nome != nome_antigo:
            KitUnidade.query.filter_by(escola=nome_antigo).update({'escola': escola.nome})
            Usuario.query.filter_by(escola=nome_antigo).update({'escola': escola.nome})
        db.session.commit()
        flash('Escola atualizada!', 'success')
        return redirect(url_for('admin.lista_escolas'))
    return render_template('admin/form_escola.html', escola=escola)


@bp.route('/admin/escola/<int:eid>/deletar', methods=['POST'])
@login_required(roles='admin')
def deletar_escola(eid):
    escola = db.get_or_404(Escola, eid)
    if KitUnidade.query.filter_by(escola=escola.nome).count() > 0:
        flash('Não é possível deletar: existem kits vinculados.', 'danger')
        return redirect(url_for('admin.lista_escolas'))
    db.session.delete(escola)
    db.session.commit()
    flash(f'Escola "{escola.nome}" removida.', 'success')
    return redirect(url_for('admin.lista_escolas'))


@bp.route('/admin/escola/<path:nome_escola>/detalhe')
@login_required(roles=['admin', 'pedagogo'])
def detalhe_escola(nome_escola):
    user = usuario_atual()
    if user.role == 'pedagogo':
        acesso = escolas_do_usuario(user)
        if acesso and nome_escola not in acesso:
            abort(403)
    unidades   = KitUnidade.query.filter_by(escola=nome_escola).order_by(KitUnidade.identificador).all()
    escola_obj = Escola.query.filter_by(nome=nome_escola).first()
    modelos_kits = {}
    for u in unidades:
        modelos_kits.setdefault(u.modelo.nome if u.modelo else 'Sem modelo', []).append(u)
    total, completos, incompletos, pendentes = calcular_stats(unidades)
    return render_template('admin/detalhe_escola.html',
                           nome_escola=nome_escola, escola_obj=escola_obj,
                           unidades=unidades, modelos_kits=modelos_kits,
                           total=total, completos=completos,
                           incompletos=incompletos, pendentes=pendentes,
                           ranking=calcular_ranking_perdas(unidades))

# ─── PEÇAS ────────────────────────────────────
@bp.route('/admin/pecas')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def listar_pecas():
    page  = request.args.get('page', 1, type=int)
    pecas = Peca.query.order_by(Peca.nome).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/lista_pecas.html', pecas=pecas)


@bp.route('/admin/pecas/novo', methods=['GET', 'POST'])
@login_required(roles='admin')
def nova_peca():
    if request.method == 'POST':
        codigo  = request.form.get('codigo_lego', '').strip()
        nome    = request.form.get('nome', '').strip()
        arquivo = request.files.get('foto')
        if not codigo or not nome:
            flash('Código e nome são obrigatórios.', 'danger')
            return redirect(url_for('admin.nova_peca'))
        if Peca.query.filter_by(codigo_lego=codigo).first():
            flash(f'Código {codigo} já cadastrado.', 'danger')
            return redirect(url_for('admin.nova_peca'))
        if arquivo and arquivo.filename and not allowed_file(arquivo.filename):
            flash('Formato inválido. Use PNG, JPG ou JPEG.', 'danger')
            return redirect(url_for('admin.nova_peca'))
        filename = salvar_upload(arquivo, codigo, current_app.config['UPLOAD_FOLDER']) or 'sem-foto.png'
        db.session.add(Peca(codigo_lego=codigo, nome=nome, imagem_url=filename))
        db.session.commit()
        flash('Peça cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.listar_pecas'))
    return render_template('admin/form_peca.html', peca=None)


@bp.route('/admin/pecas/<int:pid>/editar', methods=['GET', 'POST'])
@login_required(roles='admin')
def editar_peca(pid):
    peca    = db.get_or_404(Peca, pid)
    if request.method == 'POST':
        peca.nome = request.form.get('nome', peca.nome).strip()
        arquivo   = request.files.get('foto')
        if arquivo and arquivo.filename:
            if not allowed_file(arquivo.filename):
                flash('Formato inválido.', 'danger')
                return redirect(url_for('admin.editar_peca', pid=pid))
            fn = salvar_upload(arquivo, peca.codigo_lego, current_app.config['UPLOAD_FOLDER'])
            if fn: peca.imagem_url = fn
        db.session.commit()
        flash('Peça atualizada!', 'success')
        return redirect(url_for('admin.listar_pecas'))
    return render_template('admin/form_peca.html', peca=peca)


@bp.route('/admin/pecas/<int:pid>/deletar', methods=['POST'])
@login_required(roles='admin')
def deletar_peca(pid):
    peca = db.get_or_404(Peca, pid)
    try:
        if peca.imagem_url and peca.imagem_url != 'sem-foto.png':
            caminho = Path(current_app.config['UPLOAD_FOLDER']) / peca.imagem_url
            if caminho.exists(): caminho.unlink()
        db.session.delete(peca)
        db.session.commit()
        flash(f'Peça {peca.codigo_lego} removida.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Não foi possível remover: peça está vinculada a kits.', 'danger')
        logger.error("Erro ao deletar peça %s: %s", pid, e)
    return redirect(url_for('admin.listar_pecas'))


# ─── MODELOS DE KIT ───────────────────────────
@bp.route('/admin/modelos')
@login_required(roles=['admin', 'pedagogo'])
def listar_modelos():
    return render_template('admin/lista_modelos.html', modelos=KitModelo.query.all())


@bp.route('/admin/modelo/novo', methods=['GET', 'POST'])
@login_required(roles='admin')
def novo_modelo():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(url_for('admin.novo_modelo'))
        arquivo  = request.files.get('foto')
        filename = salvar_upload(arquivo, f"kit_{nome.replace(' ', '_')}",
                                 current_app.config['UPLOAD_FOLDER']) or 'kit-default.png'
        novo = KitModelo(nome=nome, categoria=request.form.get('categoria', '').strip(),
                         foto_capa=filename)
        db.session.add(novo)
        db.session.commit()
        flash(f'Modelo "{nome}" criado!', 'success')
        return redirect(url_for('admin.gerenciar_composicao', modelo_id=novo.id))
    return render_template('admin/form_modelo.html', modelo=None)


@bp.route('/admin/modelo/<int:mid>/editar', methods=['GET', 'POST'])
@login_required(roles='admin')
def editar_modelo(mid):
    modelo = db.get_or_404(KitModelo, mid)
    if request.method == 'POST':
        modelo.nome      = request.form.get('nome', modelo.nome).strip()
        modelo.categoria = request.form.get('categoria', modelo.categoria).strip()
        arquivo = request.files.get('foto')
        fn = salvar_upload(arquivo, f"kit_{modelo.nome.replace(' ', '_')}",
                           current_app.config['UPLOAD_FOLDER'])
        if fn: modelo.foto_capa = fn
        db.session.commit()
        flash('Modelo atualizado!', 'success')
        return redirect(url_for('admin.listar_modelos'))
    return render_template('admin/form_modelo.html', modelo=modelo,
                           destino_voltar=url_for('admin.listar_modelos'))


@bp.route('/admin/modelo/<int:mid>/deletar', methods=['POST'])
@login_required(roles='admin')
def deletar_modelo(mid):
    modelo = db.get_or_404(KitModelo, mid)
    if modelo.unidades_reais:
        flash('Não é possível deletar: existem unidades físicas vinculadas.', 'danger')
        return redirect(url_for('admin.listar_modelos'))
    db.session.delete(modelo)
    db.session.commit()
    flash(f'Modelo "{modelo.nome}" removido.', 'success')
    return redirect(url_for('admin.listar_modelos'))


@bp.route('/admin/modelo/<int:modelo_id>/composicao', methods=['GET', 'POST'])
@login_required(roles='admin')
def gerenciar_composicao(modelo_id):
    modelo         = db.get_or_404(KitModelo, modelo_id)
    pecas_catalogo = Peca.query.order_by(Peca.nome).all()
    if request.method == 'POST':
        peca_id = request.form.get('peca_id')
        try:
            quantidade = int(request.form.get('quantidade', 1))
        except ValueError:
            flash('Quantidade inválida.', 'danger')
            return redirect(url_for('admin.gerenciar_composicao', modelo_id=modelo_id))
        if quantidade < 1:
            flash('Quantidade deve ser maior que zero.', 'danger')
            return redirect(url_for('admin.gerenciar_composicao', modelo_id=modelo_id))
        item = ComposicaoKit.query.filter_by(kit_modelo_id=modelo_id, peca_id=peca_id).first()
        if item:
            item.quantidade_esperada = quantidade
        else:
            db.session.add(ComposicaoKit(kit_modelo_id=modelo_id, peca_id=peca_id,
                                         quantidade_esperada=quantidade))
        db.session.commit()
        flash('Composição atualizada!', 'success')
        return redirect(url_for('admin.gerenciar_composicao', modelo_id=modelo_id))
    return render_template('admin/gerenciar_pecas.html', modelo=modelo, pecas_catalogo=pecas_catalogo)


@bp.route('/admin/composicao/remover/<int:item_id>', methods=['POST'])
@login_required(roles='admin')
def remover_item_composicao(item_id):
    item      = db.get_or_404(ComposicaoKit, item_id)
    modelo_id = item.kit_modelo_id
    db.session.delete(item)
    db.session.commit()
    flash('Peça removida do kit.', 'info')
    return redirect(url_for('admin.gerenciar_composicao', modelo_id=modelo_id))


@bp.route('/api/composicao/<int:item_id>/quantidade', methods=['POST'])
@login_required(roles='admin')
def ajax_quantidade_composicao(item_id):
    item  = db.get_or_404(ComposicaoKit, item_id)
    delta = request.get_json(silent=True, force=True) or {}
    acao  = delta.get('acao', '')
    if acao == 'incrementar':
        item.quantidade_esperada += 1
    elif acao == 'decrementar':
        if item.quantidade_esperada <= 1:
            return jsonify({'erro': 'Quantidade mínima é 1.'}), 400
        item.quantidade_esperada -= 1
    else:
        return jsonify({'erro': 'Ação inválida.'}), 400
    db.session.commit()
    return jsonify({'quantidade': item.quantidade_esperada, 'item_id': item_id})


# ─── UNIDADES FÍSICAS ─────────────────────────
@bp.route('/admin/unidades')
@login_required(roles=['admin', 'pedagogo'])
def listar_unidades():
    page          = request.args.get('page', 1, type=int)
    escola_filtro = request.args.get('escola', '')
    qry           = KitUnidade.query
    if escola_filtro: qry = qry.filter_by(escola=escola_filtro)
    unidades = qry.order_by(KitUnidade.escola, KitUnidade.identificador).paginate(
        page=page, per_page=50, error_out=False)
    escolas = [e[0] for e in db.session.query(KitUnidade.escola).distinct().all()]
    return render_template('admin/unidades.html', unidades=unidades,
                           escolas=escolas, escola_filtro=escola_filtro)


@bp.route('/admin/unidade/novo', methods=['GET', 'POST'])
@login_required(roles=['admin', 'auxiliar'])
def nova_unidade():
    user          = usuario_atual()
    modelos       = KitModelo.query.all()
    escolas_lista = Escola.query.filter_by(ativo=True).order_by(Escola.nome).all()
    if request.method == 'POST':
        identificador = request.form.get('identificador', '').strip()
        escola = user.escola if user.role == 'auxiliar' else request.form.get('escola', '').strip()
        modelo_id = request.form.get('modelo_id')
        if not identificador or not escola or not modelo_id:
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('admin.nova_unidade'))
        db.session.add(KitUnidade(identificador=identificador, escola=escola,
                                  kit_modelo_id=modelo_id, status_atual=StatusKit.pendente))
        db.session.commit()
        flash(f'Unidade {identificador} criada!', 'success')
        destino = url_for('auxiliar.conferencias_auxiliar') if user.role == 'auxiliar' else url_for('admin.listar_unidades')
        return redirect(destino)
    return render_template('admin/form_unidade.html', modelos=modelos,
                           escolas_lista=escolas_lista, unidade=None,
                           is_auxiliar=(user.role == 'auxiliar'))


@bp.route('/admin/unidade/<int:uid>/editar', methods=['GET', 'POST'])
@login_required(roles=['admin', 'auxiliar'])
def editar_unidade(uid):
    unidade = db.get_or_404(KitUnidade, uid)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        flash('Você só pode editar unidades da sua escola.', 'danger')
        return redirect(url_for('auxiliar.conferencias_auxiliar'))
    modelos       = KitModelo.query.all()
    escolas_lista = Escola.query.filter_by(ativo=True).order_by(Escola.nome).all()
    if request.method == 'POST':
        unidade.identificador = request.form.get('identificador', '').strip()
        if user.role != 'auxiliar':
            unidade.escola = request.form.get('escola', '').strip()
        unidade.kit_modelo_id = request.form.get('modelo_id', unidade.kit_modelo_id)
        db.session.commit()
        flash('Unidade atualizada!', 'success')
        destino = url_for('auxiliar.conferencias_auxiliar') if user.role == 'auxiliar' else url_for('admin.listar_unidades')
        return redirect(destino)
    destino_voltar = url_for('auxiliar.conferencias_auxiliar') if user.role == 'auxiliar' else url_for('admin.listar_unidades')
    return render_template('admin/form_unidade.html', modelos=modelos,
                           escolas_lista=escolas_lista, unidade=unidade,
                           destino_voltar=destino_voltar, is_auxiliar=(user.role == 'auxiliar'))


@bp.route('/admin/unidade/<int:uid>/deletar', methods=['POST'])
@login_required(roles='admin')
def deletar_unidade(uid):
    unidade = db.get_or_404(KitUnidade, uid)
    db.session.delete(unidade)
    db.session.commit()
    flash(f'Unidade {unidade.identificador} removida.', 'success')
    return redirect(url_for('admin.listar_unidades'))


# ─── ETIQUETAS ────────────────────────────────
@bp.route('/admin/etiquetas')
@login_required(roles='admin')
def etiquetas_admin():
    escolas = [e[0] for e in db.session.query(KitUnidade.escola).distinct().all()]
    return render_template('admin/etiquetas.html', unidades=KitUnidade.query.all(), escolas=escolas)
