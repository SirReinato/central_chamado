from flask import Flask
from flask_login import LoginManager

from models import db, Usuario
from routes.auth import auth_bp
from routes.chamados import chamados_bp
from routes.main import main_bp
from routes.dashboard import dashboard_bp
from routes.usuarios import usuarios_bp


app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = 'sua-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chamados.db'
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
    return db.session.get(Usuario, int(user_id))


# Registra os blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chamados_bp)
app.register_blueprint(main_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(usuarios_bp)

# Cria as tabelas
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)