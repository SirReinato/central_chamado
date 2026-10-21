from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models import Usuario, db
from services.usuario_service import (
    listar_usuarios,
    aprovar_usuario,
    bloquear_usuario,
    ativar_usuario,
    tornar_adm as servico_tornar_adm,
    tornar_usuario as servico_tornar_usuario,
    tornar_operador as servico_tornar_operador,
    tornar_tecnico_impressora as servico_tornar_tecnico_impressora,
    alterar_senha_usuario,
    editar_usuario,
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


@usuarios_bp.route('/aprovar/<int:id>', methods=['POST'])
@login_required
@admin_required
def aprovar(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem gerenciar usuários de nível igual ou superior.", "danger")
        return _redirecionar_origem()

    aprovar_usuario(id)
    flash(f"Usuário '{usuario.nome}' aprovado com sucesso!", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/bloquear/<int:id>', methods=['POST'])
@login_required
@admin_required
def bloquear(id):
    if current_user.id == id:
        flash("Você não pode bloquear sua própria conta de administrador.", "warning")
        return _redirecionar_origem()

    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem bloquear outros administradores ou o Administrador Supremo.", "danger")
        return _redirecionar_origem()

    bloquear_usuario(id)
    flash(f"Usuário '{usuario.nome}' bloqueado com sucesso.", "warning")
    return _redirecionar_origem()


@usuarios_bp.route('/ativar/<int:id>', methods=['POST'])
@login_required
@admin_required
def ativar(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem ativar usuários de nível igual ou superior.", "danger")
        return _redirecionar_origem()

    ativar_usuario(id)
    flash(f"Usuário '{usuario.nome}' ativado com sucesso!", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_adm/<int:id>', methods=['POST'])
@login_required
@admin_required
def tornar_adm(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar o perfil de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    servico_tornar_adm(id)
    flash(f"Usuário '{usuario.nome}' agora é Administrador.", "success")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_usuario/<int:id>', methods=['POST'])
@login_required
@admin_required
def tornar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar o perfil de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    total_admins = Usuario.query.filter_by(perfil='admin', status='ativo').count()
    if current_user.id == id and total_admins <= 1:
        flash("Operação negada: o sistema precisa ter pelo menos um administrador ativo.", "danger")
        return _redirecionar_origem()

    servico_tornar_usuario(id)
    flash(f"Usuário '{usuario.nome}' agora é Usuário comum.", "info")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_operador/<int:id>', methods=['POST'])
@login_required
@admin_required
def tornar_operador(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar o perfil de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    total_admins = Usuario.query.filter_by(perfil='admin', status='ativo').count()
    if current_user.id == id and total_admins <= 1:
        flash("Operação negada: o sistema precisa ter pelo menos um administrador ativo.", "danger")
        return _redirecionar_origem()

    servico_tornar_operador(id)
    flash(f"Usuário '{usuario.nome}' agora é Operador.", "info")
    return _redirecionar_origem()


@usuarios_bp.route('/tornar_tecnico_impressora/<int:id>', methods=['POST'])
@login_required
@admin_required
def tornar_tecnico_impressora(id):
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar o perfil de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    total_admins = Usuario.query.filter_by(perfil='admin', status='ativo').count()
    if current_user.id == id and total_admins <= 1:
        flash("Operação negada: o sistema precisa ter pelo menos um administrador ativo.", "danger")
        return _redirecionar_origem()

    servico_tornar_tecnico_impressora(id)
    flash(f"Usuário '{usuario.nome}' agora é Técnico de Impressoras.", "info")
    return _redirecionar_origem()


@usuarios_bp.route('/alterar_senha/<int:id>', methods=['POST'])
@login_required
@admin_required
def alterar_senha(id):
    """Permite alterar a senha de um usuário respeitando as regras de hierarquia."""
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar a senha de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    nova_senha = request.form.get('nova_senha', '').strip()
    confirmar_senha = request.form.get('confirmar_senha', '').strip()

    if not nova_senha:
        flash("Por favor, informe a nova senha.", "warning")
        return _redirecionar_origem()

    if len(nova_senha) < 6:
        flash("A nova senha deve ter no mínimo 6 caracteres.", "warning")
        return _redirecionar_origem()

    if nova_senha != confirmar_senha:
        flash("A confirmação não confere com a nova senha digitada.", "danger")
        return _redirecionar_origem()

    try:
        alterar_senha_usuario(id, nova_senha, current_user)
        flash(f"Senha do usuário '{usuario.nome}' alterada com sucesso!", "success")
    except PermissionError as pe:
        flash(str(pe), "danger")
    except ValueError as ve:
        flash(str(ve), "warning")
    except Exception as e:
        flash(f"Erro ao alterar senha: {e}", "danger")

    return _redirecionar_origem()


@usuarios_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
@admin_required
def editar_dados(id):
    """Atualiza dados cadastrais (nome, e-mail e senha opcional) respeitando a hierarquia."""
    usuario = Usuario.query.get_or_404(id)
    if not current_user.pode_gerenciar(usuario):
        flash("Permissão negada: administradores não podem alterar os dados de outros administradores ou do Administrador Supremo.", "danger")
        return _redirecionar_origem()

    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip()
    nova_senha = request.form.get('nova_senha', '').strip()
    confirmar_senha = request.form.get('confirmar_senha', '').strip()

    if nova_senha and nova_senha != confirmar_senha:
        flash("A confirmação de senha não confere com a nova senha digitada.", "danger")
        return _redirecionar_origem()

    try:
        editar_usuario(id, nome, email, current_user, nova_senha=nova_senha if nova_senha else None)
        flash(f"Dados do usuário '{nome}' atualizados com sucesso!", "success")
    except PermissionError as pe:
        flash(str(pe), "danger")
    except ValueError as ve:
        flash(str(ve), "warning")
    except Exception as e:
        flash(f"Erro ao atualizar usuário: {e}", "danger")

    return _redirecionar_origem()


