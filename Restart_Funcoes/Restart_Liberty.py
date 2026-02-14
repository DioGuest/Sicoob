import requests
import time
import logging
import os

# Ensure the log directory exists
if not os.path.exists('log'):
    os.makedirs('log')

# Logger configuration
logging.basicConfig(
    filename='log/restart_liberty.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M',
    encoding='utf-8'
)

def restart_liberty(Modo, valor_cluster, valor_codigo, Login, Senha, ACAO='RESTART'):
    """
    Executa o restart do Liberty utilizando a função genérica de trigger do Jenkins.
    """
    # Caminho completo e correto para o job do Liberty
    job_path = 'view/OperacoesTI/job/Restart/job/Liberty/job/Restart-Liberty'
    
    parameters = {
        'ACAO': ACAO,
        'MODO': Modo,
        'NOMECLUSTER': valor_cluster,
        'AMBIENTE': 'PRODUCAO',
        'SELECIONADOS': valor_codigo
    }
    
    logging.info(f"Chamando trigger_jenkins_job para Liberty com os parâmetros: {parameters}")
    
    return trigger_jenkins_job(job_path, parameters, Login, Senha)

def get_job_url(queue_url: str, login: str, senha: str) -> str:
    """Obtém a URL do job a partir da URL da fila"""
    try:
        response = requests.get(
            queue_url + 'api/json',
            auth=(login, senha),
            verify=False
        )
        if response.status_code == 200:
            data = response.json()
            if 'executable' in data and 'url' in data['executable']:
                return data['executable']['url']
    except:
        pass
    return None

def check_job_status(job_url, login, senha):
    """Verifica o status atual do job"""
    try:
        response = requests.get(job_url + 'api/json', auth=(login, senha), verify=False)
        if response.status_code == 200:
            job_info = response.json()
            status = {
                "status": "RUNNING" if job_info.get('building', True) else job_info.get('result', 'UNKNOWN'),
                "building": job_info.get('building', True),
                "description": job_info.get('description', ''),
                "url": job_url
            }
            return status
    except Exception as e:
        return {
            "status": "ERROR",
            "building": False,
            "description": str(e),
            "url": job_url
        }

def trigger_jenkins_job(job_path: str, parameters: dict, login: str, senha: str):
    """
    Função genérica para iniciar um job no Jenkins a partir do seu caminho completo.
    job_path: O caminho completo do job após a URL base. Ex: 'job/Restart/job/Websphere/...'
    """
    base_url = 'https://deploy.sicoob.com.br'
    # Constrói a URL final corretamente, sem adicionar prefixos fixos
    job_url = f'{base_url}/{job_path}/buildWithParameters'
    crumb_issuer_url = f'{base_url}/crumbIssuer/api/json'

    try:
        # 1. Obter o Crumb de segurança do Jenkins
        crumb_response = requests.get(crumb_issuer_url, auth=(login, senha), verify=False, timeout=10)
        crumb_data = {}
        if crumb_response.status_code == 200:
            crumb_data = crumb_response.json()
        else:
            logging.warning("Não foi possível obter o crumb do Jenkins. Tentando prosseguir sem ele.")

        headers = {}
        if 'crumbRequestField' in crumb_data and 'crumb' in crumb_data:
            headers[crumb_data['crumbRequestField']] = crumb_data['crumb']

        # Log para depuração final
        logging.info(f"Disparando Job. URL: {job_url}, Parâmetros: {parameters}")

        # 2. Iniciar o Job
        response = requests.post(
            job_url,
            params=parameters,
            auth=(login, senha),
            headers=headers,
            verify=False,
            timeout=15
        )

        if response.status_code == 201:
            queue_url = response.headers.get('Location')
            if not queue_url:
                return {"status": "ERROR", "message": "Jenkins não retornou a URL da fila."}

            # Tenta obter a URL do job executável
            max_attempts = 15
            for _ in range(max_attempts):
                job_url_executable = get_job_url(queue_url, login, senha)
                if job_url_executable:
                    return {
                        "status": "STARTED",
                        "message": f"Job '{job_path}' iniciado.",
                        "job_url": job_url_executable
                    }
                time.sleep(2)
            
            return {"status": "ERROR", "message": "Timeout: Não foi possível obter a URL do job a partir da fila."}
        else:
            return {"status": "ERROR", "message": f"Falha ao iniciar job: {response.status_code} - {response.text}"}
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de requisição ao contatar o Jenkins: {e}")
        return {"status": "ERROR", "message": f"Erro de comunicação com o Jenkins: {str(e)}"}
    except Exception as e:
        logging.error(f"Erro inesperado ao acionar job do Jenkins: {e}")
        return {"status": "ERROR", "message": f"Erro inesperado: {str(e)}"}

