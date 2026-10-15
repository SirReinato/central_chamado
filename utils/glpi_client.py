"""
Cliente HTTP para API REST v2.3 do GLPI com OAuth2
Projetado sob a Politica de Carga Zero:
1. Reutiliza o access_token JWT durante sua validade (1h), evitando requisicoes repetidas de autenticacao.
2. Utiliza exclusivamente o metodo HTTP GET para leitura de dados.
3. Timeouts estritos para nao prender recursos.
4. Circuit Breaker / Backoff para suspender execucoes caso o servidor sinalize instabilidade.
"""
import os
import time
import logging
import requests
import urllib3

# Suprime avisos de certificado SSL interno se necessario
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('glpi_client')


class GlpiClient:
    def __init__(self):
        self.api_url = os.environ.get('GLPI_API_URL', 'https://helpdesk.brasfort.com.br/api.php').rstrip('/')
        self.client_id = os.environ.get('GLPI_CLIENT_ID', '').strip()
        self.client_secret = os.environ.get('GLPI_CLIENT_SECRET', '').strip()
        self.username = os.environ.get('GLPI_USERNAME', '').strip()
        self.password = os.environ.get('GLPI_PASSWORD', '').strip()
        
        self.timeout = int(os.environ.get('GLPI_REQUEST_TIMEOUT', 15))
        self.batch_size = int(os.environ.get('GLPI_BATCH_SIZE', 15))
        self.filter_request_type_id = os.environ.get('GLPI_FILTER_REQUEST_TYPE_ID', '1')
        self.filter_category_id = os.environ.get('GLPI_FILTER_CATEGORY_ID', '').strip()

        # Cache de token OAuth2 em memoria
        self._access_token = None
        self._token_expires_at = 0

    def _obter_token(self) -> str:
        """
        Obtem ou renova o token JWT OAuth2 apenas quando expirado.
        Evita chamadas redundantes de autenticacao no GLPI.
        """
        agora = time.time()
        # Se ja temos um token valido com margem de 60 segundos, reutiliza
        if self._access_token and agora < (self._token_expires_at - 60):
            return self._access_token

        token_url = f"{self.api_url}/token"
        payload = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password,
            'scope': 'api'
        }

        try:
            logger.info("Solicitando novo token de acesso OAuth2 ao GLPI...")
            response = requests.post(
                token_url,
                data=payload,
                verify=False,
                timeout=self.timeout
            )

            if response.status_code == 200:
                dados = response.json()
                self._access_token = dados.get('access_token')
                expires_in = int(dados.get('expires_in', 3600))
                self._token_expires_at = agora + expires_in
                logger.info(f"Token OAuth2 obtido com sucesso! Validade: {expires_in}s.")
                return self._access_token
            else:
                logger.error(f"Falha na autenticacao OAuth2: HTTP {response.status_code} - {response.text}")
                raise ConnectionError(f"Erro ao autenticar no GLPI: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de comunicacao ao solicitar token: {e}")
            raise

    def buscar_tickets(self, ultimo_glpi_id: int = None, limite: int = None) -> list:
        """
        Busca os tickets mais recentes no GLPI via GET /Assistance/Ticket.
        Aplica filtro de lote (range) e ordenacao para minimizar a carga.
        """
        token = self._obter_token()
        limite_busca = limite or self.batch_size
        
        endpoint = f"{self.api_url}/v2.3/Assistance/Ticket"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        # Busca com ordenacao decrescente por ID e limite estrito
        params = {
            'sort': 'id',
            'order': 'DESC',
            'range': f"0-{limite_busca - 1}"
        }

        try:
            logger.info(f"Consultando lote de ate {limite_busca} tickets no GLPI...")
            res = requests.get(
                endpoint,
                headers=headers,
                params=params,
                verify=False,
                timeout=self.timeout
            )

            if res.status_code == 200:
                tickets = res.json()
                if not isinstance(tickets, list):
                    tickets = [tickets]

                logger.info(f"Retornados {len(tickets)} tickets brutos do GLPI.")
                
                # Se houver um ultimo_glpi_id registrado, filtra apenas os maiores que ele
                if ultimo_glpi_id:
                    tickets = [t for t in tickets if t.get('id', 0) > ultimo_glpi_id]
                    logger.info(f"Tickets novos apos ID #{ultimo_glpi_id}: {len(tickets)}.")

                return tickets

            elif res.status_code == 401:
                # Token possivelmente invalidado: forca renovacao no proximo ciclo
                self._access_token = None
                logger.warning("Token expirado ou invalido (401). Resetando cache de token.")
                return []

            elif res.status_code in (429, 500, 502, 503):
                logger.warning(f"GLPI retornou status de sobrecarga/instabilidade HTTP {res.status_code}. Abortando ciclo.")
                return []

            else:
                logger.error(f"Resposta inesperada do GLPI: HTTP {res.status_code} - {res.text[:200]}")
                return []

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout de {self.timeout}s atingido ao consultar GLPI. Ciclo finalizado com seguranca.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar tickets: {e}")
            return []

    def buscar_detalhe_ticket(self, ticket_id: int) -> dict:
        """
        Recupera os detalhes completos de um ticket especifico (apenas GET).
        """
        token = self._obter_token()
        endpoint = f"{self.api_url}/v2.3/Assistance/Ticket/{ticket_id}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        try:
            res = requests.get(
                endpoint,
                headers=headers,
                verify=False,
                timeout=self.timeout
            )
            if res.status_code == 200:
                return res.json()
            return {}
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes do ticket #{ticket_id}: {e}")
            return {}
