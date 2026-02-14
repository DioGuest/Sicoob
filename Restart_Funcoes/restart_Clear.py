import requests
import time
from requests.auth import HTTPBasicAuth

def get_job_url(queue_url, login, senha):
    """
    Obtém a URL do build a partir da URL da fila.
    """
    try:
        response = requests.get(queue_url + 'api/json', auth=HTTPBasicAuth(login, senha), timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'executable' in data:
                return data['executable']['url']
        return None
    except Exception as e:
        return None

def restart_CleanDisk(cluster_name, node, login, senha):
    """
    Inicia o job de limpeza de disco no Jenkins para o node especificado.
    """
    try:
        url = "https://deploy.sicoob.com.br/job/Restart/job/Websphere/job/WAS-Restart-CleanDisk/buildWithParameters"
        params = {
            "ACAO": "RESTART",
            "MODO": "SEQUENCIAL",
            "NOMECLUSTER": cluster_name,
            "AMBIENTE": "PRODUCAO",
            "SELECIONADOS": node
        }
        response = requests.post(
            url,
            auth=HTTPBasicAuth(login, senha),
            data=params,
            timeout=30
        )
        if response.status_code in [200, 201]:
            queue_url = response.headers.get('Location')
            if queue_url:
                # Aguardar e obter a build URL
                build_url = None
                max_attempts = 15
                for attempt in range(max_attempts):
                    build_url = get_job_url(queue_url, login, senha)
                    if build_url:
                        break
                    time.sleep(1)
                if build_url:
                    return {"status": "STARTED", "job_url": build_url}
                else:
                    return {"status": "ERROR", "message": "Não foi possível obter a URL do build após múltiplas tentativas"}
            else:
                return {"status": "ERROR", "message": "Job iniciado mas URL da fila não retornada"}
        else:
            return {"status": "ERROR", "message": f"Status code: {response.status_code}, Response: {response.text}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

def check_job_status(job_url, login, senha):
    """
    Verifica o status de um job do Jenkins.
    """
    try:
        response = requests.get(job_url + "/api/json", auth=HTTPBasicAuth(login, senha), timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("building"):
                return {"status": "RUNNING"}
            elif data.get("result") == "SUCCESS":
                return {"status": "SUCCESS"}
            elif data.get("result") in ["FAILURE", "ABORTED"]:
                return {"status": "FAILURE", "message": data.get("result")}
            else:
                return {"status": "UNKNOWN"}
        else:
            return {"status": "ERROR", "message": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}