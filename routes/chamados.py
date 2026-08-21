from flask import Blueprint, render_template, request, redirect, abort, url_for
from flask_login import login_required, current_user
from sqlalchemy import case

from models import db, Chamado

from services.chamado_service import (
    criar_chamado,
    buscar_chamado_por_id,
    excluir_chamado as deletar_chamado_service
)

from utils.decorator import admin_required


chamados_bp = Blueprint(
    'chamados',
    __name__
)


# =============================================================
# CONSULTAS
# =============================================================

def query_chamados():
    """
    Retorna a consulta de chamados de acordo com o usuário logado.

    Administradores:
        Retornam todos os chamados.

    Usuários comuns:
        Retornam apenas os chamados pertencentes ao usuário.
    """

    if current_user.is_admin:
        return Chamado.query

    return Chamado.query.filter_by(
        usuario_id=current_user.id
    )


def lista_de_chamados():
    """
    Lista os chamados ordenados por prioridade de status.
    """

    ordem_status = case(
        (Chamado.status == 'Aberto', 1),
        (Chamado.status == 'Em Atendimento', 2),
        (Chamado.status == 'Pendente', 3),
        (Chamado.status == 'Resolvido', 4),
        (Chamado.status == 'Fechado', 5),
        else_=6
    )

    return query_chamados().order_by(
        ordem_status
    ).all()


# =============================================================
# HOME
# =============================================================

@chamados_bp.route('/home')
@login_required
def home():

    query = query_chamados()

    total = query.count()

    abertos = query.filter(
        Chamado.status.in_([
            'Aberto',
            'Novo'
        ])
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

    chamados_abertos = query.filter(
        Chamado.status.in_([
            'Aberto',
            'Novo'
        ])
    ).all()

    return render_template(
        'index.html',
        total=total,
        abertos=abertos,
        em_atendimento=em_atendimento,
        resolvidos=resolvidos,
        fechados=fechados,
        chamados_abertos=chamados_abertos
    )


# =============================================================
# LISTAGEM DE CHAMADOS
# =============================================================

@chamados_bp.route('/chamados')
@login_required
def listar_chamados():

    chamados = lista_de_chamados()

    return render_template(
        'chamados/listar_chamados.html',
        chamados=chamados
    )


# =============================================================
# NOVO CHAMADO
# =============================================================

@chamados_bp.route('/chamados/novo', methods=['GET', 'POST'])
@login_required
def novo_chamado():

    if request.method == 'POST':

        criar_chamado(request.form)

        return redirect(
            url_for('chamados.listar_chamados')
        )

    return render_template(
        'chamados/novo_chamado.html'
    )


# =============================================================
# EDITAR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_chamado(id):

    chamado = buscar_chamado_por_id(id)

    # Usuário comum só pode editar seus próprios chamados
    if (
        not current_user.is_admin
        and chamado.usuario_id != current_user.id
    ):
        abort(403)

    if request.method == 'POST':

        chamado.solicitante = request.form['solicitante']
        chamado.setor = request.form['setor']
        chamado.titulo = request.form['titulo']
        chamado.descricao = request.form['descricao']
        chamado.categoria = request.form['categoria']
        chamado.prioridade = request.form['prioridade']
        chamado.status = request.form['status']

        db.session.commit()

        return redirect(
            url_for('chamados.listar_chamados')
        )

    return render_template(
        'chamados/editar_chamado.html',
        chamado=chamado
    )


# =============================================================
# EXCLUIR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/excluir/<int:id>')
@login_required
@admin_required
def excluir_chamado(id):

    deletar_chamado_service(id)

    return redirect(
        url_for('chamados.listar_chamados')
    )


# =============================================================
# DETALHES DO CHAMADO
# =============================================================

@chamados_bp.route('/chamados/detalhes/<int:id>')
@login_required
def detalhes_chamado(id):

    chamado = buscar_chamado_por_id(id)

    # Usuário comum só pode visualizar seus próprios chamados
    if (
        not current_user.is_admin
        and chamado.usuario_id != current_user.id
    ):
        abort(403)

    return render_template(
        'chamados/detalhes_chamado.html',
        chamado=chamado
    )


# =============================================================
# RESOLVER CHAMADO
# =============================================================

@chamados_bp.route('/chamados/resolver/<int:id>')
@login_required
@admin_required
def resolver_chamado(id):

    chamado = buscar_chamado_por_id(id)

    chamado.status = 'Resolvido'

    db.session.commit()

    return redirect(
        url_for('chamados.listar_chamados')
    )


# =============================================================
# FECHAR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/fechar/<int:id>')
@login_required
@admin_required
def fechar_chamado(id):

    chamado = buscar_chamado_por_id(id)

    chamado.status = 'Fechado'

    db.session.commit()

    return redirect(
        url_for('chamados.listar_chamados')
    )