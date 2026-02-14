import paramiko
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def execute_ssh_commands(host, username, password):
    port = 22  # Definido como 22 para SSH
    sudo_password = password  # Reutiliza a senha para comandos sudo
    result_message = "Limpeza Disco-Opt - Na pasta Temp<br>"

    # Cria uma sessão SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Conecta ao servidor
        ssh.connect(host, port, username, password)
        result_message += f"[bold green]Conectado ao servidor {host}[/bold green]<br>"

        # Executa o comando para verificar o tamanho da pasta temp ANTES da exclusão
        size_command_before = 'du -sh /opt/IBM/WAS/WebSphere/AppServer/temp'
        stdin, stdout, stderr = ssh.exec_command(size_command_before)
        size_before = stdout.read().decode().strip()
        result_message += f"[yellow]Tamanho da pasta temp ANTES da exclusão: {size_before}[/yellow]<br>"

        # Atualiza o comando para deletar arquivos temporários, arquivos que começam com "C", arquivos .ttf e arquivos .pdf
        delete_command = 'sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.tmp" -delete; sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "C*" -delete; sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.ttf" -delete; sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.pdf" -delete'
        stdin, stdout, stderr = ssh.exec_command(delete_command)
        stdin.write(sudo_password + '\n')
        stdin.flush()
        time.sleep(2)  # Aguardando o comando ser executado

        # Executa o comando para verificar o tamanho da pasta temp DEPOIS da exclusão
        size_command_after = 'du -sh /opt/IBM/WAS/WebSphere/AppServer/temp'
        stdin, stdout, stderr = ssh.exec_command(size_command_after)
        size_after = stdout.read().decode().strip()
        result_message += f"[yellow]Tamanho da pasta temp DEPOIS da exclusão: {size_after}[/yellow]<br>"

    except Exception as e:
        result_message += f"[red]Erro ao conectar ou executar o comando no servidor {host}: {str(e)}[/red]<br>"

    finally:
        ssh.close()

    return result_message

def clean_opt_disk(nodes, username, password):
    """Função principal para limpar disco opt em múltiplos nodes"""
    hosts = [node.strip() for node in nodes.split(',')] if isinstance(nodes, str) else [nodes]
    
    if not hosts or not username or not password:
        return {"status": "error", "message": "Parâmetros inválidos!"}

    with ThreadPoolExecutor() as executor:
        future_to_host = {
            executor.submit(execute_ssh_commands, host, username, password): host 
            for host in hosts
        }
        
        results = []
        for future in as_completed(future_to_host):
            host = future_to_host[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(f"Erro ao processar o servidor {host}: {str(e)}")

    return {
        "status": "success",
        "message": "<br>".join(results)
    }