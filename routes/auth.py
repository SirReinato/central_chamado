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

        email = request.form['email']
        password = request.form['senha']

        usuario = Usuario.query.filter_by(
            email=email
        ).first()

        if not usuario:
            return render_template(
                'login.html',
                error='Usuário não encontrado.'
            )

        if not check_password_hash(
            usuario.password,
            password
        ):
            return render_template(
                'login.html',
                error='Senha inválida.'
            )
            
        if usuario.status != 'ativo':
            return redirect(
                url_for(
            'auth.aguardando_aprovacao',
            status=usuario.status
                )
            )

        login_user(usuario)

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
    
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

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
                'register.html',
                error='Este email já está cadastrado.'
            )

        novo_usuario = Usuario(
            nome=nome,
            email=email,
            password=generate_password_hash(senha),
            perfil= perfil,
            status= status
        )

        db.session.add(novo_usuario)
        db.session.commit()

        return redirect(
            url_for('auth.aguardando_aprovacao')
        )

    return render_template(
        'auth/register.html'
    )
    
