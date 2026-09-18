from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not current_user.is_authenticated:
            abort(401)

        if not current_user.is_admin:
            abort(403)

        return func(*args, **kwargs)

    return wrapper


def staff_required(func):
    """Permite acesso apenas para Administradores ou Operadores."""

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not current_user.is_authenticated:
            abort(401)

        if not (current_user.is_admin or current_user.is_operador):
            abort(403)

        return func(*args, **kwargs)

    return wrapper