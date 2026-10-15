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
OID_CONTACT = "1.3.6.1.2.1.1.4.0"
OID_LOCATION = "1.3.6.1.2.1.1.6.0"
OID_BASE_IF_PHYS = "1.3.6.1.2.1.2.2.1.6"

# Base da tabela de descrições de suprimentos (Printer-MIB / RFC 3805)
# Formato completo de cada linha: 1.3.6.1.2.1.43.11.1.1.6.1.<indice>
OID_BASE_DESCRICAO = "1.3.6.1.2.1.43.11.1.1.6.1"

# Colunas de nível/capacidade máxima (mesma tabela, mesmo índice)
OID_BASE_NIVEL = "1.3.6.1.2.1.43.11.1.1.9.1"
OID_BASE_MAX = "1.3.6.1.2.1.43.11.1.1.8.1"

# OID proprietário Brother (brInfoMaintenance - MIB Brother Enterprise 2435)
# Retorna carga hexadecimal TLV com níveis de toner, cilindro e contadores
OID_BROTHER_MAINTENANCE = "1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.8.0"

# OIDs de Status e Diagnóstico de Erros (RFC 2790 / RFC 3805)
OID_CONSOLE_DISPLAY = "1.3.6.1.2.1.43.16.5.1.2.1.1"     # prtConsoleDisplayBufferText (Texto do LCD da impressora)
OID_HR_PRINTER_ERROR = "1.3.6.1.2.1.25.3.5.1.2.1"       # hrPrinterDetectedErrorState (Bits de erro de hardware)
OID_HR_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"      # hrPrinterStatus (1=other, 2=unknown, 3=idle, 4=printing, 5=warmup)


def _decodificar_erros_hardware(error_state_bytes):
    """
    Decodifica os bits da RFC 2790 (hrPrinterDetectedErrorState).
    Identifica falhas físicas reais da impressora (atolamento, portas abertas, falta de suprimento).
    """
    erros = []
    if not error_state_bytes:
        return erros

    b0 = error_state_bytes[0] if len(error_state_bytes) > 0 else 0
    b1 = error_state_bytes[1] if len(error_state_bytes) > 1 else 0

    if b0 & 0x04:
        erros.append("Papel Atolado (Paper Jam)")
    if b0 & 0x08:
        erros.append("Porta / Tampa Aberta (Door Open)")
    if b0 & 0x40:
        erros.append("Bandeja Sem Papel (No Paper)")
    elif b0 & 0x80:
        erros.append("Pouco Papel (Low Paper)")
    if b0 & 0x10:
        erros.append("Toner Esgotado / Ausente")
    elif b0 & 0x20:
        erros.append("Toner em Nível Baixo")
    if b0 & 0x01:
        erros.append("Intervenção / Chamado Técnico Requerido")

    if b1 & 0x04:
        erros.append("Bandeja de Entrada Vazia")
    if b1 & 0x08:
        erros.append("Bandeja de Saída Cheia")
    if b1 & 0x80:
        erros.append("Bandeja de Entrada Ausente")
    if b1 & 0x20:
        erros.append("Cartucho de Suprimento Ausente")

    return erros


def _parse_brother_tlv(raw_bytes):
    """
    Decodifica o OID brInfoMaintenance da Brother (.1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.8.0).
    A carga é estruturada em blocos TLV:
      - Byte 0: Tipo do recurso (Tag) em hex (ex: '81', '6f', '41', etc.)
      - Byte 1: Subtipo (geralmente 0x01)
      - Byte 2: Comprimento dos dados (Length, geralmente 4 bytes ou 1-2 bytes)
      - Bytes 3..(3+Length): Valor numérico em big-endian
      - 0xFF: Marcador de fim de payload
    """
    if not raw_bytes:
        return {}

    pos = 0
    results = {}
    total_len = len(raw_bytes)

    while pos < total_len:
        if raw_bytes[pos] == 0xFF:
            break
        if pos + 3 > total_len:
            break
        tag = f"{raw_bytes[pos]:02x}"
        length = raw_bytes[pos + 2]
        if pos + 3 + length > total_len:
            break
        val_bytes = raw_bytes[pos + 3 : pos + 3 + length]
        results[tag] = int.from_bytes(val_bytes, "big")
        pos += 3 + length

    return results


def _normalizar_percentual_brother(val):
    """
    Converte o valor de suprimento da Brother em percentual (0 a 100):
    - Se o valor estiver entre 0 e 100: já é a porcentagem direta (ex: 70, 50, 100).
    - Se estiver em escala base 10000 (ex: 6700, 2800, 8400): divide por 100 -> 67%, 28%, 84%.
    """
    if val is None:
        return None
    try:
        num = float(val)
        if num < 0:
            return None
        if num <= 100:
            return round(num, 2)
        if num <= 10000:
            return round(num / 100.0, 2)
    except (ValueError, TypeError):
        return None
    return None


def _extrair_suprimentos_brother(raw_bytes):
    """
    Interpreta os códigos conhecidos da Brother para toner, cilindro e páginas.
    Tags mapeadas conforme documentação Brother SNMP:
      - Toner Preto: '81' (VAL_BLACK_TONER), 'a1' (VAL_BLACK_TONER_REMAIN), '6f' (VAL_BLACK_TONER_REMAIN)
      - Cilindro: '80' (VAL_BLACK_DRUM_REMAIN), '41' (VAL_DRUM_REMAIN)
      - Toners Coloridos: Ciano ('82','a2','70'), Magenta ('83','a3','71'), Amarelo ('84','a4','72')
      - Contador de páginas: '00' (Page Count em alguns modelos)
    """
    data = _parse_brother_tlv(raw_bytes)
    res = {}

    # Toner Preto
    for tag in ("81", "a1", "6f"):
        if tag in data:
            val = _normalizar_percentual_brother(data[tag])
            if val is not None:
                res["toner_preto"] = val
                break

    # Cilindro (Drum)
    for tag in ("80", "41"):
        if tag in data:
            val = _normalizar_percentual_brother(data[tag])
            if val is not None:
                res["cilindro"] = val
                break

    # Cores (para modelos coloridos)
    for tag in ("82", "a2", "70"):
        if tag in data:
            val = _normalizar_percentual_brother(data[tag])
            if val is not None:
                res["toner_ciano"] = val
                break

    for tag in ("83", "a3", "71"):
        if tag in data:
            val = _normalizar_percentual_brother(data[tag])
            if val is not None:
                res["toner_magenta"] = val
                break

    for tag in ("84", "a4", "72"):
        if tag in data:
            val = _normalizar_percentual_brother(data[tag])
            if val is not None:
                res["toner_amarelo"] = val
                break

    if "00" in data and data["00"] > 0:
        res["paginas"] = data["00"]

    return res

def _obter_mac_arp(ip):
    """Fallback para obter o MAC via cache ARP local do sistema operacional."""
    try:
        import subprocess, re
        res = subprocess.run(["arp", "-a", ip], capture_output=True, text=True, timeout=1)
        match = re.search(
            r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})",
            res.stdout
        )
        if match:
            return match.group(1).replace("-", ":").upper()
    except Exception:
        pass
    return None

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
            or "imaging unit" in descricao
            or "opc" in descricao
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

        indice_toner = indices.get("toner")
        indice_cilindro = indices.get("cilindro")

        # ----------------------------------------------------------
        # 2. Monta a lista de OIDs a consultar em UMA única PDU
        # ----------------------------------------------------------

        var_binds_solicitados = [
            ("serial", OID_SERIAL),
            ("paginas", OID_PAGINAS),
            ("contato", OID_CONTACT),
            ("local", OID_LOCATION),
            ("brother_maintenance", OID_BROTHER_MAINTENANCE),
            ("console_display", OID_CONSOLE_DISPLAY),
            ("hr_error", OID_HR_PRINTER_ERROR),
            ("hr_status", OID_HR_PRINTER_STATUS),
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

        resultados = {}
        brother_raw = None
        hr_error_raw = None
        if not (error_indication or error_status) and var_binds:
            for (chave, _), var_bind in zip(var_binds_solicitados, var_binds):
                val_obj = var_bind[1]
                val_str = val_obj.prettyPrint().strip()
                if val_str and "noSuchInstance" not in val_str and "noSuchObject" not in val_str:
                    if chave == "brother_maintenance":
                        try:
                            brother_raw = val_obj.asOctets() if hasattr(val_obj, "asOctets") else bytes(val_obj)
                        except Exception:
                            pass
                    elif chave == "hr_error":
                        try:
                            hr_error_raw = val_obj.asOctets() if hasattr(val_obj, "asOctets") else bytes(val_obj)
                        except Exception:
                            pass
                        resultados[chave] = val_str
                    else:
                        resultados[chave] = val_str

        # ----------------------------------------------------------
        # 3. Consulta Endereço MAC (SNMP e fallback ARP)
        # ----------------------------------------------------------
        mac_address = None
        try:
            err_ind, err_stat, err_idx, v_binds = await next_cmd(
                snmp_engine,
                CommunityData(community, mpModel=1),
                transport,
                context,
                ObjectType(ObjectIdentity(OID_BASE_IF_PHYS)),
            )
            if not (err_ind or err_stat) and v_binds:
                octetos = v_binds[0][1].asNumbers()
                if len(octetos) == 6:
                    mac_address = ":".join(f"{b:02X}" for b in octetos)
        except Exception:
            pass

        if not mac_address:
            mac_address = _obter_mac_arp(ip_address)

    except Exception as e:
        return {"erro": str(e)}

    finally:
        snmp_engine.close_dispatcher()

    # ==========================================================
    # MONTA RESULTADO FINAL (RFC 3805 + FALLBACK BROTHER + ERROS)
    # ==========================================================

    toner_perc = _calcular_percentual(
        resultados.get("toner_nivel"),
        resultados.get("toner_max"),
    )
    cilindro_perc = _calcular_percentual(
        resultados.get("cilindro_nivel"),
        resultados.get("cilindro_max"),
    )

    toner_ciano = None
    toner_magenta = None
    toner_amarelo = None

    # Se a impressora for Brother (ou respondeu brInfoMaintenance), decodifica o payload TLV:
    if brother_raw:
        suprimentos_brother = _extrair_suprimentos_brother(brother_raw)

        # 1. Toner Preto: se não obteve via Printer-MIB padrão (comum em Brother), usa o valor decodificado
        if toner_perc is None and "toner_preto" in suprimentos_brother:
            toner_perc = suprimentos_brother["toner_preto"]

        # 2. Cilindro: se não obteve via Printer-MIB padrão, usa o valor decodificado da Brother
        if cilindro_perc is None and "cilindro" in suprimentos_brother:
            cilindro_perc = suprimentos_brother["cilindro"]

        # 3. Toners Coloridos (para modelos Brother coloridos)
        toner_ciano = suprimentos_brother.get("toner_ciano")
        toner_magenta = suprimentos_brother.get("toner_magenta")
        toner_amarelo = suprimentos_brother.get("toner_amarelo")

        # 4. Total de páginas (fallback se RFC 3805 não retornou ou veio zerado)
        if not resultados.get("paginas") and "paginas" in suprimentos_brother:
            resultados["paginas"] = suprimentos_brother["paginas"]

    # Decodificação de Erros de Hardware
    erros_hardware = _decodificar_erros_hardware(hr_error_raw)

    # Interpretação do Display / Visor LCD
    visor_bruto = resultados.get("console_display", "")
    visor_alerta = None
    if visor_bruto:
        visor_limpo = " ".join(visor_bruto.split()).strip()
        termos_neutros = {
            "em espera", "ready", "pronta", "pronto", "sleep", "deep sleep",
            "modo economia", "powersave", "aguardando", "imprimindo", "printing", "warmup"
        }
        if visor_limpo.lower() not in termos_neutros and not any(visor_limpo.lower() == t for t in termos_neutros):
            visor_alerta = visor_limpo

    dados_formatados = {
        "serial": resultados.get("serial"),
        "paginas_impressas": int(resultados.get("paginas", 0) or 0),
        "toner_porcentagem": toner_perc,
        "cilindro_porcentagem": cilindro_perc,
        "toner_ciano": toner_ciano,
        "toner_magenta": toner_magenta,
        "toner_amarelo": toner_amarelo,
        "contato": resultados.get("contato") or None,
        "local": resultados.get("local") or None,
        "mac_address": mac_address or None,
        "erros_hardware": erros_hardware,
        "visor_mensagem": visor_alerta,
        "visor_texto_bruto": visor_bruto.strip() if visor_bruto else None,
        "hr_status": resultados.get("hr_status"),
    }

    return dados_formatados


# ==================================================================
# CONSULTA EM LOTE (PARALELA) DE VÁRIAS IMPRESSORAS
# ==================================================================

async def consultar_impressoras_async(lista_ips, community="public"):
    """
    Consulta impressoras em paralelo controlado (máximo 4 simultâneas)
    para evitar MemoryError e exaustão de descritores no PySNMP.
    Retorna um dicionário {ip: dados_formatados}.
    """
    semaforo = asyncio.Semaphore(4)

    async def _consultar_com_limite(ip):
        async with semaforo:
            return await consultar_impressora_async(ip, community)

    tarefas = [
        _consultar_com_limite(ip)
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


if __name__ == "__main__":
    import sys
    ip_teste = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    resultado = consultar_impressora(ip_teste)
    print(resultado)