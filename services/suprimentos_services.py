from models import db, EstoqueSuprimento, HistoricoSuprimento, Impressora
from datetime import datetime

class SuprimentosService:

    @staticmethod
    def listar_familias():
        # Retorna todas as famílias de suprimentos cadastradas.
        return EstoqueSuprimento.query.all()

    @staticmethod
    def obter_familia(familia_id):
        # Busca uma família específica pelo ID.
        return db.session.get(EstoqueSuprimento, familia_id)

    @staticmethod
    def criar_familia(nome_familia, quantidade_toner, quantidade_cilindro, estoque_minimo):
        # Cadastra um novo grupo/família de suprimentos no banco isolado.
        existente = EstoqueSuprimento.query.filter_by(nome_familia=nome_familia).first()
        if existente:
            return None, "Já existe uma família de suprimentos com esse nome."

        nova_familia = EstoqueSuprimento(
            nome_familia=nome_familia,
            quantidade_toner=int(quantidade_toner or 0),
            quantidade_cilindro=int(quantidade_cilindro or 0),
            estoque_minimo=int(estoque_minimo or 2)
        )

        db.session.add(nova_familia)
        db.session.commit()
        return nova_familia, "Família de suprimentos cadastrada com sucesso!"

    @staticmethod
    def adicionar_estoque(familia_id, qtd_toner_add, qtd_cilindro_add):
        # Adiciona novas unidades ao estoque físico (ex: compra ou chegada de insumos).
        familia = SuprimentosService.obter_familia(familia_id)
        if not familia:
            return False, "Família de suprimentos não encontrada."

        if qtd_toner_add:
            familia.quantidade_toner += int(qtd_toner_add)
        if qtd_cilindro_add:
            familia.quantidade_cilindro += int(qtd_cilindro_add)

        db.session.commit()
        return True, "Estoque atualizado com sucesso!"

    @staticmethod
    def retirar_insumo(impressora_id, tipo_insumo, usuario_nome):
        """
        Efetua a baixa (-1) no estoque da família vinculada à impressora 
        e registra a auditoria no histórico.
        """
        impressora = db.session.get(Impressora, impressora_id)
        if not impressora:
            return False, "Impressora não encontrada."
        
        if not impressora.suprimento_id or not impressora.familia_suprimento:
            return False, f"A impressora '{impressora.nome}' não está vinculada a nenhuma família de suprimentos."

        familia = impressora.familia_suprimento

        if tipo_insumo == 'toner':
            if familia.quantidade_toner <= 0:
                return False, f"Estoque esgotado para o toner da família '{familia.nome_familia}'!"
            familia.quantidade_toner -= 1
        elif tipo_insumo == 'cilindro':
            if familia.quantidade_cilindro <= 0:
                return False, f"Estoque esgotado para o cilindro da família '{familia.nome_familia}'!"
            familia.quantidade_cilindro -= 1
        else:
            return False, "Tipo de insumo inválido."

        # Registra a movimentação no histórico de auditoria
        historico = HistoricoSuprimento(
            impressora_id=impressora.id,
            tipo_insumo=tipo_insumo,
            quantidade=-1,
            usuario_responsavel=usuario_nome,
            data_retirada=datetime.now()
        )

        db.session.add(historico)
        db.session.commit()
        return True, f"Retirada de 1 {tipo_insumo} registrada para a impressora {impressora.nome}."

    @staticmethod
    def listar_historico(limite=50):
        """Retorna as últimas movimentações/retiradas para auditoria."""
        return HistoricoSuprimento.query.order_by(HistoricoSuprimento.data_retirada.desc()).limit(limite).all()
    
    @staticmethod
    def ajustar_estoque(familia_id, tipo_insumo, quantidade, motivo, usuario_nome):
        """
        Ajuste manual de estoque (correção, perda, vencimento, etc).
        'quantidade' pode ser positiva (entrada) ou negativa (saída),
        e não está vinculado a nenhuma impressora específica.
        """
        familia = SuprimentosService.obter_familia(familia_id)
        if not familia:
            return False, "Família de suprimentos não encontrada."

        if tipo_insumo not in ('toner', 'cilindro'):
            return False, "Tipo de insumo inválido."

        try:
            quantidade = int(quantidade)
        except (TypeError, ValueError):
            return False, "Quantidade inválida."

        if quantidade == 0:
            return False, "Informe uma quantidade diferente de zero."

        if tipo_insumo == 'toner':
            novo_valor = familia.quantidade_toner + quantidade
            if novo_valor < 0:
                return False, f"Ajuste inválido: estoque de toner ficaria negativo ({novo_valor})."
            familia.quantidade_toner = novo_valor
        else:
            novo_valor = familia.quantidade_cilindro + quantidade
            if novo_valor < 0:
                return False, f"Ajuste inválido: estoque de cilindro ficaria negativo ({novo_valor})."
            familia.quantidade_cilindro = novo_valor

        # Registra no histórico de auditoria (sem vínculo com impressora)
        historico = HistoricoSuprimento(
            impressora_id=None,
            tipo_insumo=tipo_insumo,
            quantidade=quantidade,
            usuario_responsavel=f"{usuario_nome} (Ajuste: {motivo})",
            data_retirada=datetime.now()
        )

        db.session.add(historico)
        db.session.commit()

        sinal = "adicionadas" if quantidade > 0 else "removidas"
        return True, f"{abs(quantidade)} unidade(s) de {tipo_insumo} {sinal} da família '{familia.nome_familia}'."