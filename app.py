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
from services.impressoras_services import ImpressorasService
from utils.logger import setup_logging, get_logger

# Carrega variaveis do arquivo .env
load_dotenv()

app = Flask(__name__)
setup_logging(app)
logger = get_logger('central_chamados')

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-padrao-desenvolvimento-trocar-em-producao')

# Banco de dados unificado (Chamados, Usuários, Impressoras, Estoque e Histórico)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chamados.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# manter a sessão ativa mesmo após fechar o navegador, falso
app.config['SESSION_PERMANENT'] = False
 


# Banco de dados
db.init_app(app)

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


# Registra os blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chamados_bp)
app.register_blueprint(main_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(impressoras_bp)

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
    replace_existing=True,
    next_run_time=datetime.now()
)

# Garante o encerramento limpo do scheduler ao finalizar a aplicação
atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)


if __name__ == '__main__':
    scheduler.start()
    from waitress import serve
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Servidor iniciado em http://{host}:{port}")
    serve(app, host=host, port=port)