"""
Modelos do banco de dados e enums do sistema.
"""
import enum
from datetime import datetime, timezone
from itsdangerous import URLSafeTimedSerializer as Serializer
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
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
    def saude_media(self):
        """Média da saúde de todos os kits desta escola."""
        from models import KitUnidade
        kits = KitUnidade.query.filter_by(escola=self.nome).all()
        if not kits: 
            return None
        saude_vals = [k.saude_percentual for k in kits if k.saude_percentual is not None]
        if not saude_vals:
            return 0
        return round(sum(saude_vals) / len(saude_vals), 1)


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

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except:
            return None
        return Usuario.query.get(user_id)


class Peca(db.Model):
    __tablename__ = 'pecas'
    id          = db.Column(db.Integer, primary_key=True)
    codigo_lego = db.Column(db.String(50), unique=True, nullable=False)
    nome        = db.Column(db.String(100), nullable=False)
    imagem_url  = db.Column(db.String(255))


class KitModelo(db.Model):
    __tablename__ = 'kit_modelos'
    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    foto_capa = db.Column(db.String(255))


class ComposicaoKit(db.Model):
    __tablename__ = 'composicao_kits'
    id                  = db.Column(db.Integer, primary_key=True)
    kit_modelo_id       = db.Column(db.Integer, db.ForeignKey('kit_modelos.id'), nullable=False)
    peca_id             = db.Column(db.Integer, db.ForeignKey('pecas.id'), nullable=False)
    quantidade_esperada = db.Column(db.Integer, nullable=False)

    modelo = db.relationship('KitModelo', backref=db.backref('pecas_obrigatorias', lazy=True, cascade="all, delete-orphan"))
    peca   = db.relationship('Peca')


class KitUnidade(db.Model):
    __tablename__ = 'kit_unidades'
    id              = db.Column(db.Integer, primary_key=True)
    identificador   = db.Column(db.String(50), nullable=False)
    kit_modelo_id   = db.Column(db.Integer, db.ForeignKey('kit_modelos.id'), nullable=False)
    escola          = db.Column(db.String(100))
    status_atual    = db.Column(db.Enum(StatusKit), default=StatusKit.pendente)

    modelo = db.relationship('KitModelo', backref=db.backref('unidades_reais', lazy=True))

    @property
    def ultima_conferencia(self):
        if not self.historico_conferencias:
            return None
        # Ordena por data decrescente
        return sorted(self.historico_conferencias, key=lambda c: c.data_conferencia, reverse=True)[0]

    @property
    def saude_percentual(self):
        conf = self.ultima_conferencia
        if not conf:
            return 100 if self.status_atual == StatusKit.completo else 0
        
        detalhes = conf.detalhes
        if not detalhes:
            return 100
            
        total_esperado = sum(d.quantidade_esperada_na_epoca or 0 for d in detalhes)
        if total_esperado == 0:
            return 100
            
        total_encontrado = sum(d.quantidade_encontrada or 0 for d in detalhes)
        return int((total_encontrado / total_esperado) * 100)


class Conferencia(db.Model):
    __tablename__ = 'conferencias'
    id             = db.Column(db.Integer, primary_key=True)
    kit_unidade_id = db.Column(db.Integer, db.ForeignKey('kit_unidades.id'), nullable=False)
    data_conferencia = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    responsavel    = db.Column(db.String(100))
    observacoes    = db.Column(db.Text)
    status_resultado = db.Column(db.Enum(StatusConferencia), default=StatusConferencia.incompleto)

    unidade = db.relationship('KitUnidade', backref=db.backref('historico_conferencias', lazy=True))


class ConferenciaDetalhe(db.Model):
    __tablename__ = 'conferencia_detalhes'
    id             = db.Column(db.Integer, primary_key=True)
    conferencia_id = db.Column(db.Integer, db.ForeignKey('conferencias.id'), nullable=False)
    peca_id        = db.Column(db.Integer, db.ForeignKey('pecas.id'), nullable=False)
    quantidade_esperada_na_epoca = db.Column(db.Integer)
    quantidade_encontrada        = db.Column(db.Integer, default=0, nullable=False)
    observacao_peca              = db.Column(db.String(200))

    conferencia = db.relationship('Conferencia', backref=db.backref('detalhes', lazy=True, cascade="all, delete-orphan"))
    peca        = db.relationship('Peca')
