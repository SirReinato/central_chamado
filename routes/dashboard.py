from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from models import Usuario, Chamado
from services.impressoras_services import ImpressorasService


dashboard_bp = Blueprint(
    'dashboard',
    __name__
)


def _ranking(query, coluna, limite=None):
    """
    Agrupa os chamados da query por uma coluna (categoria, setor, etc.)
    e devolve uma lista pronta para o template, já com o percentual
    relativo ao maior grupo (usado para desenhar a barra).
    """

    consulta = query.with_entities(
        coluna, func.count(Chamado.id)
    ).filter(
        coluna.isnot(None)
    ).group_by(
        coluna
    ).order_by(
        func.count(Chamado.id).desc()
    )

    if limite:
        consulta = consulta.limit(limite)

    resultados = consulta.all()

    maior = max((qtd for _, qtd in resultados), default=0)

    return [
        {
            'nome': nome,
            'total': qtd,
            'percentual': round((qtd / maior) * 100) if maior else 0
        }
        for nome, qtd in resultados
    ]


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():

    query = Chamado.query

    if not current_user.is_admin:
        query = query.filter_by(
            usuario_id=current_user.id
        )

    total = query.count()

    abertos = query.filter(
        Chamado.status.in_(['Aberto', 'Novo'])
    ).count()

    em_atendimento = query.filter(
        Chamado.status.in_([
            'Em Atendimento',
            'Pendente'
        ])
    ).count()

    resolvidos = query.filter_by(
        status='Resolvido'
    ).count()

    fechados = query.filter_by(
        status='Fechado'
    ).count()

    if current_user.is_admin:

        usuarios = Usuario.query.order_by(
            Usuario.nome
        ).all()

        total_usuarios = Usuario.query.count()

    else:

        usuarios = [current_user]
        total_usuarios = 1

    por_categoria = _ranking(query, Chamado.categoria)
    por_setor = _ranking(query, Chamado.setor, limite=5)

    # Itens críticos de impressoras/suprimentos: visão só para admins,
    # já que envolve o parque de impressoras como um todo.
    itens_atencao = (
        ImpressorasService.obter_itens_atencao()
        if current_user.is_admin
        else []
    )

    return render_template(
        'dashboard.html',
        total=total,
        abertos=abertos,
        em_atendimento=em_atendimento,
        resolvidos=resolvidos,
        fechados=fechados,
        usuarios=usuarios,
        total_usuarios=total_usuarios,
        por_categoria=por_categoria,
        por_setor=por_setor,
        itens_atencao=itens_atencao
    )