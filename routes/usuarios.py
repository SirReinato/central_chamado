from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models import Usuario, db
from services.usuario_service import (
    listar_usuarios,
    aprovar_usuario,
    bloquear_usuario,
    ativar_usuario,
    tornar_adm,
    tornar_usuario,
    tornar_operador,
)
from utils.decorator import admin_required


usuarios_bp = Blueprint(
    'usuarios',
    __name__,
    url_prefix='/usuarios'
)


def _redirecionar_origem():
    if request.referrer and 'dashboard' in request.referrer:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('usuarios.listar'))


@usuarios_bp.route('/')
@usuarios_bp.route('')
@login_required
@admin_required
def listar():
    usuarios = listar_usuarios()
    return render_template(
        'usuarios/lista_usuarios.html',
        usuarios=usuarios
    )


@usuarios_bp.route('/aprovar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def aprovar(id):
    usuario = aprovar_usuario(id)
    flash(f"Usuário '{usuario.nome}' aprovado com sucesso!", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/bloquear/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def bloquear(id):
    if current_user.id == id:
        flash("Você não pode bloquear sua própria conta de administrador.", "warning")
        return _redirecionar_origem()

    usuario = bloquear_usuario(id)
    flash(f"Usuário '{usuario.nome}' bloqueado com sucesso.", "warning")
    return _redirecionar_origem()


@usuarios_bp.route('/ativar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def ativar(id):
    usuario = ativar_usuario(id)
    flash(f"Usuário '{usuario.nome}' ativado com sucesso!", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_adm/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def rota_tornar_adm(id):
    usuario = tornar_adm(id)
    flash(f"Usuário '{usuario.nome}' agora é Administrador.", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_usuario/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def rota_tornar_usuario(id):
    total_admins = Usuario.query.filter_by(perfil='admin', status='ativo').count()
    if current_user.id == id and total_admins <= 1:
        flash("Operação negada: o sistema precisa ter pelo menos um administrador ativo.", "danger")
        return _redirecionar_origem()

    usuario = tornar_usuario(id)
    flash(f"Usuário '{usuario.nome}' agora é Usuário comum.", "info")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_operador/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def rota_tornar_operador(id):
    total_admins = Usuario.query.filter_by(perfil='admin', status='ativo').count()
    if current_user.id == id and total_admins <= 1:
        flash("Operação negada: o sistema precisa ter pelo menos um administrador ativo.", "danger")
        return _redirecionar_origem()

    usuario = tornar_operador(id)
    flash(f"Usuário '{usuario.nome}' agora é Operador.", "info")
    return _redirecionar_origem()

