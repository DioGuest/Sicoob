import requests
import time
import logging
import os

# Garante que o diretório de log exista
log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configuração do Logger
logging.basicConfig(
    filename=os.path.join(log_dir, 'restart_sws.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M',
    encoding='utf-8'
)

def get_job_url(queue_url: str, login: str, senha: str) -> str:
    """Obtém a URL do job a partir da URL da fila."""
    try:
        response = requests.get(queue_url + 'api/json', auth=(login, senha), verify=False)
        if response.status_code == 200:
            data = response.json()
            if 'executable' in data and 'url' in data['executable']:
                return data['executable']['url']
    except Exception as e:
        logging.error(f"Erro ao obter URL do job da fila {queue_url}: {e}")
    return None

def check_job_status(job_url, login, senha):
    """Verifica o status atual do job."""
    try:
        response = requests.get(job_url + 'api/json', auth=(login, senha), verify=False)
        if response.status_code == 200:
            job_info = response.json()
            return {
                "status": "RUNNING" if job_info.get('building', True) else job_info.get('result', 'UNKNOWN'),
                "building": job_info.get('building', True)
            }
    except Exception as e:
        logging.error(f"Erro ao verificar status do job {job_url}: {e}")
        return {"status": "ERROR", "building": False, "message": str(e)}

def restart_SWS(Modo, valor_cluster, valor_codigo, Login, Senha):
    """
    Inicia o job de restart para o SWS (Serviço WebSphere).
    """
    jenkins_url = 'https://deploy.sicoob.com.br/view/OperacoesTI/job/Restart/job/SWS/job/restart-sws-srv-websphere/buildWithParameters'
    
    params = {
        'ACAO': 'RESTART',
        'MODO': Modo,
        'NOMECLUSTER': valor_cluster,
        'AMBIENTE': 'PRODUCAO',
        'SELECIONADOS': valor_codigo
    }

    try:
        logging.info(f"Disparando job do SWS com parâmetros: {params}")
        response = requests.post(jenkins_url, params=params, auth=(Login, Senha), verify=False)

        if response.status_code == 201:
            queue_url = response.headers.get('Location')
            logging.info(f"Build do SWS iniciado para: {valor_codigo or valor_cluster}")
            
            max_attempts = 15
            for _ in range(max_attempts):
                job_url = get_job_url(queue_url, Login, Senha)
                if job_url:
                    return {"status": "STARTED", "message": "Build iniciado", "job_url": job_url}
                time.sleep(2)
            return {"status": "ERROR", "message": "Timeout aguardando URL do job"}
        else:
            logging.error(f"Falha ao iniciar build do SWS: {response.status_code} - {response.text}")
            return {"status": "ERROR", "message": f"Falha ao iniciar build: {response.status_code}"}
            
    except Exception as e:
        logging.error(f"Erro no restart do SWS: {e}")
        return {"status": "ERROR", "message": f"Erro no restart do SWS: {str(e)}"}
