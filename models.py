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