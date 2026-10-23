import re
from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from services.assinatura_service import AssinaturaService

assinatura_bp = Blueprint('assinatura', __name__)

@assinatura_bp.route('/gerador-assinatura', methods=['GET'])
@assinatura_bp.route('/assinatura', methods=['GET'])
@login_required
def gerador():
    """Exibe a interface do Gerador de Assinatura Institucional."""
    # Sugestões comuns para acelerar o preenchimento
    setores_sugestoes = [
        'Setor de Suporte de TI',
        'Infraestrutura & Redes',
        'Sistemas & Desenvolvimento',
        'Recursos Humanos',
        'Departamento Pessoal',
        'Financeiro & Controladoria',
        'Operações & Segurança',
        'Comercial & Novos Negócios',
        'Compras & Suprimentos',
        'Jurídico & Compliance'
    ]

    diretorias_sugestoes = [
        'Diretoria de Inovação e Processos',
        'Diretoria de Operações',
        'Diretoria Administrativa e Financeira',
        'Diretoria Executiva',
        'Diretoria Comercial',
        'Diretoria Jurídica'
    ]

    return render_template(
        'assinatura/gerador.html',
        setores=setores_sugestoes,
        diretorias=diretorias_sugestoes
    )

@assinatura_bp.route('/gerador-assinatura/gerar', methods=['POST'])
@login_required
def gerar_download():
    """Endpoint backend para geração e download direto do PNG da assinatura."""
    nome = request.form.get('nome', '').strip()
    setor = request.form.get('setor', '').strip()
    diretoria = request.form.get('diretoria', '').strip()
    email = request.form.get('email', '').strip()
    telefone = request.form.get('telefone', '').strip()
    foto_file = request.files.get('foto')

    if not nome:
        flash('O campo Nome é obrigatório para gerar a assinatura.', 'warning')
        return redirect(url_for('assinatura.gerador'))

    # Se a foto enviada estiver vazia (sem filename), passa None
    if foto_file and not foto_file.filename:
        foto_file = None

    try:
        buffer_img = AssinaturaService.gerar_assinatura(
            nome=nome,
            setor=setor,
            diretoria=diretoria,
            email=email,
            telefone=telefone,
            foto_file=foto_file
        )

        nome_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', nome.lower())
        filename = f"assinatura_{nome_slug}.png"

        return send_file(
            buffer_img,
            mimetype='image/png',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Erro ao processar assinatura: {str(e)}', 'danger')
        return redirect(url_for('assinatura.gerador'))
