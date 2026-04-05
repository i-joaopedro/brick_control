"""
Testes de autenticação: login, logout, perfil, troca de senha.
"""
from tests.conftest import login_admin, login_as


# ── Login ─────────────────────────────────────
class TestLogin:
    def test_login_sucesso_admin(self, client):
        """Admin faz login e é redirecionado para dashboard admin."""
        resp = login_admin(client)
        assert resp.status_code == 200
        # Dashboard admin deve conter algum texto característico
        assert b'dashboard' in resp.data.lower() or b'Dashboard' in resp.data or b'Kits' in resp.data

    def test_login_sucesso_pedagogo(self, client):
        resp = login_as(client, 'pedagogo_test', 'Pedagogo@123')
        assert resp.status_code == 200

    def test_login_sucesso_auxiliar(self, client):
        resp = login_as(client, 'auxiliar_test', 'Auxiliar@123')
        assert resp.status_code == 200

    def test_login_senha_errada(self, client):
        resp = login_as(client, 'admin_test', 'SenhaErrada@1')
        assert 'inválidos'.encode() in resp.data or b'inv' in resp.data
        assert resp.status_code == 200

    def test_login_usuario_inexistente(self, client):
        resp = login_as(client, 'naoexiste', 'Qualquer@123')
        assert resp.status_code == 200
        assert b'inv' in resp.data  # "inválidos"

    def test_login_conta_inativa(self, client):
        """Conta desativada não deve conseguir logar."""
        resp = login_as(client, 'inativo_test', 'Inativo@123')
        assert resp.status_code == 200
        # Deve permanecer na página de login (não redireciona para dashboard)
        assert b'login' in resp.data.lower()

    def test_login_ja_autenticado_redireciona(self, client):
        """Usuário já logado não deve ver a tela de login."""
        login_admin(client)
        resp = client.get('/login', follow_redirects=False)
        assert resp.status_code == 302

    def test_login_page_get(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()


# ── Logout ────────────────────────────────────
class TestLogout:
    def test_logout_redireciona_para_login(self, client):
        login_admin(client)
        resp = client.get('/logout', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_logout_sem_login_redireciona(self, client):
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200


# ── Perfil ────────────────────────────────────
class TestPerfil:
    def test_perfil_requer_login(self, client):
        resp = client.get('/perfil', follow_redirects=True)
        assert b'login' in resp.data.lower()

    def test_perfil_carrega_para_logado(self, client):
        login_admin(client)
        resp = client.get('/perfil')
        assert resp.status_code == 200
        assert b'admin_test' in resp.data

    def test_atualizar_dados_perfil(self, client, app):
        login_admin(client)
        resp = client.post('/perfil', data={
            'acao': 'dados',
            'nome_exibicao': 'Admin Teste',
            'email': 'admin@teste.com',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Usuario
            u = Usuario.query.filter_by(username='admin_test').first()
            assert u.nome_exibicao == 'Admin Teste'
            assert u.email == 'admin@teste.com'

    def test_trocar_senha_sucesso(self, client, app):
        login_admin(client)
        resp = client.post('/perfil', data={
            'acao': 'senha',
            'senha_atual': 'Admin@123',
            'nova_senha': 'NovaAdmin@456',
            'confirmacao': 'NovaAdmin@456',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Usuario
            u = Usuario.query.filter_by(username='admin_test').first()
            assert u.check_password('NovaAdmin@456')

    def test_trocar_senha_errada_atual(self, client):
        login_admin(client)
        resp = client.post('/perfil', data={
            'acao': 'senha',
            'senha_atual': 'Errada@123',
            'nova_senha': 'Nova@456',
            'confirmacao': 'Nova@456',
        }, follow_redirects=True)
        assert 'atual incorreta'.encode() in resp.data or b'incorreta' in resp.data

    def test_trocar_senha_confirmacao_diferente(self, client):
        login_admin(client)
        resp = client.post('/perfil', data={
            'acao': 'senha',
            'senha_atual': 'Admin@123',
            'nova_senha': 'Nova@456a',
            'confirmacao': 'Nova@456b',
        }, follow_redirects=True)
        assert b'coincidem' in resp.data
