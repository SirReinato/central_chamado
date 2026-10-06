import re
from flask import Blueprint, render_template, request, redirect, session, url_for

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import check_password_hash, generate_password_hash

from models import Usuario, db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():

    # Se já estiver logado
    if current_user.is_authenticated:
        return redirect(url_for('chamados.home'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('senha', '')

        # Se o usuário digitar somente nome.sobrenome, completa com @king.com
        if email and '@' not in email:
            email = f"{email}@king.com"

        usuario = Usuario.query.filter_by(
            email=email
        ).first()

        if not usuario or not check_password_hash(usuario.password, password):
            return render_template(
                'auth/login.html',
                error='E-mail ou senha incorretos.'
            )

        if usuario.status != 'ativo':
            return redirect(
                url_for(
                    'auth.aguardando_aprovacao',
                    status=usuario.status
                )
            )

        login_user(usuario)

        if usuario.is_tecnico_impressora:
            return redirect(url_for('impressoras.index'))

        return redirect(url_for('chamados.home'))

    return render_template(
        'auth/login.html'
    )

@auth_bp.route('/logout')
@login_required
def logout():

    logout_user()
    session.clear()

    return redirect(
        url_for('auth.login')
    )

@auth_bp.route('/aguardando_aprovacao')
def aguardando_aprovacao():
    status = request.args.get('status')

    return render_template(
        'auth/aguardando_aprovacao.html',
        status=status
    )

def validar_email_institucional(email_raw):
    """
    Valida e normaliza o e-mail para novos usuários.
    Padrão institucional obrigatório: nome.sobrenome@king.com
    (deve conter pelo menos nome e sobrenome separados por ponto).
    
    Retorna: (email_normalizado, mensagem_erro)
    """
    if not email_raw or not email_raw.strip():
        return None, "Por favor, informe seu e-mail institucional."

    email = email_raw.strip().lower()

    # Se o usuário digitou apenas "nome.sobrenome" sem o sufixo "@king.com"
    if '@' not in email:
        email = f"{email}@king.com"

    # Verifica se termina obrigatoriamente com o domínio @king.com
    if not email.endswith('@king.com'):
        return None, "Domínio não permitido. Novos usuários devem utilizar obrigatoriamente o domínio @king.com (exemplo: nome.sobrenome@king.com)."

    # Extrai o nome de usuário local antes do @king.com
    usuario_local = email[:-len('@king.com')]

    # Valida formato nome.sobrenome (apenas caracteres alfanuméricos e pontos)
    # Requer pelo menos duas partes separadas por ponto: nome.sobrenome
    padrao = r'^[a-z0-9]+(?:\.[a-z0-9]+)+$'
    if not re.match(padrao, usuario_local):
        return None, "Formato de e-mail inválido! O login deve conter nome e sobrenome separados por ponto no padrão: nome.sobrenome@king.com (exemplo: joao.silva@king.com)."

    return email, None


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()
        email_raw = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')

        if not nome or not email_raw or not senha:
            return render_template(
                'auth/register.html',
                error='Por favor, preencha todos os campos.',
                nome=nome,
                email=email_raw
            )

        if len(senha) < 6:
            return render_template(
                'auth/register.html',
                error='A senha deve conter no mínimo 6 caracteres para sua segurança.',
                nome=nome,
                email=email_raw
            )

        # Validação estrita do padrão de e-mail institucional
        email, erro_email = validar_email_institucional(email_raw)
        if erro_email:
            return render_template(
                'auth/register.html',
                error=erro_email,
                nome=nome,
                email=email_raw
            )

        admin_existe = Usuario.query.filter_by(
            perfil='admin'
        ).first()

        if not admin_existe:
            perfil = 'admin'
            status = 'ativo'
        else:
            perfil = 'usuario'
            status = 'pendente'

        usuario_existente = Usuario.query.filter_by(
            email=email
        ).first()

        if usuario_existente:
            return render_template(
                'auth/register.html',
                error='Este e-mail já está cadastrado.',
                nome=nome,
                email=email_raw
            )

        novo_usuario = Usuario(
            nome=nome,
            email=email,
            password=generate_password_hash(senha),
            perfil=perfil,
            status=status
        )

        db.session.add(novo_usuario)
        db.session.commit()

        return redirect(
            url_for('auth.aguardando_aprovacao')
        )

    return render_template(
        'auth/register.html'
    )

    
