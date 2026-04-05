"""
Testes do blueprint auxiliar: conferências, histórico, controle de acesso.
"""
from tests.conftest import login_auxiliar, login_admin, login_pedagogo


# ── Dashboard Auxiliar ────────────────────────
class TestDashboardAuxiliar:
    def test_dashboard_auxiliar_acesso(self, client):
        login_auxiliar(client)
        resp = client.get('/auxiliar/dashboard')
        assert resp.status_code == 200
        assert b'Escola A' in resp.data

    def test_dashboard_auxiliar_admin_negado(self, client):
        login_admin(client)
        resp = client.get('/auxiliar/dashboard')
        assert resp.status_code == 403

    def test_dashboard_auxiliar_sem_login(self, client):
        resp = client.get('/auxiliar/dashboard', follow_redirects=True)
        assert b'login' in resp.data.lower()


# ── Conferências ──────────────────────────────
class TestConferencias:
    def test_lista_conferencias_auxiliar(self, client):
        login_auxiliar(client)
        resp = client.get('/auxiliar/conferencias')
        assert resp.status_code == 200
        assert b'KIT-001' in resp.data

    def test_conferir_kit_get(self, client, app):
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade
            kit = KitUnidade.query.filter_by(identificador='KIT-001').first()
            kit_id = kit.id
        resp = client.get(f'/conferir/{kit_id}')
        assert resp.status_code == 200

    def test_conferir_kit_post(self, client, app):
        """Auxiliar registra conferência de kit com modelo."""
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade, KitModelo, Peca, ComposicaoKit
            kit = KitUnidade.query.filter_by(identificador='KIT-001').first()
            kit_id = kit.id
            modelo = kit.modelo
            # Adiciona uma peça ao modelo para poder conferir
            peca = Peca(codigo_lego='TEST-01', nome='Peça Teste')
            db_from_app = __import__('extensions', fromlist=['db']).db
            db_from_app.session.add(peca)
            db_from_app.session.flush()
            comp = ComposicaoKit(kit_modelo_id=modelo.id, peca_id=peca.id, quantidade_esperada=2)
            db_from_app.session.add(comp)
            db_from_app.session.commit()
            peca_id = peca.id

        resp = client.post(f'/conferir/{kit_id}', data={
            f'peca_{peca_id}': '2',
            'observacoes': 'Tudo ok',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from models import KitUnidade, StatusKit
            kit = KitUnidade.query.get(kit_id)
            assert kit.status_atual == StatusKit.completo

    def test_conferir_kit_outra_escola_negado(self, client, app):
        """Auxiliar não pode conferir kit de escola diferente."""
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade, Escola
            from extensions import db as _db
            # Cria escola e kit de outra escola
            outra = Escola(nome='Escola B', cidade='Outra Cidade')
            _db.session.add(outra)
            _db.session.flush()
            otro_kit = KitUnidade(identificador='KIT-B01', escola='Escola B')
            _db.session.add(otro_kit)
            _db.session.commit()
            kit_id = otro_kit.id

        resp = client.get(f'/conferir/{kit_id}')
        assert resp.status_code == 403

    def test_kit_sem_modelo_redireciona(self, client, app):
        """Kit sem modelo deve redirecionar com flash, não quebrar com 500."""
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade
            from extensions import db as _db
            # Kit sem modelo (kit_modelo_id=None)
            sem_modelo = KitUnidade(identificador='KIT-SM', escola='Escola A', kit_modelo_id=None)
            _db.session.add(sem_modelo)
            _db.session.commit()
            kit_id = sem_modelo.id

        resp = client.get(f'/conferir/{kit_id}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'modelo' in resp.data.lower()  # mensagem de flash mencionando modelo


# ── Histórico de Kit ──────────────────────────
class TestHistoricoKit:
    def test_historico_auxiliar_propria_escola(self, client, app):
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade
            kit = KitUnidade.query.filter_by(identificador='KIT-001').first()
            kit_id = kit.id
        resp = client.get(f'/auxiliar/kit/{kit_id}/historico')
        assert resp.status_code == 200

    def test_historico_outra_escola_negado(self, client, app):
        login_auxiliar(client)
        with app.app_context():
            from models import KitUnidade, Escola
            from extensions import db as _db
            outra = Escola(nome='Escola C')
            _db.session.add(outra)
            _db.session.flush()
            kit_c = KitUnidade(identificador='KIT-C01', escola='Escola C')
            _db.session.add(kit_c)
            _db.session.commit()
            kit_id = kit_c.id

        resp = client.get(f'/auxiliar/kit/{kit_id}/historico')
        assert resp.status_code == 403

    def test_historico_admin_pode_ver_qualquer(self, client, app):
        login_admin(client)
        with app.app_context():
            from models import KitUnidade
            kit = KitUnidade.query.filter_by(identificador='KIT-001').first()
            kit_id = kit.id
        resp = client.get(f'/auxiliar/kit/{kit_id}/historico')
        assert resp.status_code == 200


# ── Comparar Kits ─────────────────────────────
class TestCompararKits:
    def test_comparar_auxiliar(self, client):
        login_auxiliar(client)
        resp = client.get('/auxiliar/comparar')
        assert resp.status_code == 200

    def test_comparar_admin_com_escola(self, client):
        login_admin(client)
        resp = client.get('/auxiliar/comparar?escola=Escola+A')
        assert resp.status_code == 200


# ── Pendentes ─────────────────────────────────
class TestPendentes:
    def test_pendentes_auxiliar(self, client):
        login_auxiliar(client)
        resp = client.get('/pendentes')
        assert resp.status_code == 200

    def test_pendentes_admin(self, client):
        login_admin(client)
        resp = client.get('/pendentes')
        assert resp.status_code == 200

    def test_pendentes_sem_login(self, client):
        resp = client.get('/pendentes', follow_redirects=True)
        assert b'login' in resp.data.lower()
