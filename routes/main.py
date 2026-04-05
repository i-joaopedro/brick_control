"""
Blueprint principal: index, busca global, scan QR, pendentes, exportação CSV.
"""
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO

from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, jsonify, Response, abort)
from flask_login import current_user

from extensions import db
from models import (KitUnidade, Peca, Escola, Conferencia, StatusKit)
from helpers import (usuario_atual, escolas_do_usuario, login_required)
from services.dashboard_service import calcular_stats

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    dest = {
        'admin':    'admin.dashboard',
        'pedagogo': 'admin.dashboard_pedagogo',
        'auxiliar': 'auxiliar.dashboard_auxiliar',
    }.get(role, 'auth.login')
    return redirect(url_for(dest))


@bp.route('/busca')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def busca_global():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'kits': [], 'pecas': [], 'escolas': []})
    user   = usuario_atual()
    acesso = escolas_do_usuario(user)
    termo  = f'%{q}%'
    qry_kit = KitUnidade.query.filter(
        db.or_(KitUnidade.identificador.ilike(termo), KitUnidade.escola.ilike(termo)))
    if user.role == 'auxiliar':
        qry_kit = qry_kit.filter_by(escola=user.escola)
    elif acesso:
        qry_kit = qry_kit.filter(KitUnidade.escola.in_(acesso))
    kits   = qry_kit.limit(8).all()
    pecas  = Peca.query.filter(
        db.or_(Peca.nome.ilike(termo), Peca.codigo_lego.ilike(termo))).limit(6).all()
    escolas = []
    if user.role in ('admin', 'pedagogo'):
        qry_e = Escola.query.filter(Escola.nome.ilike(termo))
        if acesso: qry_e = qry_e.filter(Escola.nome.in_(acesso))
        escolas = qry_e.limit(5).all()
    return jsonify({
        'kits':   [{'id': u.id, 'nome': u.identificador, 'escola': u.escola,
                    'status': u.status_atual.value if u.status_atual else '',
                    'url': url_for('auxiliar.historico_kit_auxiliar', kit_id=u.id)} for u in kits],
        'pecas':  [{'id': p.id, 'nome': p.nome, 'codigo': p.codigo_lego,
                    'url': url_for('admin.listar_pecas')} for p in pecas],
        'escolas':[{'id': e.id, 'nome': e.nome,
                    'url': url_for('admin.detalhe_escola', nome_escola=e.nome)} for e in escolas],
    })


@bp.route('/scan')
@login_required(roles=['auxiliar', 'admin', 'pedagogo'])
def scan_qr():
    return render_template('auxiliar/scan_qr.html')


@bp.route('/qr/<int:kit_id>')
@login_required(roles=['auxiliar', 'admin', 'pedagogo'])
def qr_redirect(kit_id):
    unidade = db.get_or_404(KitUnidade, kit_id)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        abort(403)
    return redirect(url_for('auxiliar.conferir_kit', kit_id=kit_id))


@bp.route('/pendentes')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def conferencias_pendentes():
    user          = usuario_atual()
    dias          = int(request.args.get('dias', 30))
    cidade_filtro = request.args.get('cidade', '').strip()

    if user.role == 'auxiliar':
        unidades = KitUnidade.query.filter_by(escola=user.escola).all()
    else:
        acesso   = escolas_do_usuario(user)
        unidades = (KitUnidade.query.filter(KitUnidade.escola.in_(acesso)).all()
                    if acesso else KitUnidade.query.all())

    if cidade_filtro and user.role != 'auxiliar':
        escolas_cidade = {e.nome for e in Escola.query.filter_by(cidade=cidade_filtro).all()}
        unidades = [u for u in unidades if u.escola in escolas_cidade]

    limite_naive = datetime.now() - timedelta(days=dias)
    nunca, atrasados, ok = [], [], []
    for u in unidades:
        uc = u.ultima_conferencia
        if not uc:
            nunca.append(u)
        else:
            dt = uc.data_conferencia
            dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
            if dt_naive < limite_naive:
                atrasados.append({'unidade': u, 'dias': (datetime.now() - dt_naive).days})
            else:
                ok.append(u)
    atrasados.sort(key=lambda x: x['dias'], reverse=True)

    def _agrupar(lista):
        grupos = defaultdict(list)
        for item in lista:
            u = item if isinstance(item, KitUnidade) else item['unidade']
            grupos[u.escola].append(item)
        return dict(sorted(grupos.items()))

    cidades = []
    if user.role != 'auxiliar':
        todas_escolas = {u.escola for u in unidades}
        cidades = sorted({e.cidade for e in Escola.query.filter(
            Escola.nome.in_(todas_escolas)).all() if e.cidade})

    escola_cidade = {e.nome: e.cidade or '' for e in Escola.query.all()}

    return render_template('pendentes.html',
                           nunca=nunca, atrasados=atrasados, ok=ok,
                           nunca_grupos=_agrupar(nunca)   if user.role != 'auxiliar' else None,
                           atrasados_grupos=_agrupar(atrasados) if user.role != 'auxiliar' else None,
                           escola_cidade=escola_cidade,
                           dias=dias, total=len(unidades),
                           cidades=cidades, cidade_filtro=cidade_filtro,
                           is_admin=(user.role != 'auxiliar'))


# ─── CSV ──────────────────────────────────────
@bp.route('/exportar/kits.csv')
@login_required(roles=['admin', 'pedagogo'])
def exportar_kits_csv():
    user   = usuario_atual()
    acesso = escolas_do_usuario(user)
    qry    = KitUnidade.query
    if acesso:
        qry = qry.filter(KitUnidade.escola.in_(acesso))
    if request.args.get('escola'):
        qry = qry.filter_by(escola=request.args['escola'])
    unidades     = qry.order_by(KitUnidade.escola, KitUnidade.identificador).all()
    escola_cidade = {e.nome: e.cidade or '' for e in Escola.query.all()}
    si = StringIO()
    w  = csv.writer(si)
    w.writerow(['Identificador', 'Modelo', 'Escola', 'Cidade', 'Status',
                'Saúde (%)', 'Última Conferência', 'Responsável'])
    for u in unidades:
        uc = u.ultima_conferencia
        w.writerow([
            u.identificador,
            u.modelo.nome if u.modelo else '',
            u.escola,
            escola_cidade.get(u.escola, ''),
            u.status_atual.value if u.status_atual else '',
            u.saude_percentual if u.saude_percentual is not None else '',
            uc.data_conferencia.strftime('%d/%m/%Y %H:%M') if uc else '',
            uc.responsavel if uc else '',
        ])
    return Response(si.getvalue().encode('utf-8-sig'), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=kits.csv'})



