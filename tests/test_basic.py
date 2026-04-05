"""
Testes básicos: app inicia, rotas principais respondem.
"""


def test_app_criado(app):
    assert app is not None


def test_rota_raiz_redireciona_sem_login(client):
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 302


def test_rota_404(client):
    resp = client.get('/rota-que-nao-existe')
    assert resp.status_code == 404


def test_rota_login_get(client):
    resp = client.get('/login')
    assert resp.status_code == 200
