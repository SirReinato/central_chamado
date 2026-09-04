from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

from services.usuario_service import (
    listar_usuarios,
    aprovar_usuario,
    bloquear_usuario,
    ativar_usuario,
)

from utils.decorator import admin_required


usuarios_bp = Blueprint(
    'usuarios',
    __name__,
    url_prefix='/usuarios'
)


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


@usuarios_bp.route('/aprovar/<int:id>')
@login_required
@admin_required
def aprovar(id):

    aprovar_usuario(id)

    return redirect(
        url_for('dashboard.dashboard')
    )


@usuarios_bp.route('/bloquear/<int:id>')
@login_required
@admin_required
def bloquear(id):

    bloquear_usuario(id)

    return redirect(
        url_for('dashboard.dashboard')
    )


@usuarios_bp.route('/ativar/<int:id>')
@login_required
@admin_required
def ativar(id):

    ativar_usuario(id)

    return redirect(
        url_for('dashboard.dashboard')
    )
    
@usuarios_bp.route('/tornar_adm/<int:id>')
@login_required
@admin_required
def tornar_adm(id):
    from services.usuario_service import tornar_adm

    tornar_adm(id)

    return redirect(
        url_for('dashboard.dashboard')
    )
    
@usuarios_bp.route('/tornar_usuario/<int:id>')
@login_required 
@admin_required
def tornar_usuario(id):
    from services.usuario_service import tornar_usuario

    tornar_usuario(id)

    return redirect(
        url_for('dashboard.dashboard')
    )