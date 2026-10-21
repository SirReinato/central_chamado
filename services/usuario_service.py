from models import Usuario, db


def aprovar_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.status = 'ativo'

    db.session.commit()

    return usuario


def bloquear_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.status = 'bloqueado'

    db.session.commit()

    return usuario

def tornar_adm(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.perfil = 'admin'

    db.session.commit()

    return usuario

def tornar_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.perfil = 'usuario'

    db.session.commit()

    return usuario

def tornar_operador(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.perfil = 'operador'

    db.session.commit()

    return usuario


def tornar_tecnico_impressora(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.perfil = 'tecnicoImpressora'

    db.session.commit()

    return usuario

def ativar_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    usuario.status = 'ativo'

    db.session.commit()

    return usuario


def listar_usuarios():

    return Usuario.query.order_by(
        Usuario.nome
    ).all()


def contar_usuarios():

    return Usuario.query.count()


def alterar_senha_usuario(id, nova_senha, ator):
    """
    Altera a senha de um usuário no sistema, aplicando verificação hierárquica rigorosa:
    - Administrador Supremo pode alterar a senha de qualquer usuário.
    - Administrador comum pode alterar a senha de usuários subordinados e de si mesmo.
    - Administrador comum NÃO pode alterar a senha de outros administradores ou do Administrador Supremo.
    """
    from werkzeug.security import generate_password_hash

    usuario = Usuario.query.get_or_404(id)

    if not ator.pode_gerenciar(usuario):
        raise PermissionError("Permissão negada: administradores não podem alterar dados ou senha de usuários de mesmo nível ou superiores.")

    if not nova_senha or len(nova_senha.strip()) < 6:
        raise ValueError("A nova senha deve conter pelo menos 6 caracteres.")

    usuario.password = generate_password_hash(nova_senha.strip())
    db.session.commit()
    return usuario


def editar_usuario(id, nome, email, ator, nova_senha=None):
    """
    Atualiza dados cadastrais de um usuário (nome, e-mail, senha opcional) respeitando a hierarquia administrativa.
    """
    from werkzeug.security import generate_password_hash

    usuario = Usuario.query.get_or_404(id)

    if not ator.pode_gerenciar(usuario):
        raise PermissionError("Permissão negada: você não tem permissão para alterar os dados deste usuário.")

    if not nome or not nome.strip():
        raise ValueError("O nome do usuário não pode ser vazio.")

    email_clean = (email or '').strip().lower()
    if not email_clean:
        raise ValueError("O e-mail não pode ser vazio.")

    # Se digitou sem domínio, completa com @king.com
    if '@' not in email_clean:
        email_clean = f"{email_clean}@king.com"

    # Verificar se e-mail já existe em outro usuário
    existente = Usuario.query.filter(Usuario.email == email_clean, Usuario.id != id).first()
    if existente:
        raise ValueError(f"O e-mail '{email_clean}' já está em uso por outro usuário.")

    usuario.nome = nome.strip()
    usuario.email = email_clean

    if nova_senha and nova_senha.strip():
        if len(nova_senha.strip()) < 6:
            raise ValueError("A nova senha deve conter pelo menos 6 caracteres.")
        usuario.password = generate_password_hash(nova_senha.strip())

    db.session.commit()
    return usuario