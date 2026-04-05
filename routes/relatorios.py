"""
Blueprint de relatórios: PDF e visualização HTML.
"""
import os
from datetime import datetime
from io import BytesIO

from flask import (Blueprint, render_template, request, abort, send_file, current_app)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable, Image as RLImage)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from extensions import db
from models import KitUnidade, Conferencia
from helpers import (usuario_atual, escolas_do_usuario, login_required,
                     _filtrar_detalhes, _modo_valido)

bp = Blueprint('relatorios', __name__)


# ─── HELPERS PDF ──────────────────────────────
def _pdf_styles():
    s  = getSampleStyleSheet()
    az = colors.HexColor('#2563EB')
    return {
        's': s,
        'title': ParagraphStyle('t',   parent=s['Title'],   fontSize=16, textColor=az, spaceAfter=2),
        'sub':   ParagraphStyle('sub', parent=s['Normal'],  fontSize=9,  textColor=colors.grey, spaceAfter=6),
        'sec':   ParagraphStyle('sec', parent=s['Heading2'],fontSize=11, textColor=az, spaceBefore=10, spaceAfter=4),
        'norm':  s['Normal'],
        'h3':    s['Heading3'],
        'azul':  az,
        'cinza': colors.HexColor('#F1F5F9'),
        'verde': colors.HexColor('#D1FAE5'),
        'verm':  colors.HexColor('#FEE2E2'),
        'borda': colors.HexColor('#CBD5E1'),
    }


def _img_cell(imagem_url, upload_folder, size_cm=1.2):
    if imagem_url and imagem_url not in ('sem-foto.png', 'kit-default.png'):
        path = os.path.join(upload_folder, imagem_url)
        if os.path.exists(path):
            try:
                return RLImage(path, width=size_cm * cm, height=size_cm * cm)
            except Exception:
                pass
    return Paragraph('—', getSampleStyleSheet()['Normal'])


def _pdf_tabela_pecas(detalhes, st, upload_folder):
    if not detalhes:
        return None
    cols   = [1.4*cm, 5.0*cm, 2.4*cm, 1.8*cm, 1.8*cm, 1.8*cm]
    header = [['Foto', 'Peça', 'Código', 'Esperado', 'Encontrado', 'Diferença']]
    rows, style = [], [
        ('BACKGROUND', (0, 0), (-1, 0), st['azul']),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('ALIGN',      (3, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0), (-1, -1), 0.4, st['borda']),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for i, d in enumerate(sorted(detalhes,
                                  key=lambda d: d.quantidade_encontrada - d.quantidade_esperada_na_epoca),
                           start=1):
        diff = d.quantidade_encontrada - d.quantidade_esperada_na_epoca
        rows.append([
            _img_cell(d.peca.imagem_url if d.peca else None, upload_folder),
            d.peca.nome if d.peca else '—',
            d.peca.codigo_lego if d.peca else '—',
            str(d.quantidade_esperada_na_epoca),
            str(d.quantidade_encontrada),
            str(diff) if diff != 0 else '✓',
        ])
        bg = st['verm'] if diff < 0 else (st['verde'] if diff == 0 else colors.HexColor('#EFF6FF'))
        style.append(('BACKGROUND', (0, i), (-1, i), bg))
    t = Table(header + rows, colWidths=cols, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def _pdf_relatorio_kit(unidade, modo, upload_folder):
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    st  = _pdf_styles()
    els = [
        Paragraph(f"{'Relatório Completo' if modo == 'completo' else 'Relatório de Peças Faltantes'} — Kit: {unidade.identificador}", st['title']),
        Paragraph(f"Modelo: {unidade.modelo.nome if unidade.modelo else '—'}  ·  Escola: {unidade.escola}  ·  Status: {unidade.status_atual.value if unidade.status_atual else '—'}", st['sub']),
        Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", st['sub']),
        HRFlowable(width='100%', thickness=2, color=st['azul']),
        Spacer(1, 10),
    ]
    conferencias = (Conferencia.query.filter_by(kit_unidade_id=unidade.id)
                    .order_by(Conferencia.data_conferencia.desc()).all())
    if not conferencias:
        els.append(Paragraph("Nenhuma conferência registrada.", st['norm']))
    else:
        saude = unidade.saude_percentual
        tr = Table([
            ['Total de conferências', str(len(conferencias))],
            ['Saúde atual', f"{saude}%" if saude is not None else '—'],
            ['Última conferência', conferencias[0].data_conferencia.strftime('%d/%m/%Y %H:%M')],
            ['Responsável', conferencias[0].responsavel or '—'],
        ], colWidths=[8*cm, 9*cm])
        tr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), st['cinza']),
            ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID',       (0, 0), (-1, -1), 0.5, st['borda']),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        els += [Paragraph("Resumo de Saúde", st['sec']), tr, Spacer(1, 12)]
        for idx, conf in enumerate(conferencias):
            els.append(Paragraph(
                f"Conferência #{len(conferencias)-idx}  —  "
                f"{conf.data_conferencia.strftime('%d/%m/%Y %H:%M')}  "
                f"por {conf.responsavel or '—'}  ·  {conf.status_resultado.value if conf.status_resultado else '—'}", st['sec']))
            if conf.observacoes:
                els.append(Paragraph(f"Obs: {conf.observacoes}", st['sub']))
            detalhes = _filtrar_detalhes(conf.detalhes, modo)
            tbl = _pdf_tabela_pecas(detalhes, st, upload_folder) if detalhes else None
            if tbl:
                els.append(tbl)
            else:
                els.append(Paragraph("Nenhuma peça faltando nesta conferência." if modo == 'faltantes' else "Sem detalhes registrados.", st['norm']))
            els.append(Spacer(1, 8))
    doc.build(els)
    buffer.seek(0)
    return buffer


def _pdf_relatorio_escola(unidades, titulo, autor, modo, upload_folder):
    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    st  = _pdf_styles()
    els = [
        Paragraph(f"{'Relatório Completo' if modo == 'completo' else 'Relatório de Peças Faltantes'} — {titulo}", st['title']),
        Paragraph(f"Emitido por {autor} em {datetime.now().strftime('%d/%m/%Y %H:%M')}", st['sub']),
        HRFlowable(width='100%', thickness=2, color=st['azul']),
        Spacer(1, 10),
        Paragraph("Visão Geral dos Kits", st['sec']),
    ]
    hdr  = [['Kit', 'Modelo', 'Status', 'Saúde', 'Última Conf.', 'Responsável']]
    rows = []
    for u in unidades:
        uc = u.ultima_conferencia
        rows.append([
            u.identificador,
            u.modelo.nome[:20] if u.modelo else '—',
            u.status_atual.value if u.status_atual else '—',
            f"{u.saude_percentual}%" if u.saude_percentual is not None else '—',
            uc.data_conferencia.strftime('%d/%m/%Y') if uc else 'Pendente',
            uc.responsavel if uc else '—',
        ])
    rc = [
        ('BACKGROUND', (0, 0), (-1, 0), st['azul']),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('GRID',       (0, 0), (-1, -1), 0.4, st['borda']),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(rows, start=1):
        if row[2] == 'Incompleto':
            rc.append(('BACKGROUND', (2, i), (2, i), st['verm']))
        elif row[2] == 'Completo':
            rc.append(('BACKGROUND', (2, i), (2, i), st['verde']))
    tbl = Table(hdr + rows, colWidths=[3.5*cm, 4*cm, 2.5*cm, 1.8*cm, 2.8*cm, 2.9*cm], repeatRows=1)
    tbl.setStyle(TableStyle(rc))
    els += [tbl, Spacer(1, 14)]
    els.append(Paragraph("Detalhes por Kit" if modo == 'completo' else "Peças Faltantes por Kit", st['sec']))
    for u in unidades:
        uc = u.ultima_conferencia
        if not uc or not uc.detalhes: continue
        detalhes = _filtrar_detalhes(uc.detalhes, modo)
        if not detalhes: continue
        els.append(Paragraph(
            f"{u.identificador}  —  {uc.data_conferencia.strftime('%d/%m/%Y')}  "
            f"·  {uc.responsavel or '—'}  ·  {uc.status_resultado.value if uc.status_resultado else '—'}", st['h3']))
        t = _pdf_tabela_pecas(detalhes, st, upload_folder)
        if t: els.append(t)
        els.append(Spacer(1, 8))
    els.append(Paragraph(f"Total de kits: {len(unidades)}", st['norm']))
    doc.build(els)
    buffer.seek(0)
    return buffer


# ─── ROTAS HTML ───────────────────────────────
@bp.route('/relatorio/kit/<int:kit_id>')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def relatorio_kit_view(kit_id):
    unidade = db.get_or_404(KitUnidade, kit_id)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        abort(403)
    modo       = _modo_valido(request.args.get('modo', 'completo'))
    conferencia = unidade.ultima_conferencia
    detalhes   = _filtrar_detalhes(conferencia.detalhes, modo) if conferencia else []
    return render_template('relatorio.html',
                           unidade=unidade, conferencia=conferencia,
                           detalhes=detalhes, modo=modo,
                           titulo=f"Kit {unidade.identificador} — {unidade.escola}", tipo='kit')


@bp.route('/relatorio/escola/<path:nome_escola>')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def relatorio_escola_view(nome_escola):
    user = usuario_atual()
    if user.role == 'auxiliar' and user.escola != nome_escola:
        abort(403)
    if user.role == 'pedagogo':
        acesso = escolas_do_usuario(user)
        if acesso and nome_escola not in acesso:
            abort(403)
    modo      = _modo_valido(request.args.get('modo', 'completo'))
    unidades  = KitUnidade.query.filter_by(escola=nome_escola).order_by(KitUnidade.identificador).all()
    kits_dados = []
    for u in unidades:
        conf = u.ultima_conferencia
        if not conf:
            if modo == 'completo':
                kits_dados.append({'unidade': u, 'conferencia': None, 'detalhes': []})
            continue
        detalhes = _filtrar_detalhes(conf.detalhes, modo)
        if modo == 'faltantes' and not detalhes:
            continue
        kits_dados.append({'unidade': u, 'conferencia': conf, 'detalhes': detalhes})
    return render_template('relatorio.html',
                           kits_dados=kits_dados, modo=modo,
                           titulo=f"Relatório — {nome_escola}",
                           nome_escola=nome_escola, tipo='escola')


# ─── ROTAS PDF ────────────────────────────────
@bp.route('/relatorio/kit/<int:kit_id>/pdf')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def relatorio_kit_pdf(kit_id):
    unidade = db.get_or_404(KitUnidade, kit_id)
    user    = usuario_atual()
    if user.role == 'auxiliar' and unidade.escola != user.escola:
        abort(403)
    modo   = _modo_valido(request.args.get('modo', 'completo'))
    buffer = _pdf_relatorio_kit(unidade, modo, current_app.config['UPLOAD_FOLDER'])
    return send_file(buffer, as_attachment=True,
                     download_name=f"relatorio_{modo}_{unidade.identificador.replace(' ', '_')}.pdf",
                     mimetype='application/pdf')


@bp.route('/relatorio/escola/<path:nome_escola>/pdf')
@login_required(roles=['admin', 'pedagogo', 'auxiliar'])
def relatorio_escola_pdf(nome_escola):
    user = usuario_atual()
    if user.role == 'auxiliar' and user.escola != nome_escola:
        abort(403)
    if user.role == 'pedagogo':
        acesso = escolas_do_usuario(user)
        if acesso and nome_escola not in acesso:
            abort(403)
    modo     = _modo_valido(request.args.get('modo', 'completo'))
    unidades = KitUnidade.query.filter_by(escola=nome_escola).order_by(KitUnidade.identificador).all()
    buffer   = _pdf_relatorio_escola(unidades, titulo=nome_escola, autor=user.username,
                                     modo=modo, upload_folder=current_app.config['UPLOAD_FOLDER'])
    return send_file(buffer, as_attachment=True,
                     download_name=f"relatorio_{modo}_{nome_escola.replace(' ', '_')}.pdf",
                     mimetype='application/pdf')


@bp.route('/relatorio/geral/pdf')
@login_required(roles=['admin', 'pedagogo'])
def relatorio_geral_pdf():
    user          = usuario_atual()
    acesso        = escolas_do_usuario(user)
    escola_filtro = request.args.get('escola', '')
    modo          = _modo_valido(request.args.get('modo', 'completo'))
    if escola_filtro:
        unidades = KitUnidade.query.filter_by(escola=escola_filtro).all()
        titulo   = escola_filtro
    elif acesso:
        unidades = KitUnidade.query.filter(KitUnidade.escola.in_(acesso)).all()
        titulo   = "Escolas Acessíveis"
    else:
        unidades = KitUnidade.query.all()
        titulo   = "Todos os Kits"
    buffer = _pdf_relatorio_escola(unidades, titulo=titulo, autor=user.username,
                                   modo=modo, upload_folder=current_app.config['UPLOAD_FOLDER'])
    return send_file(buffer, as_attachment=True,
                     download_name=f"relatorio_geral_{modo}.pdf",
                     mimetype='application/pdf')
