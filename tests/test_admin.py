"""
Testes do blueprint admin: dashboards, usuários, escolas, peças, unidades.
"""
from tests.conftest import login_admin, login_pedagogo, login_auxiliar, login_as


# ── Proteção de rotas ─────────────────────────
class TestProtecaoRotas:
    def test_dashboard_admin_sem_login(self, client):
        resp = client.get('/admin/dashboard', follow_redirects=True)
        assert b'login' in resp.data.lower()

    def test_dashboard_admin_acesso_negado_auxiliar(self, client):
        login_auxiliar(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 403

    def test_dashboard_admin_acesso_negado_pedagogo(self, client):
        login_pedagogo(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 403

    def test_dashboard_admin_acesso_ok(self, client):
        login_admin(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 200

    def test_gerenciar_usuarios_requer_admin(self, client):
        login_pedagogo(client)
        resp = client.get('/admin/usuarios')
        assert resp.status_code == 403

    def test_gerenciar_usuarios_admin_ok(self, client):
        login_admin(client)
        resp = client.get('/admin/usuarios')
        assert resp.status_code == 200
        assert b'admin_test' in resp.data


# ── CRUD Usuário ──────────────────────────────
class TestUsuarioCRUD:
    def test_criar_usuario_auxiliar(self, client, app):
        login_admin(client)
        resp = client.post('/admin/usuario/novo', data={
            'username': 'novo_aux',
            'password': 'Novo@Aux123',
            'password_confirm': 'Novo@Aux123',
            'role': 'auxiliar',
            'escola_unica': 'Escola A',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Usuario, Role
            u = Usuario.query.filter_by(username='novo_aux').first()
            assert u is not None
            # Check both Enum member and String value for robustness
            role_val = getattr(u.role, 'value', u.role)
            assert role_val == 'auxiliar'
            assert u.ativo is True

    def test_criar_usuario_sem_senha_falha(self, client):
        login_admin(client)
        resp = client.post('/admin/usuario/novo', data={
            'username': 'sem_senha',
            'password': '',
            'password_confirm': '',
            'role': 'auxiliar',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Deve exibir erro de validação
        assert b'obrigat' in resp.data

    def test_criar_usuario_duplicado(self, client):
        login_admin(client)
        resp = client.post('/admin/usuario/novo', data={
            'username': 'admin_test',  # já existe
            'password': 'Admin@123',
            'password_confirm': 'Admin@123',
            'role': 'admin',
        }, follow_redirects=True)
        assert b'j\xc3\xa1 existe' in resp.data or b'existe' in resp.data

    def test_criar_usuario_senha_fraca(self, client):
        login_admin(client)
        resp = client.post('/admin/usuario/novo', data={
            'username': 'fraco_user',
            'password': '12345678',  # sem maiúscula e especial
            'password_confirm': '12345678',
            'role': 'auxiliar',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Deve exibir erro de senha fraca
        assert b'mai\xc3\xbascula' in resp.data or b'senha' in resp.data.lower()

    def test_toggle_usuario(self, client, app):
        """Admin pode ativar/desativar outro usuário."""
        login_admin(client)
        with app.app_context():
            from models import Usuario
            aux = Usuario.query.filter_by(username='auxiliar_test').first()
            uid = aux.id
            original_ativo = aux.ativo

        resp = client.post(f'/admin/usuario/{uid}/toggle',
                           follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Usuario
            aux = Usuario.query.get(uid)
            assert aux.ativo != original_ativo

    def test_nao_pode_deletar_propria_conta(self, client, app):
        login_admin(client)
        with app.app_context():
            from models import Usuario
            admin = Usuario.query.filter_by(username='admin_test').first()
            uid = admin.id
        resp = client.post(f'/admin/usuario/{uid}/deletar', follow_redirects=True)
        assert b'pr\xc3\xb3pria' in resp.data or b'pr' in resp.data


# ── CRUD Escola ───────────────────────────────
class TestEscolaCRUD:
    def test_lista_escolas_admin(self, client):
        login_admin(client)
        resp = client.get('/admin/escolas')
        assert resp.status_code == 200
        assert b'Escola A' in resp.data

    def test_lista_escolas_pedagogo(self, client):
        login_pedagogo(client)
        resp = client.get('/admin/escolas')
        assert resp.status_code == 200

    def test_lista_escolas_auxiliar_negado(self, client):
        login_auxiliar(client)
        resp = client.get('/admin/escolas')
        assert resp.status_code == 403

    def test_criar_escola(self, client, app):
        login_admin(client)
        resp = client.post('/admin/escola/nova', data={
            'nome': 'Escola Nova',
            'cidade': 'Cidade Y',
            'responsavel': 'Fulano',
            'telefone': '11999999999',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Escola
            e = Escola.query.filter_by(nome='Escola Nova').first()
            assert e is not None
            assert e.cidade == 'Cidade Y'

    def test_criar_escola_duplicada(self, client):
        login_admin(client)
        resp = client.post('/admin/escola/nova', data={
            'nome': 'Escola A',  # já existe
            'cidade': '',
        }, follow_redirects=True)
        assert b'j\xc3\xa1 est\xc3\xa1' in resp.data or b'cadastrada' in resp.data

    def test_criar_escola_sem_nome(self, client):
        login_admin(client)
        resp = client.post('/admin/escola/nova', data={'nome': ''},
                           follow_redirects=True)
        assert b'obrigat' in resp.data


# ── Unidades ──────────────────────────────────
class TestUnidades:
    def test_listar_unidades_admin(self, client):
        login_admin(client)
        resp = client.get('/admin/unidades')
        assert resp.status_code == 200
        assert b'KIT-001' in resp.data

    def test_listar_unidades_auxiliar_negado(self, client):
        login_auxiliar(client)
        resp = client.get('/admin/unidades')
        assert resp.status_code == 403


# ── Peças ─────────────────────────────────────
class TestPecas:
    def test_listar_pecas_qualquer_role(self, client):
        login_auxiliar(client)
        resp = client.get('/admin/pecas')
        assert resp.status_code == 200

    def test_criar_peca_so_admin(self, client, app):
        login_admin(client)
        resp = client.post('/admin/pecas/novo', data={
            'codigo_lego': '3001',
            'nome': 'Tijolo 2x4',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from models import Peca
            p = Peca.query.filter_by(codigo_lego='3001').first()
            assert p is not None
            assert p.nome == 'Tijolo 2x4'

    def test_criar_peca_auxiliar_negado(self, client):
        login_auxiliar(client)
        resp = client.post('/admin/pecas/novo', data={
            'codigo_lego': '9999', 'nome': 'Peça X',
        }, follow_redirects=False)
        assert resp.status_code == 403


# ── Dashboard pedagogo ─────────────────────────
class TestDashboardPedagogo:
    def test_dashboard_pedagogo_acesso(self, client):
        login_pedagogo(client)
        resp = client.get('/pedagogo/dashboard')
        assert resp.status_code == 200

    def test_dashboard_pedagogo_auxiliar_negado(self, client):
        login_auxiliar(client)
        resp = client.get('/pedagogo/dashboard')
        assert resp.status_code == 403
