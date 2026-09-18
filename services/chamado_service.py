from models import db, Chamado
from flask_login import login_required, current_user

def criar_chamado(dados):
    solicitante = dados.get('solicitante', '').strip() or current_user.nome

    chamado = Chamado(
        usuario_id=current_user.id,
        solicitante=solicitante,
        setor=dados.get('setor', '').strip(),
        titulo=dados.get('titulo', '').strip(),
        descricao=dados.get('descricao', '').strip(),
        categoria=dados.get('categoria', 'Hardware'),
        prioridade=dados.get('prioridade', 'Baixa')
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