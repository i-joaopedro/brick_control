from typing import List, Tuple, Dict, Any, Optional
from models import KitUnidade, Conferencia, ConferenciaDetalhe, Peca, Escola, StatusKit
from extensions import db

def calcular_stats(unidades: List[KitUnidade]) -> Tuple[int, int, int, int]:
    """Calcula total, completos, incompletos e pendentes."""
    total = len(unidades)
    completos = sum(1 for u in unidades if u.status_atual == StatusKit.completo)
    incompletos = sum(1 for u in unidades if u.status_atual == StatusKit.incompleto)
    pendentes = total - completos - incompletos
    return total, completos, incompletos, pendentes

def calcular_ranking_perdas(unidades: List[KitUnidade], top: int = 10) -> List[Dict[str, Any]]:
    """Gera o ranking de peças mais perdidas."""
    if not unidades:
        return []
    kit_ids = [u.id for u in unidades]

    ultima_conf_sq = (
        db.session.query(db.func.max(Conferencia.id).label('conf_id'))
        .filter(Conferencia.kit_unidade_id.in_(kit_ids))
        .group_by(Conferencia.kit_unidade_id)
        .subquery()
    )

    rows = (
        db.session.query(
            Peca.id, Peca.nome, Peca.codigo_lego,
            db.func.sum(
                db.case(
                    (ConferenciaDetalhe.quantidade_encontrada < ConferenciaDetalhe.quantidade_esperada_na_epoca,
                     ConferenciaDetalhe.quantidade_esperada_na_epoca - ConferenciaDetalhe.quantidade_encontrada),
                    else_=0
                )
            ).label('perdas'),
            db.func.count(
                db.case(
                    (ConferenciaDetalhe.quantidade_encontrada < ConferenciaDetalhe.quantidade_esperada_na_epoca, 1),
                    else_=None
                )
            ).label('kits')
        )
        .join(ConferenciaDetalhe, ConferenciaDetalhe.peca_id == Peca.id)
        .join(Conferencia, Conferencia.id == ConferenciaDetalhe.conferencia_id)
        .filter(Conferencia.id.in_(db.session.query(ultima_conf_sq.c.conf_id)))
        .group_by(Peca.id, Peca.nome, Peca.codigo_lego)
        .having(db.func.sum(
            db.case(
                (ConferenciaDetalhe.quantidade_encontrada < ConferenciaDetalhe.quantidade_esperada_na_epoca,
                 ConferenciaDetalhe.quantidade_esperada_na_epoca - ConferenciaDetalhe.quantidade_encontrada),
                else_=0
            )
        ) > 0)
        .order_by(db.text('perdas DESC'))
        .limit(top)
        .all()
    )
    return [{'nome': r.nome, 'codigo': r.codigo_lego, 'perdas': r.perdas, 'kits': r.kits} for r in rows]

def get_cidades_data(escolas_obj: List[Escola], unidades: List[KitUnidade]) -> Dict[str, Any]:
    """Agrega os dados de dashboard por cidade para a view do admin."""
    from collections import defaultdict
    cidades_data = defaultdict(lambda: {'escolas': [], 'total': 0, 'completos': 0,
                                        'incompletos': 0, 'pendentes': 0})
    for escola in escolas_obj:
        cidade = escola.cidade or 'Sem cidade'
        ue = [u for u in unidades if u.escola == escola.nome]
        t, c, i, p = calcular_stats(ue)
        # Fix N+1: instead of calling u.saude_percentual (which triggers self.ultima_conferencia),
        # saude is best bulk fetched, but keeping it simple for now and letting models property handle or optimize independently
        # TODO: Optimize saude_percentual if it causes N+1
        saude_vals = [u.saude_percentual for u in ue if u.saude_percentual is not None]
        cidades_data[cidade]['escolas'].append({
            'obj': escola, 'total': t, 'completos': c, 'incompletos': i, 'pendentes': p,
            'saude': round(sum(saude_vals) / len(saude_vals), 1) if saude_vals else None
        })
        cidades_data[cidade]['total'] += t
        cidades_data[cidade]['completos'] += c
        cidades_data[cidade]['incompletos'] += i
        cidades_data[cidade]['pendentes'] += p

    return dict(cidades_data)
