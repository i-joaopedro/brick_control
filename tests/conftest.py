"""
Fixtures compartilhadas pelos testes do Brick Control.
A config de teste é passada diretamente para create_app() para garantir
que o banco in-memory seja usado antes de qualquer conexão SQLAlchemy.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app import create_app
from extensions import db
from models import Usuario, Role, Escola, KitModelo, KitUnidade, Peca, ComposicaoKit

TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "WTF_CSRF_ENABLED": False,
    "SECRET_KEY": "test-secret-key-not-for-production",
    "SERVER_NAME": None,
}


@pytest.fixture(scope="function")
def app():
    """Cria app Flask com banco in-memory limpo para cada teste."""
    application = create_app(test_config=TEST_CONFIG)

    with application.app_context():
        db.create_all()

        # Usuário admin
        admin = Usuario(username='admin_test', role=Role.admin, escola='Todas')
        admin.set_password('Admin@123')

        # Usuário pedagogo
        pedagogo = Usuario(username='pedagogo_test', role=Role.pedagogo, escola='Escola A')
        pedagogo.set_password('Pedagogo@123')

        # Usuário auxiliar
        auxiliar = Usuario(username='auxiliar_test', role=Role.auxiliar, escola='Escola A')
        auxiliar.set_password('Auxiliar@123')

        # Usuário inativo
        inativo = Usuario(username='inativo_test', role=Role.auxiliar, escola='Escola A', ativo=False)
        inativo.set_password('Inativo@123')

        # Escola
        escola = Escola(nome='Escola A', cidade='Cidade X')

        # Modelo de kit
        modelo = KitModelo(nome='Kit Básico', categoria='Principal')

        db.session.add_all([admin, pedagogo, auxiliar, inativo, escola, modelo])
        db.session.commit()

        # Kit unidade
        unidade = KitUnidade(identificador='KIT-001', escola='Escola A', kit_modelo_id=modelo.id)
        db.session.add(unidade)
        db.session.commit()

        yield application

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


# ── Helpers de login ───────────────────────────
def login_as(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def login_admin(client):
    return login_as(client, 'admin_test', 'Admin@123')


def login_pedagogo(client):
    return login_as(client, 'pedagogo_test', 'Pedagogo@123')


def login_auxiliar(client):
    return login_as(client, 'auxiliar_test', 'Auxiliar@123')
