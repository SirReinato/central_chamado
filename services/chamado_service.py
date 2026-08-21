from models import db, Chamado
from flask_login import login_required, current_user

def criar_chamado(dados):
    chamado = Chamado(
        usuario_id=current_user.id,
        solicitante=current_user.nome,
        setor=dados['setor'],
        titulo=dados['titulo'],
        descricao=dados['descricao'],
        categoria=dados['categoria'],
        prioridade=dados['prioridade']
    )

    db.session.add(chamado)
    db.session.commit()

    return chamado

def buscar_chamado_por_id(chamado_id):
    return Chamado.query.get_or_404(chamado_id)

def excluir_chamado(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    
    db.session.delete(chamado)
    db.session.commit()