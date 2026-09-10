import asyncio

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
    next_cmd,
)


# ==================================================================
# OIDs FIXOS (independem de modelo)
# ==================================================================

OID_SERIAL = "1.3.6.1.2.1.43.5.1.1.17.1"
OID_PAGINAS = "1.3.6.1.2.1.43.10.2.1.4.1.1"

# Base da tabela de descrições de suprimentos (Printer-MIB / RFC 3805)
# Formato completo de cada linha: 1.3.6.1.2.1.43.11.1.1.6.1.<indice>
OID_BASE_DESCRICAO = "1.3.6.1.2.1.43.11.1.1.6.1"

# Colunas de nível/capacidade máxima (mesma tabela, mesmo índice)
OID_BASE_NIVEL = "1.3.6.1.2.1.43.11.1.1.9.1"
OID_BASE_MAX = "1.3.6.1.2.1.43.11.1.1.8.1"

# Valores "sentinela" definidos pela RFC 3805 para prtMarkerSuppliesLevel
NIVEL_NAO_DISPONIVEL = -1   # não foi possível obter o nível
NIVEL_SEM_UNIDADE = -2      # nível existe, mas não é medido em unidades quantificáveis
NIVEL_SEM_RESTRICAO = -3    # não há como estimar (ex.: suprimento "ilimitado")


# ==================================================================
# DESCOBERTA DINÂMICA DO ÍNDICE DE CADA SUPRIMENTO
# ==================================================================

async def _descobrir_indices_suprimentos(engine, community, transport, context):
    """
    Percorre (SNMP WALK) a tabela prtMarkerSuppliesDescription para
    descobrir, para ESTA impressora especificamente, em qual índice
    fica o "Toner Preto" e em qual fica o "Cilindro/Drum/Tambor".

    Isso substitui o uso de índices fixos (ex: sempre ".2"), que não
    são padronizados entre modelos/fabricantes diferentes.

    Retorna um dicionário: {"toner": indice_ou_None, "cilindro": indice_ou_None}
    """

    indices = {"toner": None, "cilindro": None}

    oid_atual = OID_BASE_DESCRICAO
    max_iteracoes = 30  # segurança contra loop infinito

    for _ in range(max_iteracoes):

        error_indication, error_status, error_index, var_binds = await next_cmd(
            engine,
            CommunityData(community, mpModel=1),
            transport,
            context,
            ObjectType(ObjectIdentity(oid_atual)),
        )

        if error_indication or error_status:
            break

        if not var_binds:
            break

        oid_retornado, valor = var_binds[0]
        oid_str = str(oid_retornado)

        # Saiu da subárvore da tabela de descrições -> fim do walk
        if not oid_str.startswith(OID_BASE_DESCRICAO + "."):
            break

        # O último número do OID é o índice do suprimento na tabela
        indice = oid_str.rsplit(".", 1)[-1]
        descricao = valor.prettyPrint().lower()

        if indices["toner"] is None and (
            "black" in descricao or "preto" in descricao
        ) and "toner" in descricao:
            indices["toner"] = indice

        if indices["cilindro"] is None and (
            "drum" in descricao
            or "cilindro" in descricao
            or "tambor" in descricao
        ):
            indices["cilindro"] = indice

        # Já achou os dois, não precisa continuar o walk
        if indices["toner"] and indices["cilindro"]:
            break

        oid_atual = oid_str

    return indices


def _calcular_percentual(nivel_str, maximo_str):
    """
    Calcula o percentual (0-100) a partir do nível atual e capacidade
    máxima retornados via SNMP, tratando os valores sentinela da
    RFC 3805 (-1, -2, -3), que NÃO são percentuais e não devem ser
    usados em contas.
    """

    try:
        nivel = float(nivel_str)
        maximo = float(maximo_str)
    except (TypeError, ValueError):
        return None

    # Valores sentinela: não é possível calcular um percentual real
    if nivel < 0 or maximo <= 0:
        return None

    percentual = (nivel / maximo) * 100

    return round(max(0, min(100, percentual)), 2)


# ==================================================================
# CONSULTA COMPLETA DE UMA IMPRESSORA
# ==================================================================

async def consultar_impressora_async(ip_address, community="public"):
    """
    Consulta assíncrona os dados SNMP essenciais de uma impressora,
    descobrindo dinamicamente os índices de toner preto e cilindro
    (funciona para qualquer modelo/fabricante compatível com a
    Printer-MIB padrão), e faz a leitura de nível/capacidade em UMA
    única requisição SNMP (GET com múltiplos OIDs), em vez de uma
    requisição por OID.
    """

    snmp_engine = SnmpEngine()

    try:
        transport = await UdpTransportTarget.create(
            (ip_address, 161),
            timeout=2,
            retries=1
        )
    except Exception as e:
        snmp_engine.close_dispatcher()
        return {
            "erro": f"Falha no transporte UDP: {str(e)}"
        }

    context = ContextData()

    try:

        # ----------------------------------------------------------
        # 1. Descobre em qual índice está o toner preto e o cilindro
        #    (1 walk curto, específico desta impressora)
        # ----------------------------------------------------------

        indices = await _descobrir_indices_suprimentos(
            snmp_engine, community, transport, context
        )

        indice_toner = indices["toner"]
        indice_cilindro = indices["cilindro"]

        if not indice_toner and not indice_cilindro:
            return {
                "erro": (
                    "Não foi possível localizar os índices de "
                    "toner/cilindro via SNMP nesta impressora."
                )
            }

        # ----------------------------------------------------------
        # 2. Monta a lista de OIDs a consultar em UMA única PDU
        # ----------------------------------------------------------

        var_binds_solicitados = [
            ("serial", OID_SERIAL),
            ("paginas", OID_PAGINAS),
        ]

        if indice_toner:
            var_binds_solicitados.append(
                ("toner_nivel", f"{OID_BASE_NIVEL}.{indice_toner}")
            )
            var_binds_solicitados.append(
                ("toner_max", f"{OID_BASE_MAX}.{indice_toner}")
            )

        if indice_cilindro:
            var_binds_solicitados.append(
                ("cilindro_nivel", f"{OID_BASE_NIVEL}.{indice_cilindro}")
            )
            var_binds_solicitados.append(
                ("cilindro_max", f"{OID_BASE_MAX}.{indice_cilindro}")
            )

        object_types = [
            ObjectType(ObjectIdentity(oid))
            for _, oid in var_binds_solicitados
        ]

        error_indication, error_status, error_index, var_binds = await get_cmd(
            snmp_engine,
            CommunityData(community, mpModel=1),
            transport,
            context,
            *object_types,
        )

        if error_indication or error_status:
            return {
                "erro": f"Erro SNMP: {error_indication or error_status}"
            }

        resultados = {}
        for (chave, _), var_bind in zip(var_binds_solicitados, var_binds):
            resultados[chave] = var_bind[1].prettyPrint()

    except Exception as e:
        return {"erro": str(e)}

    finally:
        snmp_engine.close_dispatcher()

    # ==========================================================
    # MONTA RESULTADO FINAL
    # ==========================================================

    dados_formatados = {
        "serial": resultados.get("serial"),
        "paginas_impressas": int(resultados.get("paginas", 0) or 0),
        "toner_porcentagem": _calcular_percentual(
            resultados.get("toner_nivel"),
            resultados.get("toner_max"),
        ),
        "cilindro_porcentagem": _calcular_percentual(
            resultados.get("cilindro_nivel"),
            resultados.get("cilindro_max"),
        ),
    }

    return dados_formatados


# ==================================================================
# CONSULTA EM LOTE (PARALELA) DE VÁRIAS IMPRESSORAS
# ==================================================================

async def consultar_impressoras_async(lista_ips, community="public"):
    """
    Consulta várias impressoras EM PARALELO (asyncio.gather), em vez
    de uma por uma. O tempo total passa a ser aproximadamente o da
    impressora mais lenta, e não a SOMA do tempo de todas.

    Retorna um dicionário {ip: dados_formatados}.
    """

    tarefas = [
        consultar_impressora_async(ip, community)
        for ip in lista_ips
    ]

    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    saida = {}
    for ip, resultado in zip(lista_ips, resultados):
        if isinstance(resultado, Exception):
            saida[ip] = {"erro": str(resultado)}
        else:
            saida[ip] = resultado

    return saida


# ==================================================================
# WRAPPERS SÍNCRONOS (para uso em rotas/serviços Flask)
# ==================================================================

def consultar_impressora(ip_address, community="public"):
    """
    Função síncrona wrapper para consultar UMA impressora.
    Mantida para compatibilidade com código existente.
    """

    return asyncio.run(
        consultar_impressora_async(ip_address, community)
    )


def consultar_impressoras_bulk(lista_ips, community="public"):
    """
    Função síncrona wrapper para consultar VÁRIAS impressoras em
    paralelo de uma vez. Use esta função em vez de chamar
    `consultar_impressora` dentro de um loop.
    """

    return asyncio.run(
        consultar_impressoras_async(lista_ips, community)
    )


# ==================================================================
# TESTE DIRETO
# ==================================================================

if __name__ == "__main__":

    resultado = consultar_impressora(
        "10.90.1.16"
    )

    print(resultado)