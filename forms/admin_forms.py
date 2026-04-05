from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Optional, Length

class UsuarioForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[Optional(), Length(min=8)])
    password_confirm = PasswordField('Confirmar Senha', validators=[EqualTo('password', message='As senhas não coincidem.')])
    role = SelectField('Cargo / Perfil', choices=[('auxiliar', 'Auxiliar'), ('pedagogo', 'Pedagogo'), ('admin', 'Administrador')], validators=[DataRequired()])
    escola_unica = StringField('Escola Vinculada')
    ativo = BooleanField('Conta Ativa', default=True)
    submit = SubmitField('Salvar')

class EscolaForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    cidade = StringField('Cidade')
    responsavel = StringField('Responsável')
    telefone = StringField('Telefone')
    ativo = BooleanField('Ativa', default=True)
    submit = SubmitField('Salvar')

from flask_wtf.file import FileField, FileAllowed

class PecaForm(FlaskForm):
    codigo_lego = StringField('Código LEGO', validators=[DataRequired()])
    nome = StringField('Nome da Peça', validators=[DataRequired()])
    imagem = FileField('Imagem', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens!')])
    submit = SubmitField('Salvar')

class ModeloForm(FlaskForm):
    nome = StringField('Nome do Modelo', validators=[DataRequired()])
    categoria = StringField('Categoria', default='Principal')
    capa = FileField('Capa', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens!')])
    submit = SubmitField('Salvar')

class KitUnidadeForm(FlaskForm):
    identificador = StringField('Identificador da Unidade', validators=[DataRequired()])
    escola = StringField('Escola', validators=[DataRequired()])
    kit_modelo_id = SelectField('Modelo', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar')
