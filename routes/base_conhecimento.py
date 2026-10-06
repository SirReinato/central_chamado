from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, KbCategoria, KbTag, KbArtigo, KbFeedback, KbSolicitacao
from services.conhecimento_service import ConhecimentoService
from utils.decorator import admin_required

conhecimento_bp = Blueprint('conhecimento', __name__, url_prefix='/base-conhecimento')


@conhecimento_bp.route('/')
@login_required
def index():
    """Hub principal da Base de Conhecimento."""
    ConhecimentoService.seed_dados_iniciais()

    busca = request.args.get('busca', '').strip()
    categoria_slug = request.args.get('categoria', '').strip()
    tag_slug = request.args.get('tag', '').strip()
    ordem = request.args.get('ordem', 'relevancia').strip()
    modo_visualizacao = request.args.get('view', 'cards').strip()

    artigos = ConhecimentoService.listar_artigos(
        busca=busca,
        categoria_slug=categoria_slug,
        tag_slug=tag_slug,
        ordem=ordem,
        status='publicado'
    )

    categorias = KbCategoria.query.filter_by(ativo=True).order_by(KbCategoria.ordem).all()
    todas_tags = KbTag.query.order_by(KbTag.nome).all()
    
    # Artigos em destaque (top 4 mais acessados)
    artigos_populares = KbArtigo.query.filter_by(status='publicado').order_by(KbArtigo.visualizacoes.desc()).limit(4).all()

    categoria_ativa = KbCategoria.query.filter_by(slug=categoria_slug).first() if categoria_slug else None

    return render_template(
        'conhecimento/index.html',
        artigos=artigos,
        categorias=categorias,
        todas_tags=todas_tags,
        artigos_populares=artigos_populares,
        categoria_ativa=categoria_ativa,
        filtros={
            'busca': busca,
            'categoria': categoria_slug,
            'tag': tag_slug,
            'ordem': ordem,
            'view': modo_visualizacao
        }
    )


@conhecimento_bp.route('/artigo/<slug>')
@login_required
def ver_artigo(slug):
    """Visualização e leitura completa de um artigo formatado em Markdown."""
    artigo = ConhecimentoService.obter_artigo_por_slug(slug, incrementar_views=True)
    if not artigo:
        abort(404)

    # Converte Markdown para HTML com ToC e Callouts
    conteudo_html, toc_html = ConhecimentoService.renderizar_markdown(artigo.conteudo_md)

    # Artigos recomendados/relacionados (mesma categoria, excluindo o atual)
    artigos_relacionados = KbArtigo.query.filter(
        KbArtigo.categoria_id == artigo.categoria_id,
        KbArtigo.id != artigo.id,
        KbArtigo.status == 'publicado'
    ).order_by(KbArtigo.visualizacoes.desc()).limit(3).all()

    return render_template(
        'conhecimento/artigo.html',
        artigo=artigo,
        conteudo_html=conteudo_html,
        toc_html=toc_html,
        artigos_relacionados=artigos_relacionados
    )


@conhecimento_bp.route('/artigo/<int:artigo_id>/feedback', methods=['POST'])
@login_required
def feedback_artigo(artigo_id):
    """Registra voto útil (👍) ou inútil (👎) com comentário opcional."""
    util_str = request.form.get('util', '1')
    util = util_str in ('1', 'true', 'True')
    comentario = request.form.get('comentario', '').strip()

    sucesso, mensagem = ConhecimentoService.registrar_feedback(
        artigo_id=artigo_id,
        util=util,
        usuario_id=current_user.id,
        comentario=comentario
    )

    flash(mensagem, 'success' if sucesso else 'danger')
    artigo = db.session.get(KbArtigo, artigo_id)
    if artigo:
        return redirect(url_for('conhecimento.ver_artigo', slug=artigo.slug))
    return redirect(url_for('conhecimento.index'))


@conhecimento_bp.route('/solicitar', methods=['GET', 'POST'])
@login_required
def solicitar_artigo():
    """Formulário para usuários comuns sugerirem novos procedimentos ou atualizações."""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        justificativa = request.form.get('justificativa', '').strip()
        prioridade = request.form.get('prioridade', 'normal')
        categoria_id = request.form.get('categoria_id')

        if not titulo or not descricao:
            flash("Título e descrição são obrigatórios para a solicitação.", "warning")
            return redirect(url_for('conhecimento.solicitar_artigo'))

        try:
            cat_id = int(categoria_id) if categoria_id else None
        except (ValueError, TypeError):
            cat_id = None

        ConhecimentoService.criar_solicitacao(
            titulo=titulo,
            descricao=descricao,
            categoria_id=cat_id,
            justificativa=justificativa,
            prioridade=prioridade,
            usuario_id=current_user.id
        )

        flash("Sua solicitação de artigo foi enviada com sucesso para a equipe de TI!", "success")
        return redirect(url_for('conhecimento.minhas_solicitacoes'))

    categorias = KbCategoria.query.filter_by(ativo=True).order_by(KbCategoria.ordem).all()
    return render_template('conhecimento/solicitar.html', categorias=categorias)


@conhecimento_bp.route('/solicitacoes')
@login_required
def minhas_solicitacoes():
    """Exibe as solicitações de conteúdo enviadas pelo usuário logado."""
    solicitacoes = KbSolicitacao.query.filter_by(solicitante_id=current_user.id).order_by(KbSolicitacao.data_envio.desc()).all()
    return render_template('conhecimento/minhas_solicitacoes.html', solicitacoes=solicitacoes)


# =========================================================
# ROTAS ADMINISTRATIVAS (/base-conhecimento/admin)
# =========================================================

@conhecimento_bp.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Dashboard analítico da Base de Conhecimento e fila de triagem."""
    kpis = ConhecimentoService.obter_kpis_admin()
    solicitacoes_pendentes = KbSolicitacao.query.filter_by(status='pendente').order_by(KbSolicitacao.data_envio.asc()).all()
    artigos_recentes = KbArtigo.query.order_by(KbArtigo.data_atualizacao.desc()).limit(15).all()
    categorias = KbCategoria.query.order_by(KbCategoria.ordem).all()

    return render_template(
        'conhecimento/admin_dashboard.html',
        kpis=kpis,
        solicitacoes_pendentes=solicitacoes_pendentes,
        artigos_recentes=artigos_recentes,
        categorias=categorias
    )


@conhecimento_bp.route('/admin/artigo/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_artigo():
    """Criação de novo artigo com editor Markdown."""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        categoria_id = request.form.get('categoria_id')
        resumo = request.form.get('resumo', '').strip()
        conteudo_md = request.form.get('conteudo_md', '').strip()
        tags_raw = request.form.get('tags', '').strip()
        status = request.form.get('status', 'publicado')

        if not titulo or not conteudo_md or not categoria_id:
            flash("Título, Categoria e Conteúdo Markdown são obrigatórios.", "danger")
            return redirect(url_for('conhecimento.novo_artigo'))

        # Gera slug único
        slug_base = ConhecimentoService.gerar_slug(titulo)
        slug = slug_base
        contador = 1
        while KbArtigo.query.filter_by(slug=slug).first():
            slug = f"{slug_base}-{contador}"
            contador += 1

        tempo_leitura = ConhecimentoService.calcular_tempo_leitura(conteudo_md)

        novo = KbArtigo(
            titulo=titulo,
            slug=slug,
            resumo=resumo if resumo else None,
            conteudo_md=conteudo_md,
            categoria_id=int(categoria_id),
            autor_id=current_user.id,
            status=status,
            tempo_leitura_min=tempo_leitura
        )

        # Trata tags separadas por vírgula
        if tags_raw:
            nomes_tags = [t.strip().lower() for t in tags_raw.replace(';', ',').split(',') if t.strip()]
            for nome_t in nomes_tags:
                slug_tag = ConhecimentoService.gerar_slug(nome_t)
                tag_obj = KbTag.query.filter_by(slug=slug_tag).first()
                if not tag_obj:
                    tag_obj = KbTag(nome=nome_t, slug=slug_tag)
                    db.session.add(tag_obj)
                novo.tags.append(tag_obj)

        db.session.add(novo)
        db.session.commit()

        flash(f"Artigo '{novo.titulo}' criado com sucesso!", "success")
        return redirect(url_for('conhecimento.ver_artigo', slug=novo.slug))

    categorias = KbCategoria.query.filter_by(ativo=True).order_by(KbCategoria.ordem).all()
    # Verifica se veio preenchido de uma solicitação
    solicitacao_id = request.args.get('solicitacao_id')
    solicitacao = db.session.get(KbSolicitacao, int(solicitacao_id)) if solicitacao_id else None

    return render_template(
        'conhecimento/editor_artigo.html',
        categorias=categorias,
        artigo=None,
        solicitacao=solicitacao
    )


@conhecimento_bp.route('/admin/artigo/<int:artigo_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_artigo(artigo_id):
    """Edição de artigo existente."""
    artigo = db.session.get(KbArtigo, artigo_id)
    if not artigo:
        abort(404)

    if request.method == 'POST':
        artigo.titulo = request.form.get('titulo', '').strip()
        artigo.categoria_id = int(request.form.get('categoria_id'))
        artigo.resumo = request.form.get('resumo', '').strip()
        artigo.conteudo_md = request.form.get('conteudo_md', '').strip()
        artigo.status = request.form.get('status', 'publicado')
        artigo.tempo_leitura_min = ConhecimentoService.calcular_tempo_leitura(artigo.conteudo_md)
        artigo.data_atualizacao = datetime.now()

        # Atualiza tags
        tags_raw = request.form.get('tags', '').strip()
        artigo.tags.clear()
        if tags_raw:
            nomes_tags = [t.strip().lower() for t in tags_raw.replace(';', ',').split(',') if t.strip()]
            for nome_t in nomes_tags:
                slug_tag = ConhecimentoService.gerar_slug(nome_t)
                tag_obj = KbTag.query.filter_by(slug=slug_tag).first()
                if not tag_obj:
                    tag_obj = KbTag(nome=nome_t, slug=slug_tag)
                    db.session.add(tag_obj)
                artigo.tags.append(tag_obj)

        db.session.commit()
        flash("Artigo atualizado com sucesso!", "success")
        return redirect(url_for('conhecimento.ver_artigo', slug=artigo.slug))

    categorias = KbCategoria.query.filter_by(ativo=True).order_by(KbCategoria.ordem).all()
    tags_string = ", ".join([t.nome for t in artigo.tags])
    return render_template(
        'conhecimento/editor_artigo.html',
        categorias=categorias,
        artigo=artigo,
        tags_string=tags_string
    )


@conhecimento_bp.route('/admin/artigo/<int:artigo_id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_artigo(artigo_id):
    """Exclusão de artigo."""
    artigo = db.session.get(KbArtigo, artigo_id)
    if not artigo:
        abort(404)

    titulo = artigo.titulo
    db.session.delete(artigo)
    db.session.commit()
    flash(f"Artigo '{titulo}' excluído com sucesso.", "success")
    return redirect(url_for('conhecimento.admin_dashboard'))


@conhecimento_bp.route('/admin/solicitacao/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def atualizar_solicitacao(id):
    """Aprova, rejeita ou conclui uma solicitação de usuário."""
    solicitacao = db.session.get(KbSolicitacao, id)
    if not solicitacao:
        abort(404)

    novo_status = request.form.get('status', 'pendente')
    resposta = request.form.get('resposta', '').strip()

    solicitacao.status = novo_status
    solicitacao.resposta_admin = resposta if resposta else None
    solicitacao.data_resolucao = datetime.now()
    db.session.commit()

    flash(f"Solicitação #{id} atualizada para '{novo_status}'.", "success")
    return redirect(url_for('conhecimento.admin_dashboard'))


@conhecimento_bp.route('/admin/categoria/nova', methods=['POST'])
@login_required
@admin_required
def nova_categoria():
    """Adiciona nova categoria à base de conhecimento."""
    nome = request.form.get('nome', '').strip()
    icone = request.form.get('icone', 'bi-journal-bookmark').strip()
    descricao = request.form.get('descricao', '').strip()

    if not nome:
        flash("Nome da categoria é obrigatório.", "warning")
        return redirect(url_for('conhecimento.admin_dashboard'))

    slug = ConhecimentoService.gerar_slug(nome)
    if KbCategoria.query.filter_by(slug=slug).first():
        flash("Já existe uma categoria com este nome.", "warning")
        return redirect(url_for('conhecimento.admin_dashboard'))

    cat = KbCategoria(nome=nome, slug=slug, icone=icone, descricao=descricao)
    db.session.add(cat)
    db.session.commit()

    flash(f"Categoria '{nome}' criada com sucesso!", "success")
    return redirect(url_for('conhecimento.admin_dashboard'))
