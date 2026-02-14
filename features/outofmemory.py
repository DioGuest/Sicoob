import paramiko
import time

def move_files_ssh(host, username, password):
    """Executa a movimentação de arquivos OutOfMemory via SSH"""
    port = 22
    sudo_password = password
    result_message = "OutOfMemory - Movendo arquivos<br>"
    
    print(f"\n[DEBUG] Tentando conectar ao host: {host}")
    print(f"[DEBUG] Usando usuário: {username}")

    # Cria uma sessão SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"[DEBUG] Iniciando conexão SSH com {host}")
        ssh.connect(host, port, username, password)
        print(f"[SUCCESS] Conectado ao servidor {host}")
        result_message += f"[bold green]Conectado ao servidor {host}[/bold green]<br>"

        # Lista arquivos antes da movimentação
        list_command = 'ls -lh /opt/IBM/WAS/WebSphere/AppServer/profiles/sicoob/'
        stdin, stdout, stderr = ssh.exec_command(list_command)
        files_before = stdout.read().decode()
        result_message += f"[yellow]Arquivos antes da movimentação:[/yellow]<br>{files_before}<br>"

        # Move os arquivos
        move_command = 'cd /opt/IBM/WAS/WebSphere/AppServer/profiles/sicoob/ && sudo mv *.dmp *.txt *.phd *.trc /media/dump/'
        stdin, stdout, stderr = ssh.exec_command(move_command)
        stdin.write(sudo_password + '\n')
        stdin.flush()
        
        error = stderr.read().decode()
        if error:
            result_message += f"[red]Aviso durante a movimentação: {error}[/red]<br>"

        # Lista arquivos após a movimentação
        stdin, stdout, stderr = ssh.exec_command(list_command)
        files_after = stdout.read().decode()
        result_message += f"[yellow]Arquivos após a movimentação:[/yellow]<br>{files_after}<br>"

    except Exception as e:
        error_msg = f"Erro ao conectar ou executar comando no servidor {host}: {str(e)}"
        print(f"[ERROR] {error_msg}")
        result_message += f"[red]Erro: {error_msg}[/red]<br>"

    finally:
        ssh.close()

    return {
        "status": "success",
        "message": result_message
    }
