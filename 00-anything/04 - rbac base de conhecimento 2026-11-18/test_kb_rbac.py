"""Testes de isolamento RBAC para artigos da Base de Conhecimento (SIR-126)."""
import os
import sys
import tempfile
import unittest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Usa banco temporário isolado antes de importar app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app import app, db  # noqa: E402
from models import Usuario, KbCategoria, KbArtigo  # noqa: E402


class TestKbRbac(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

        with app.app_context():
            db.create_all()
            cls.cat = KbCategoria(nome="Geral", slug="geral", ordem=1, ativo=True)
            db.session.add(cls.cat)

            senha = generate_password_hash("123456")
            cls.u_admin = Usuario(nome="Adm", email="adm@test.com", password=senha, perfil="admin", status="ativo")
            cls.u_supremo = Usuario(nome="Sup", email="sup@test.com", password=senha, perfil="supremo", status="ativo")
            cls.u_operador = Usuario(nome="Op", email="op@test.com", password=senha, perfil="operador", status="ativo")
            cls.u_comum = Usuario(nome="User", email="usr@test.com", password=senha, perfil="usuario", status="ativo")
            db.session.add_all([cls.u_admin, cls.u_supremo, cls.u_operador, cls.u_comum])
            db.session.flush()

            cls.art_publico = KbArtigo(
                titulo="Artigo Publico Geral",
                slug="artigo-publico-geral",
                resumo="Resumo publico",
                conteudo_md="# Publico",
                categoria_id=cls.cat.id,
                autor_id=cls.u_admin.id,
                status="publicado",
                perfis_permitidos=None,
                visualizacoes=5,
            )
            cls.art_restrito = KbArtigo(
                titulo="Artigo Restrito Operacao",
                slug="artigo-restrito-operacao",
                resumo="Resumo restrito",
                conteudo_md="# Restrito",
                categoria_id=cls.cat.id,
                autor_id=cls.u_admin.id,
                status="publicado",
                perfis_permitidos="operador,tecnicoImpressora",
                visualizacoes=50,
            )
            db.session.add_all([cls.art_publico, cls.art_restrito])
            db.session.commit()

            cls.art_publico_id = cls.art_publico.id
            cls.art_restrito_id = cls.art_restrito.id

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        try:
            os.unlink(_tmp_db.name)
        except OSError:
            pass

    def _login(self, email):
        self.client.get("/logout", follow_redirects=False)
        return self.client.post(
            "/login",
            data={"email": email, "senha": "123456"},
            follow_redirects=False,
        )

    def test_01_usuario_comum_nao_ve_artigo_restrito(self):
        self._login("usr@test.com")
        resp = self.client.get("/base-conhecimento/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Artigo Publico Geral", html)
        self.assertNotIn("Artigo Restrito Operacao", html)

        # Acesso direto retorna 403 e não incrementa views
        resp_art = self.client.get("/base-conhecimento/artigo/artigo-restrito-operacao")
        self.assertEqual(resp_art.status_code, 403)
        with app.app_context():
            art = db.session.get(KbArtigo, self.art_restrito_id)
            self.assertEqual(art.visualizacoes, 50)

        # Feedback em artigo restrito retorna 403
        resp_fb = self.client.post(
            f"/base-conhecimento/artigo/{self.art_restrito_id}/feedback",
            data={"util": "1"},
        )
        self.assertEqual(resp_fb.status_code, 403)

    def test_02_operador_autorizado_acessa_artigo_restrito(self):
        self._login("op@test.com")
        resp = self.client.get("/base-conhecimento/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Artigo Restrito Operacao", resp.get_data(as_text=True))

        resp_art = self.client.get("/base-conhecimento/artigo/artigo-restrito-operacao")
        self.assertEqual(resp_art.status_code, 200)
        with app.app_context():
            art = db.session.get(KbArtigo, self.art_restrito_id)
            self.assertEqual(art.visualizacoes, 51)

    def test_03_admin_edita_artigo_existente_para_restrito_e_publico(self):
        self._login("adm@test.com")
        # Restringe artigo público existente apenas para admin
        resp_edit = self.client.post(
            f"/base-conhecimento/admin/artigo/{self.art_publico_id}/editar",
            data={
                "titulo": "Artigo Publico Geral",
                "categoria_id": "1",
                "resumo": "Resumo",
                "conteudo_md": "# Conteudo",
                "status": "publicado",
                "tags": "",
                "perfis_permitidos": ["admin"],
            },
            follow_redirects=False,
        )
        self.assertEqual(resp_edit.status_code, 302)

        # Operador agora recebe 403 nele
        self._login("op@test.com")
        resp_op = self.client.get("/base-conhecimento/artigo/artigo-publico-geral")
        self.assertEqual(resp_op.status_code, 403)

        # Supremo continua vendo normalmente
        self._login("sup@test.com")
        resp_sup = self.client.get("/base-conhecimento/artigo/artigo-publico-geral")
        self.assertEqual(resp_sup.status_code, 200)

        # Admin volta para público (sem perfis marcados)
        self._login("adm@test.com")
        self.client.post(
            f"/base-conhecimento/admin/artigo/{self.art_publico_id}/editar",
            data={
                "titulo": "Artigo Publico Geral",
                "categoria_id": "1",
                "resumo": "Resumo",
                "conteudo_md": "# Conteudo",
                "status": "publicado",
                "tags": "",
            },
            follow_redirects=False,
        )
        self._login("usr@test.com")
        resp_usr = self.client.get("/base-conhecimento/artigo/artigo-publico-geral")
        self.assertEqual(resp_usr.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
