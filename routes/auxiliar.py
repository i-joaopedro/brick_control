"""
Blueprint auxiliar: conferências, histórico, comparar, etiquetas.
"""
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort)

from extensions import db
from models import (KitUnidade, Conferencia, ConferenciaDetalhe,
                    StatusKit, StatusConferencia)
from helpers import (usuario_atual, escolas_do_usuario, login_required)
from services.dashboard_service import calcular_stats, calcular_ranking_perdas

bp = Blueprint('auxiliar', __name__)


@bp.route('/auxiliar/dashboard')
@login_required(roles='auxiliar')
def dashboard_auxiliar():
    user         = usuario_atual()
    minha_escola = user.escola or ''
    unidades     = KitUnidade.query.filter_by(escola=minha_escola).all()
    completos    = sum(1 for u in unidades if u.status_atual == StatusKit.completo)
    incompletos  = len(unidades) - completos
    return render_template('auxiliar/dashboard.html',
                           unidades=unidades, escola=minha_escola,
                           completos=completos, incompletos=incompletos)


@bp.route('/auxiliar/conferencias')
@login_required(roles='auxiliar')
def conferencias_auxiliar():
    user     = usuario_atual()
    unidades = KitUnidade.query.filter_by(escola=user.escola).order_by(KitUnidade.identificador).all()
    total, completos, incompletos, pendentes = calcular_stats(unidades)
    total_perdidas = sum(
        abs(d.quantidade_encontrada - d.quantidade_esperada_na_epoca)
        for u in unidades
        for d in (u.ultima_conferencia.detalhes if u.ultima_conferencia else [])
        if d.quantidade_encontrada < d.quantidade_esperada_na_epoca
    )
    return render_template('auxiliar/conferencias.html',
                           unidades=unidades, escola=user.escola,
                           total=total, completos=completos,
                           incompletos=incompletos, pendentes=pendentes,
                           total_perdidas=total_perdidas)


@bp.route('/conferir/<int:kit_id>', methods=['GET', 'POST'])
@login_required(roles=['auxiliar', 'admin', 'pedagogo'])
def conferir_kit(kit_id):
    unidade = db.get_or_404(KitUnidade, kit_id)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        abort(403)
    if not unidade.modelo:
        flash('Este kit não possui modelo vinculado. Edite o kit e associe um modelo antes de conferir.', 'danger')
        destino = url_for('auxiliar.conferencias_auxiliar') if user.role == 'auxiliar' else url_for('admin.listar_unidades')
        return redirect(destino)
    itens = unidade.modelo.pecas_obrigatorias
    if request.method == 'POST':
        nova_conf = Conferencia(
            kit_unidade_id=kit_id,
            responsavel=user.username,
            observacoes=request.form.get('observacoes', '').strip())
        db.session.add(nova_conf)
        todas_completas = True
        for item in itens:
            try:
                qtd = int(request.form.get(f'peca_{item.peca.id}', 0))
            except ValueError:
                qtd = 0
            obs = request.form.get(f'obs_{item.peca.id}', '').strip() or None
            if qtd < item.quantidade_esperada: todas_completas = False
            db.session.add(ConferenciaDetalhe(
                conferencia=nova_conf, peca_id=item.peca.id,
                quantidade_esperada_na_epoca=item.quantidade_esperada,
                quantidade_encontrada=qtd, observacao_peca=obs))
        unidade.status_atual       = StatusKit.completo if todas_completas else StatusKit.incompleto
        nova_conf.status_resultado = StatusConferencia.completo if todas_completas else StatusConferencia.incompleto
        db.session.commit()
        flash(f'Conferência salva! Status: {unidade.status_atual.value}', 'success')
        if user.role == 'auxiliar':
            return redirect(url_for('auxiliar.conferencias_auxiliar'))
        return redirect(url_for('auxiliar.historico_kit_auxiliar', kit_id=kit_id))
    return render_template('auxiliar/conferir.html', unidade=unidade, itens=itens)


@bp.route('/auxiliar/kit/<int:kit_id>/historico')
@login_required(roles=['auxiliar', 'admin', 'pedagogo'])
def historico_kit_auxiliar(kit_id):
    unidade = db.get_or_404(KitUnidade, kit_id)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        abort(403)
    conferencias = (Conferencia.query.filter_by(kit_unidade_id=kit_id)
                    .order_by(Conferencia.data_conferencia.desc()).all())
    labels_graf, valores_graf = [], []
    for c in reversed(conferencias):
        labels_graf.append(c.data_conferencia.strftime('%d/%m/%y'))
        esp = sum(d.quantidade_esperada_na_epoca for d in c.detalhes)
        enc = sum(d.quantidade_encontrada for d in c.detalhes)
        valores_graf.append(round(enc / esp * 100, 1) if esp else 100.0)
    tendencia_pecas = []
    if len(conferencias) >= 2:
        mapa = {d.peca_id: d.quantidade_encontrada for d in conferencias[-1].detalhes}
        for d in conferencias[0].detalhes:
            antes = mapa.get(d.peca_id)
            if antes is not None and d.peca:
                diff = d.quantidade_encontrada - antes
                tendencia_pecas.append({'nome': d.peca.nome, 'codigo': d.peca.codigo_lego,
                                        'antes': antes, 'depois': d.quantidade_encontrada, 'diff': diff})
        tendencia_pecas.sort(key=lambda x: x['diff'])
    return render_template('auxiliar/historico_kit.html',
                           unidade=unidade, conferencias=conferencias,
                           labels_graf=labels_graf, valores_graf=valores_graf,
                           tendencia_pecas=tendencia_pecas)


@bp.route('/auxiliar/comparar')
@login_required(roles=['auxiliar', 'admin', 'pedagogo'])
def comparar_kits():
    user = usuario_atual()
    if user.role == 'auxiliar':
        unidades = KitUnidade.query.filter_by(escola=user.escola).order_by(KitUnidade.identificador).all()
        escola   = user.escola
    else:
        escola   = request.args.get('escola', '')
        unidades = (KitUnidade.query.filter_by(escola=escola).order_by(KitUnidade.identificador).all()
                    if escola else KitUnidade.query.order_by(KitUnidade.identificador).all())

    # Carrega todas as conferências de uma vez, evitando N queries
    kit_ids = [u.id for u in unidades]
    todas_confs = (Conferencia.query
                   .filter(Conferencia.kit_unidade_id.in_(kit_ids))
                   .order_by(Conferencia.kit_unidade_id, Conferencia.data_conferencia.asc())
                   .all()) if kit_ids else []

    # Agrupa por kit
    from collections import defaultdict
    confs_por_kit = defaultdict(list)
    for c in todas_confs:
        confs_por_kit[c.kit_unidade_id].append(c)

    datasets, todas_labels = [], set()
    for u in unidades:
        confs = confs_por_kit.get(u.id, [])
        if not confs:
            continue
        pontos = {}
        for c in confs:
            label = c.data_conferencia.strftime('%d/%m/%y')
            todas_labels.add(label)
            esp = sum(d.quantidade_esperada_na_epoca for d in c.detalhes)
            enc = sum(d.quantidade_encontrada for d in c.detalhes)
            pontos[label] = round(enc / esp * 100, 1) if esp else 100.0
        datasets.append({'id': u.id, 'nome': u.identificador,
                         'pontos': pontos,
                         'status': u.status_atual.value if u.status_atual else '',
                         'saude': u.saude_percentual})

    labels_ord    = sorted(todas_labels, key=lambda s: datetime.strptime(s, '%d/%m/%y'))
    escolas_lista = [e[0] for e in db.session.query(KitUnidade.escola).distinct().all()]
    return render_template('auxiliar/comparar.html',
                           unidades=unidades, datasets=datasets,
                           labels_ord=labels_ord,
                           ranking_perdas=calcular_ranking_perdas(unidades, top=15),
                           escola=escola, escolas_lista=escolas_lista)


@bp.route('/auxiliar/etiquetas')
@login_required(roles=['auxiliar', 'admin'])
def etiquetas_auxiliar():
    user = usuario_atual()
    if user.role == 'auxiliar':
        kits   = KitUnidade.query.filter_by(escola=user.escola).all()
        escola = user.escola
    else:
        escola_filtro = request.args.get('escola', '')
        kits   = (KitUnidade.query.filter_by(escola=escola_filtro).all()
                  if escola_filtro else KitUnidade.query.all())
        escola = escola_filtro or 'Todas'
    return render_template('auxiliar/etiquetas_print.html', kits=kits, escola=escola)
