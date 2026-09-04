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