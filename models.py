from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class Chamado(db.Model):
    __tablename__ = 'chamados'

    id = db.Column(db.Integer, primary_key=True)
    
    usuario_id = db.Column(
        db.Integer, 
        db.ForeignKey('usuarios.id'), 
        nullable=False
    )
    usuario = db.relationship('Usuario', backref='chamados')

    solicitante = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(100), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    prioridade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Aberto')
    data_abertura = db.Column(db.DateTime, default=datetime.now)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(
        db.Integer, 
        primary_key=True
        )
    nome = db.Column(
        db.String(100), 
        nullable=False
    )
    email = db.Column(
        db.String(100), 
        unique=True, 
        nullable=False
        )
    password = db.Column(
        db.String(200), 
        nullable=False
    )
    perfil = db.Column(
        db.String(20), 
        nullable=False, 
        default='usuario'
    )
    status = db.Column(
        db.String(20), 
        nullable=False, 
        default='pendente'
    )
    
    @property
    def is_admin(self):
        return self.perfil == 'admin'
    
    
class Impressora(db.Model):
    __tablename__ = "impressoras"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100))
    ip = db.Column(db.String(45), unique=True)
    modelo = db.Column(db.String(100))

    # Localização fisica
    andar = db.Column(db.String(50), default="Não Informado")
    sala = db.Column(db.String(50), default="Não Informado")
    
    # Chave estrangeira para a tabela EstoqueSuprimento
    suprimento_id = db.Column(
        db.Integer,
        nullable=True,
        )
  

    online = db.Column(
        db.Boolean,
        default=False
    )

    toner_preto = db.Column(
        db.Integer,
        nullable=True
    )

    toner_ciano = db.Column(
        db.Integer,
        nullable=True
    )

    toner_magenta = db.Column(
        db.Integer,
        nullable=True
    )

    toner_amarelo = db.Column(
        db.Integer,
        nullable=True
    )

    paginas_impressas = db.Column(
        db.Integer,
        default=0
    )

    ultimo_check = db.Column(
        db.DateTime
    )    
    
    cilindro = db.Column(
    db.Integer,
    nullable=True
    )

    nivel_papel = db.Column(
        db.Integer,
        nullable=True
    )

    serial = db.Column(
        db.String(100)
    )

    status_detalhado = db.Column(
        db.String(255)
    )
    
    fabricante = db.Column(
    db.String(50)
    )

    ultimo_erro = db.Column(
        db.String(255)
    )

    ultima_sincronizacao = db.Column(
        db.DateTime
    )

    necessita_atencao = db.Column(
        db.Boolean,
        default=False
    )
    
    
# =========================================================
# NOVAS TABELAS ISOLADAS NO BANCO DE ESTOQUE (estoque_suprimentos.db)
# =========================================================

class EstoqueSuprimento(db.Model):
    __tablename__ = "estoque_suprimentos"
    __bind_key__ = 'estoque_db'

    id = db.Column(db.Integer, primary_key=True)
    nome_familia = db.Column(db.String(100), nullable=False, unique=True)
    quantidade_toner = db.Column(db.Integer, default=0, nullable=False)
    quantidade_cilindro = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo = db.Column(db.Integer, default=2, nullable=False)

class HistoricoSuprimento(db.Model):
    __tablename__ = "historico_suprimentos"
    __bind_key__ = 'estoque_db'

    id = db.Column(db.Integer, primary_key=True)
    impressora_id = db.Column(db.Integer, nullable=False)
    tipo_insumo = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=-1)
    usuario_responsavel = db.Column(db.String(100), nullable=False)
    data_retirada = db.Column(db.DateTime, default=datetime.now)