"""
Script para criar o usuário administrador inicial.
"""
import getpass
from dotenv import load_dotenv
load_dotenv()

from app import app
from extensions import db
from models import Usuario, Role
from helpers import _validar_senha


def criar_admin():
    with app.app_context():
        db.create_all()
        username = input("Username do admin [admin]: ").strip() or 'admin'
        if Usuario.query.filter_by(username=username).first():
            print(f"⚠️  Usuário '{username}' já existe.")
            return
        senha = getpass.getpass("Senha: ")
        erro  = _validar_senha(senha)
        if erro:
            print(f"❌ {erro}")
            return
        if senha != getpass.getpass("Confirmar senha: "):
            print("❌ Senhas não coincidem.")
            return
        admin = Usuario(username=username, role=Role.admin, escola='Todas')
        admin.set_password(senha)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Administrador '{username}' criado com sucesso!")


if __name__ == '__main__':
    criar_admin()
