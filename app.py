import atexit
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, session, redirect, url_for
from flask_login import LoginManager, current_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler

from models import db, Usuario, EstoqueSuprimento
from routes.auth import auth_bp
from routes.chamados import chamados_bp
from routes.main import main_bp
from routes.dashboard import dashboard_bp
from routes.usuarios import usuarios_bp
from routes.impressoras import impressoras_bp
from routes.base_conhecimento import conhecimento_bp
from services.impressoras_services import ImpressorasService
from utils.logger import setup_logging, get_logger

# Carrega variaveis do arquivo .env
load_dotenv()

app = Flask(__name__)
setup_logging(app)
logger = get_logger('central_chamados')

# Configurações de Segurança e Sessão
secret_key_env = os.environ.get('SECRET_KEY')
if not secret_key_env or secret_key_env == 'chave-padrao-desenvolvimento-trocar-em-producao':
    import secrets
    app.config['SECRET_KEY'] = secrets.token_hex(32)
else:
    app.config['SECRET_KEY'] = secret_key_env

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1')

# Banco de dados unificado (Chamados, Usuários, Impressoras, Estoque e Histórico)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chamados.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'timeout': 30,
        'check_same_thread': False
    }
}
# manter a sessão ativa mesmo após fechar o navegador, falso
app.config['SESSION_PERMANENT'] = False

# Proteção CSRF Global
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# Banco de dados
db.init_app(app)

from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    cursor.close()

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    usuario = db.session.get(Usuario, int(user_id))
    
    if not usuario:
        return None
    
    if usuario.status != 'ativo':
        return None
    
    return usuario

@app.before_request
def verificar_usuario_ativo():
    if not current_user.is_authenticated:
        return
    
    usuario = db.session.get(
        Usuario,
        current_user.id
    )
    
    if not usuario:
        logout_user()
        session.clear()
        
        return redirect(
            url_for('auth.login')
        )
    
    if usuario.status != 'ativo':
        logout_user()
        session.clear()
        
        return redirect(
            url_for('auth.login')
        )

@app.after_request
def adicionar_cabecalhos_seguranca(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Registra os blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chamados_bp)
app.register_blueprint(main_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(impressoras_bp)
app.register_blueprint(conhecimento_bp)

# Cria as tabelas em ambos os bancos (chamados.db e estoque_suprimentos.db)
with app.app_context():
    db.create_all()


# ==========================================
# CONFIGURAÇÃO DO AGENDADOR (APScheduler)
# ==========================================
def tarefa_atualizar_impressoras():
    """Função executada periodicamente em segundo plano."""
    with app.app_context():
        try:
            logger.info("Iniciando atualização automática das impressoras...")
            ImpressorasService.atualizar_status()
            logger.info("Impressoras atualizadas com sucesso via scheduler.")
        except Exception as e:
            logger.error(f"Falha ao atualizar impressoras automaticamente: {e}", exc_info=True)

scheduler = BackgroundScheduler()

# Agendamento a cada 1 hora
scheduler.add_job(
    func=tarefa_atualizar_impressoras,
    trigger="interval",
    hours=1,
    id="job_atualizar_impressoras",
    replace_existing=True
)

import sys

# Inicia o agendador em segundo plano apenas quando o servidor web estiver em execução
is_server_process = (
    __name__ == '__main__' or
    any(arg.lower() == 'run' for arg in sys.argv)
)

if is_server_process and not scheduler.running:
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or 'WERKZEUG_RUN_MAIN' not in os.environ:
        try:
            scheduler.start()
            logger.info("Agendador APScheduler iniciado com sucesso.")
        except Exception as e:
            logger.warning(f"Aviso ao iniciar agendador: {e}")

# Garante o encerramento limpo do scheduler ao finalizar a aplicação
atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)


if __name__ == '__main__':
    from waitress import serve
    from scripts.get_ip import get_network_ip

    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    network_ip = get_network_ip()

    print("\n" + "=" * 70)
    print("           CENTRAL DE CHAMADOS BRASFORT - SERVIDOR DE REDE")
    print("=" * 70)
    print("  * Servidor WSGI:     Waitress (Multi-thread, Producao)")
    print("  * Threads Ativas:    8 conexoes simultaneas")
    print("  * Acesso Local:      http://127.0.0.1:5000  ou  http://localhost:5000")
    print(f"  * Acesso na Rede:    http://{network_ip}:{port}")
    print("  --------------------------------------------------------------------")
    print(f"  COMPARTILHE ESTE LINK NA SUA REDE: http://{network_ip}:{port}")
    print("  --------------------------------------------------------------------")
    print("  Pressione Ctrl + C para encerrar o servidor.")
    print("=" * 70 + "\n")

    logger.info(f"Servidor iniciado em http://{host}:{port} (Rede: http://{network_ip}:{port})")
    serve(app, host=host, port=port, threads=8)