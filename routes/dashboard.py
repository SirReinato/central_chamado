from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import Usuario, Chamado


dashboard_bp = Blueprint(
    'dashboard',
    __name__
)


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

    return render_template(
        'dashboard.html',
        total=total,
        abertos=abertos,
        em_atendimento=em_atendimento,
        resolvidos=resolvidos,
        fechados=fechados,
        usuarios=usuarios,
        total_usuarios=total_usuarios
    )