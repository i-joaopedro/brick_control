"""
Modelos do banco de dados e enums do sistema.
"""
import enum
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


# ─────────────────────────────────────────────
#  ENUMS
# ─────────────────────────────────────────────
class Role(str, enum.Enum):
    admin    = 'admin'
    pedagogo = 'pedagogo'
    auxiliar = 'auxiliar'


class StatusKit(str, enum.Enum):
    completo   = 'Completo'
    incompleto = 'Incompleto'
    pendente   = 'Pendente'


class StatusConferencia(str, enum.Enum):
    completo   = 'Completo'
    incompleto = 'Incompleto'


# ─────────────────────────────────────────────
#  MODELOS
# ─────────────────────────────────────────────
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password      = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.Enum(Role), nullable=False)
    escola        = db.Column(db.String(200), nullable=True)
    email         = db.Column(db.String(120), nullable=True)
    nome_exibicao = db.Column(db.String(100), nullable=True)
    ativo         = db.Column(db.Boolean, default=True, nullable=False)
    criado_em     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ultimo_login  = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw): self.password = generate_password_hash(raw)
    def check_password(self, raw): return check_password_hash(self.password, raw)

    @property
    def nome_display(self):
        return self.nome_exibicao or self.username


class Peca(db.Model):
    __tablename__ = 'pecas'
    id          = db.Column(db.Integer, primary_key=True)
    codigo_lego = db.Column(db.String(50), unique=True, nullable=False)
    nome        = db.Column(db.String(100), nullable=False)
    imagem_url  = db.Column(db.String(255), default='sem-foto.png')
    composicoes = db.relationship('ComposicaoKit', backref='peca',
                                  cascade='all, delete-orphan', lazy=True)


class KitModelo(db.Model):
    __tablename__      = 'kit_modelos'
    id                 = db.Column(db.Integer, primary_key=True)
    nome               = db.Column(db.String(100), nullable=False)
    categoria          = db.Column(db.String(50))
    foto_capa          = db.Column(db.String(255), default='kit-default.png')
    pecas_obrigatorias = db.relationship('ComposicaoKit', backref='kit_modelo',
                                         cascade='all, delete-orphan', lazy=True)
    unidades_reais     = db.relationship('KitUnidade', backref='modelo',
                                         cascade='all, delete-orphan', lazy=True)


class ComposicaoKit(db.Model):
    __tablename__       = 'composicao_kits'
    id                  = db.Column(db.Integer, primary_key=True)
    kit_modelo_id       = db.Column(db.Integer, db.ForeignKey('kit_modelos.id'))
    peca_id             = db.Column(db.Integer, db.ForeignKey('pecas.id'))
    quantidade_esperada = db.Column(db.Integer, nullable=False, default=1)


class KitUnidade(db.Model):
    __tablename__ = 'kit_unidades'
    __table_args__ = (
        db.Index('ix_kit_unidades_escola', 'escola'),
        db.Index('ix_kit_unidades_status', 'status_atual'),
    )
    id            = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(50), nullable=False)
    kit_modelo_id = db.Column(db.Integer, db.ForeignKey('kit_modelos.id'))
    escola        = db.Column(db.String(100), default='Laboratório Central')
    status_atual  = db.Column(db.Enum(StatusKit), default=StatusKit.pendente)
    conferencias  = db.relationship('Conferencia', backref='unidade',
                                    cascade='all, delete-orphan',
                                    lazy='subquery',
                                    order_by='Conferencia.data_conferencia.desc()')

    @property
    def ultima_conferencia(self):
        return self.conferencias[0] if self.conferencias else None

    @property
    def saude_percentual(self):
        uc = self.ultima_conferencia
        if not uc or not uc.detalhes: return None
        esp = sum(d.quantidade_esperada_na_epoca for d in uc.detalhes)
        enc = sum(d.quantidade_encontrada for d in uc.detalhes)
        return round(enc / esp * 100, 1) if esp else 100.0


class Conferencia(db.Model):
    __tablename__ = 'conferencias'
    __table_args__ = (
        db.Index('ix_conferencias_kit_id', 'kit_unidade_id'),
        db.Index('ix_conferencias_data', 'data_conferencia'),
    )
    id               = db.Column(db.Integer, primary_key=True)
    kit_unidade_id   = db.Column(db.Integer, db.ForeignKey('kit_unidades.id'))
    data_conferencia = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    responsavel      = db.Column(db.String(100))
    observacoes      = db.Column(db.Text)
    status_resultado = db.Column(db.Enum(StatusConferencia), nullable=True)
    detalhes         = db.relationship('ConferenciaDetalhe', backref='conferencia',
                                       cascade='all, delete-orphan', lazy='subquery')


class ConferenciaDetalhe(db.Model):
    __tablename__                = 'conferencia_detalhes'
    id                           = db.Column(db.Integer, primary_key=True)
    conferencia_id               = db.Column(db.Integer, db.ForeignKey('conferencias.id'))
    peca_id                      = db.Column(db.Integer, db.ForeignKey('pecas.id'))
    quantidade_esperada_na_epoca = db.Column(db.Integer)
    quantidade_encontrada        = db.Column(db.Integer, nullable=False)
    observacao_peca              = db.Column(db.String(200), nullable=True)
    peca                         = db.relationship('Peca')


class Escola(db.Model):
    __tablename__ = 'escolas'
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(100), unique=True, nullable=False)
    cidade      = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))
    telefone    = db.Column(db.String(30))
    ativo       = db.Column(db.Boolean, default=True)
    criado_em   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def total_kits(self):
        return KitUnidade.query.filter_by(escola=self.nome).count()

    @property
    def kits_completos(self):
        return KitUnidade.query.filter_by(escola=self.nome, status_atual=StatusKit.completo).count()

    @property
    def saude_media(self):
        ultima_sq = (
            db.session.query(db.func.max(Conferencia.id).label('cid'))
            .join(KitUnidade, KitUnidade.id == Conferencia.kit_unidade_id)
            .filter(KitUnidade.escola == self.nome)
            .group_by(Conferencia.kit_unidade_id)
            .subquery()
        )
        row = (
            db.session.query(
                db.func.avg(
                    db.cast(ConferenciaDetalhe.quantidade_encontrada, db.Float) /
                    db.func.nullif(ConferenciaDetalhe.quantidade_esperada_na_epoca, 0) * 100
                )
            )
            .join(Conferencia, Conferencia.id == ConferenciaDetalhe.conferencia_id)
            .filter(Conferencia.id.in_(db.session.query(ultima_sq.c.cid)))
            .one_or_none()
        )
        val = row[0] if row and row[0] is not None else None
        return round(val, 1) if val is not None else None
