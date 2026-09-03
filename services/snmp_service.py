import asyncio

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
)


async def consultar_impressora_async(ip_address, community="public"):
    """
    Consulta assíncrona os dados SNMP essenciais de uma impressora Brother.
    """

    snmp_engine = SnmpEngine()

    try:
        # Configuração do transporte SNMP
        transport = await UdpTransportTarget.create(
            (ip_address, 161),
            timeout=2,
            retries=1
        )

    except Exception as e:
        return {
            "erro": f"Falha no transporte UDP: {str(e)}"
        }

    # ==========================================================
    # OIDs CONSULTADOS
    # ==========================================================

    oids_alvo = {

        # Número de série
        "serial":
            "1.3.6.1.2.1.43.5.1.1.17.1",

        # Total de páginas impressas
        "paginas":
            "1.3.6.1.2.1.43.10.2.1.4.1.1",

        # ======================================================
        # TONER - BROTHER PRIVATE MIB
        # ======================================================
        #
        # A Brother DCP-8157DN retorna o percentual diretamente
        # através deste OID.
        #
        "toner_porcentagem":
            "1.3.6.1.4.1.1240.2.3.4.1.11.0",

        # ======================================================
        # CILINDRO - PRINTER MIB
        # ======================================================

        # Capacidade atual do cilindro
        "cilindro_atual":
            "1.3.6.1.2.1.43.11.1.1.9.1.2",

        # Capacidade máxima do cilindro
        "cilindro_max":
            "1.3.6.1.2.1.43.11.1.1.8.1.2",
    }

    resultados = {}

    # ==========================================================
    # CONSULTA SNMP
    # ==========================================================

    try:

        for chave, oid_str in oids_alvo.items():

            error_indication, error_status, error_index, var_binds = await get_cmd(
                snmp_engine,
                CommunityData(
                    community,
                    mpModel=1
                ),
                transport,
                ContextData(),
                ObjectType(
                    ObjectIdentity(oid_str)
                )
            )

            # Erro na consulta
            if error_indication or error_status:

                resultados[chave] = None

            else:

                for var_bind in var_binds:

                    valor = var_bind[1]

                    resultados[chave] = valor.prettyPrint()

    except Exception as e:

        resultados["erro"] = str(e)

    finally:

        snmp_engine.close_dispatcher()

    # ==========================================================
    # MONTA RESULTADO FINAL
    # ==========================================================

    dados_formatados = {

        "serial":
            resultados.get("serial"),

        "paginas_impressas":
            int(
                resultados.get("paginas", 0)
                or 0
            ),

        "toner_porcentagem":
            None,

        "cilindro_porcentagem":
            None,
    }

    # ==========================================================
    # CÁLCULO / LEITURA DO TONER
    # ==========================================================

    try:

        toner = float(
            resultados.get(
                "toner_porcentagem"
            )
        )

        # Garante que o percentual esteja entre 0 e 100
        if 0 <= toner <= 100:

            dados_formatados["toner_porcentagem"] = round(
                toner,
                2
            )

    except (TypeError, ValueError):

        dados_formatados["toner_porcentagem"] = None

    # ==========================================================
    # CÁLCULO DA PORCENTAGEM DO CILINDRO
    # ==========================================================

    try:

        cilindro_atual = float(
            resultados.get(
                "cilindro_atual",
                0
            )
        )

        cilindro_max = float(
            resultados.get(
                "cilindro_max",
                0
            )
        )

        if cilindro_max > 0:

            porcentagem_cilindro = (
                cilindro_atual / cilindro_max
            ) * 100

            # Garante que o resultado fique entre 0 e 100
            dados_formatados["cilindro_porcentagem"] = round(
                max(
                    0,
                    min(
                        100,
                        porcentagem_cilindro
                    )
                ),
                2
            )

    except (TypeError, ValueError):

        dados_formatados["cilindro_porcentagem"] = None

    return dados_formatados


def consultar_impressora(ip_address, community="public"):
    """
    Função síncrona wrapper para facilitar a chamada
    dentro das rotas e serviços Flask.
    """

    return asyncio.run(
        consultar_impressora_async(
            ip_address,
            community
        )
    )


# ==============================================================
# TESTE DIRETO
# ==============================================================

if __name__ == "__main__":

    resultado = consultar_impressora(
        "10.90.1.16"
    )

    print(resultado)