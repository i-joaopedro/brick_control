from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from models import Usuario

class LoginForm(FlaskForm):
    username = StringField('E-mail ou Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar no Sistema')

class RequestResetForm(FlaskForm):
    email = StringField('Seu E-mail Cadastrado', validators=[DataRequired(), Email(message="E-mail inválido")])
    submit = SubmitField('Enviar Link de Recuperação')

    def validate_email(self, email):
        user = Usuario.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Não há conta com este e-mail cadastrado.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova Senha', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar Nova Senha', 
                                    validators=[DataRequired(), EqualTo('password', message='As senhas devem ser iguais')])
    submit = SubmitField('Redefinir Senha')
