from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
import re

db = SQLAlchemy()

class Chamado(db.Model):
    __tablename__ = 'chamados'

    id = db.Column(db.Integer, primary_key=True)
    
    usuario_id = db.Column(
        db.Integer, 
        db.ForeignKey('usuarios.id'), 
        nullable=False
    )
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='chamados')


    solicitante = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(100), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    prioridade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Aberto')

    data_abertura = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    data_fechamento = db.Column(db.DateTime, nullable=True)

    tecnico_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=True
    )
    tecnico = db.relationship('Usuario', foreign_keys=[tecnico_id], backref='chamados_atendidos')

    # Integracao com GLPI (Campos de Rastreabilidade e Idempotencia)
    origem = db.Column(db.String(20), nullable=False, default='local')
    glpi_id = db.Column(db.Integer, unique=True, nullable=True, index=True)
    glpi_numero = db.Column(db.String(50), nullable=True)


class GlpiSyncLog(db.Model):
    """Registro de auditoria e controle de cursor para sincronizacao com o GLPI."""
    __tablename__ = 'glpi_sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    data_execucao = db.Column(db.DateTime, default=datetime.now, nullable=False)
    tickets_encontrados = db.Column(db.Integer, default=0)
    tickets_importados = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), nullable=False, default='Sucesso')
    mensagem = db.Column(db.Text, nullable=True)
    ultimo_ticket_id = db.Column(db.Integer, nullable=True)
    ultima_data_ticket = db.Column(db.DateTime, nullable=True)


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(
        db.Integer, 
        primary_key=True
        )
    nome = db.Column(
        db.String(100), 
        nullable=False
    )
    email = db.Column(
        db.String(100), 
        unique=True, 
        nullable=False
        )
    password = db.Column(
        db.String(200), 
        nullable=False
    )
    perfil = db.Column(
        db.String(30), 
        nullable=False, 
        default='usuario'
    )
    status = db.Column(
        db.String(20), 
        nullable=False, 
        default='pendente'
    )
    
    @property
    def is_admin(self):
        return self.perfil == 'admin'
    
    @property
    def is_operador(self):
        return self.perfil == 'operador'
    
    @property
    def is_tecnico_impressora(self):
        return self.perfil == 'tecnicoImpressora'
    
    
class Impressora(db.Model):
    __tablename__ = "impressoras"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100))
    ip = db.Column(db.String(45), unique=True)
    modelo = db.Column(db.String(100))

    # Localização fisica
    andar = db.Column(db.String(50), default="Não Informado")
    sala = db.Column(db.String(50), default="Não Informado")
    
    # Chave estrangeira para a tabela EstoqueSuprimento
    suprimento_id = db.Column(
        db.Integer,
        db.ForeignKey('estoque_suprimentos.id'),
        nullable=True,
    )
    suprimento = db.relationship('EstoqueSuprimento', backref='impressoras')

    online = db.Column(
        db.Boolean,
        default=False
    )

    toner_preto = db.Column(
        db.Integer,
        nullable=True
    )

    toner_ciano = db.Column(
        db.Integer,
        nullable=True
    )

    toner_magenta = db.Column(
        db.Integer,
        nullable=True
    )

    toner_amarelo = db.Column(
        db.Integer,
        nullable=True
    )

    paginas_impressas = db.Column(
        db.Integer,
        default=0
    )

    ultimo_check = db.Column(
        db.DateTime
    )

    cilindro = db.Column(
        db.Integer,
        nullable=True
    )

    nivel_papel = db.Column(
        db.Integer,
        nullable=True
    )

    serial = db.Column(
        db.String(100)
    )

    status_detalhado = db.Column(
        db.String(255)
    )

    fabricante = db.Column(
        db.String(50)
    )

    ultimo_erro = db.Column(
        db.String(255)
    )

    ultima_sincronizacao = db.Column(
        db.DateTime
    )

    necessita_atencao = db.Column(
        db.Boolean,
        default=False
    )

    mac_address = db.Column(
        db.String(50),
        nullable=True
    )

    contato = db.Column(
        db.String(100),
        nullable=True
    )

    local = db.Column(
        db.String(100),
        nullable=True
    )

    @property
    def familia_suprimento(self):
        return self.suprimento

    @property
    def is_virtual(self):
        """Identifica se é uma fila virtual de software (PDF, Generic, etc.) em vez de hardware físico."""
        if not self.nome:
            return False
        termos = (
            'pdf24',
            'generic',
            'text only',
            'print to pdf',
            'xps',
            'fax',
            'onenote',
            'anydesk',
            'adobe pdf'
        )
        nome_lower = self.nome.lower()
        return any(t in nome_lower for t in termos)


# =========================================================
# TABELAS DE ESTOQUE E SUPRIMENTOS (BANCO UNIFICADO)
# =========================================================

class EstoqueSuprimento(db.Model):
    __tablename__ = "estoque_suprimentos"

    id = db.Column(db.Integer, primary_key=True)
    nome_familia = db.Column(db.String(100), nullable=False, unique=True)
    quantidade_toner = db.Column(db.Integer, default=0, nullable=False)
    quantidade_cilindro = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo = db.Column(db.Integer, default=2, nullable=False)

class HistoricoSuprimento(db.Model):
    __tablename__ = "historico_suprimentos"

    id = db.Column(db.Integer, primary_key=True)
    impressora_id = db.Column(
        db.Integer,
        db.ForeignKey('impressoras.id'),
        nullable=True
    )
    impressora = db.relationship('Impressora', backref='historico_retiradas')

    familia_id = db.Column(
        db.Integer,
        db.ForeignKey('estoque_suprimentos.id'),
        nullable=True
    )
    familia = db.relationship('EstoqueSuprimento', backref='historico_suprimentos')

    tipo_insumo = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=-1)
    usuario_responsavel = db.Column(db.String(100), nullable=False)
    data_retirada = db.Column(db.DateTime, default=datetime.now)

    @property
    def responsavel_nome(self):
        """Retorna o nome do usuário sem o sufixo de motivo de ajuste."""
        if not self.usuario_responsavel:
            return "Sistema"
        match = re.match(r'^(.*?)\s*\(.*?\)$', self.usuario_responsavel.strip())
        if match and match.group(1).strip():
            return match.group(1).strip()
        return self.usuario_responsavel.strip()

    @property
    def destino_detalhe(self):
        """
        Identifica se a retirada foi vinculada a uma impressora física
        ou a um ajuste de setor manual.
        """
        if self.impressora:
            local = (self.impressora.local or "").strip()
            if not local and self.impressora.andar and self.impressora.andar != "Não Informado":
                local = f"{self.impressora.andar} - {self.impressora.sala}"
            return {
                "tipo": "impressora",
                "label": self.impressora.nome,
                "local": local or "Local não informado"
            }
        if self.usuario_responsavel:
            match = re.match(r'^.*?\((?:Ajuste:\s*)?(.*?)\)$', self.usuario_responsavel.strip())
            if match and match.group(1).strip():
                return {
                    "tipo": "setor",
                    "label": match.group(1).strip(),
                    "local": "Ajuste de estoque"
                }
        return {
            "tipo": "geral",
            "label": "Ajuste manual",
            "local": None
        }


# =========================================================
# BASE DE CONHECIMENTO (KNOWLEDGE BASE / WIKI / PROCEDIMENTOS)
# =========================================================

class KbCategoria(db.Model):
    __tablename__ = 'kb_categorias'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    icone = db.Column(db.String(40), default='bi-journal-bookmark')
    descricao = db.Column(db.String(255), nullable=True)
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)

    artigos = db.relationship('KbArtigo', backref='categoria', lazy='dynamic')


# Tabela associativa many-to-many entre Artigos e Tags
artigo_tags = db.Table(
    'kb_artigo_tags',
    db.Column('artigo_id', db.Integer, db.ForeignKey('kb_artigos.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('kb_tags.id', ondelete='CASCADE'), primary_key=True)
)


class KbTag(db.Model):
    __tablename__ = 'kb_tags'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)


class KbArtigo(db.Model):
    __tablename__ = 'kb_artigos'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    resumo = db.Column(db.String(350), nullable=True)
    conteudo_md = db.Column(db.Text, nullable=False)

    categoria_id = db.Column(db.Integer, db.ForeignKey('kb_categorias.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    status = db.Column(db.String(20), default='publicado')  # 'rascunho', 'publicado', 'arquivado'
    tempo_leitura_min = db.Column(db.Integer, default=3)
    visualizacoes = db.Column(db.Integer, default=0)

    # Avaliações
    votos_util = db.Column(db.Integer, default=0)
    votos_inutil = db.Column(db.Integer, default=0)

    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relacionamentos
    autor = db.relationship('Usuario', backref='artigos_kb')
    tags = db.relationship('KbTag', secondary=artigo_tags, backref=db.backref('artigos', lazy='dynamic'))
    feedbacks = db.relationship('KbFeedback', backref='artigo', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def total_votos(self):
        return (self.votos_util or 0) + (self.votos_inutil or 0)

    @property
    def percentual_util(self):
        total = self.total_votos
        if total == 0:
            return 100
        return int(round((self.votos_util / total) * 100))

    @property
    def score_relevancia(self):
        # Ponderação: visualizações + (votos úteis * 5) - (votos inúteis * 3)
        return (self.visualizacoes or 0) + ((self.votos_util or 0) * 5) - ((self.votos_inutil or 0) * 3)


class KbFeedback(db.Model):
    __tablename__ = 'kb_feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    artigo_id = db.Column(db.Integer, db.ForeignKey('kb_artigos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    util = db.Column(db.Boolean, nullable=False)  # True = 👍, False = 👎
    comentario = db.Column(db.Text, nullable=True)
    data = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship('Usuario', backref='feedbacks_kb')


class KbSolicitacao(db.Model):
    __tablename__ = 'kb_solicitacoes'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('kb_categorias.id'), nullable=True)
    descricao = db.Column(db.Text, nullable=False)
    justificativa = db.Column(db.Text, nullable=True)
    prioridade = db.Column(db.String(20), default='normal')  # 'baixa', 'normal', 'alta'

    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    status = db.Column(db.String(20), default='pendente')  # 'pendente', 'aprovada', 'rejeitada', 'concluida'
    resposta_admin = db.Column(db.Text, nullable=True)
    artigo_gerado_id = db.Column(db.Integer, db.ForeignKey('kb_artigos.id'), nullable=True)

    data_envio = db.Column(db.DateTime, default=datetime.now)
    data_resolucao = db.Column(db.DateTime, nullable=True)

    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id], backref='solicitacoes_kb')
    categoria = db.relationship('KbCategoria', foreign_keys=[categoria_id])
    artigo_gerado = db.relationship('KbArtigo', foreign_keys=[artigo_gerado_id])


# =========================================================================
# MODELOS: ITENS DA SALA (ESTOQUE INTERNO TI ENTRE SALAS)
# =========================================================================

class ItemSala(db.Model):
    __tablename__ = 'itens_sala'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, index=True)
    categoria = db.Column(db.String(60), nullable=False, default='Periféricos', index=True)
    estoque_minimo = db.Column(db.Integer, default=2, nullable=False)
    unidade = db.Column(db.String(20), default='UN')
    descricao = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relacionamentos
    estoques = db.relationship('ItemSalaEstoque', backref='item', cascade='all, delete-orphan', lazy='joined')
    movimentacoes = db.relationship('ItemSalaMovimentacao', backref='item', cascade='all, delete-orphan', lazy='dynamic', order_by='ItemSalaMovimentacao.created_at.desc()')

    @property
    def total_estoque(self):
        return sum(e.quantidade for e in self.estoques)

    @property
    def estoque_sala_principal(self):
        for e in self.estoques:
            if e.sala == 'Sala Principal':
                return e.quantidade
        return 0

    @property
    def estoque_sala_terceiro(self):
        for e in self.estoques:
            if e.sala == 'Sala TI - 3º Andar':
                return e.quantidade
        return 0

    @property
    def is_estoque_baixo(self):
        return self.total_estoque <= (self.estoque_minimo or 0)

    def estoque_por_sala(self, nome_sala):
        for e in self.estoques:
            if e.sala == nome_sala:
                return e.quantidade
        return 0


class ItemSalaEstoque(db.Model):
    __tablename__ = 'itens_sala_estoque'
    __table_args__ = (
        db.UniqueConstraint('item_id', 'sala', name='uq_item_sala'),
    )

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('itens_sala.id', ondelete='CASCADE'), nullable=False)
    sala = db.Column(db.String(60), nullable=False, index=True)  # 'Sala Principal' ou 'Sala TI - 3º Andar'
    quantidade = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class ItemSalaMovimentacao(db.Model):
    __tablename__ = 'itens_sala_movimentacoes'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('itens_sala.id', ondelete='CASCADE'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, index=True)  # 'saida', 'entrada', 'transferencia', 'ajuste'
    quantidade = db.Column(db.Integer, nullable=False)
    sala_origem = db.Column(db.String(60), nullable=True)
    sala_destino = db.Column(db.String(60), nullable=True)
    entregue_por = db.Column(db.String(120), nullable=True)  # Quem entregou (Técnico TI)
    recebido_por = db.Column(db.String(120), nullable=True)  # Quem retirou
    setor = db.Column(db.String(120), nullable=True, index=True)  # Setor de destino
    origem_fornecedor = db.Column(db.String(120), nullable=True)  # Compra, Fornecedor, etc.
    observacao = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


