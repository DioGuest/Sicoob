"""
Módulo para gerenciar mensagens padrão de integração para máquinas ATM
"""
import os
import tempfile
import subprocess

def obter_mensagem_atm_padrao():
    """
    Retorna a mensagem padrão para máquinas ATM
    """
    return """*ATM* - Terminal de Auto Atendimento

*Incidente*: Rejeições para as transações da utilização da ATM

*Hora Inicio*: 10h12

*Impacto*: Instabilidade para as transações da ATM

*Causa*: Intermitência nos servidores que atendem a ATM.

*Acionados*: Área de Operações de TI

*Obs*: Executada ações de 1º nível para regularização

*Regularizado*: 10h29"""

def eh_maquina_atm(cluster_name):
    """
    Verifica se a máquina pertence a um cluster ATM que começa com TRNP
    
    Args:
        cluster_name: Nome do cluster da máquina
        
    Returns:
        bool: True se é uma máquina ATM com cluster começando com TRNP
    """
    if not cluster_name:
        return False
    
    cluster_upper = cluster_name.upper()
    # Verifica se contém 'ATM' e começa com 'TRNP'
    return 'ATM' in cluster_upper and cluster_upper.startswith('TRNP')

def exibir_mensagem_em_arquivo(mensagem, titulo="MENSAGEM ATM"):
    """
    Exibe a mensagem em um arquivo de texto temporário mantendo formatação
    
    Args:
        mensagem: Conteúdo da mensagem
        titulo: Título do arquivo
        
    Returns:
        bool: True se conseguiu exibir
    """
    try:
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(f"{titulo}\n")
            tmp_file.write("="*80 + "\n\n")
            tmp_file.write(mensagem)
            tmp_path = tmp_file.name
        
        # Abrir com Notepad (Windows)
        subprocess.Popen(['notepad.exe', tmp_path])
        return True
    except Exception as e:
        print(f"Erro ao exibir arquivo: {e}")
        return False

def exibir_mensagem_gui(mensagem, titulo="MENSAGEM ATM - ATM"):
    """
    Exibe a mensagem em uma janela GUI (tkinter) mantendo formatação
    
    Args:
        mensagem: Conteúdo da mensagem
        titulo: Título da janela
        
    Returns:
        bool: True se conseguiu exibir
    """
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        
        janela = tk.Tk()
        janela.title(titulo)
        janela.geometry("900x600")
        
        # Frame para botões
        frame_botoes = tk.Frame(janela, bg="#f0f0f0")
        frame_botoes.pack(fill=tk.X, padx=10, pady=10)
        
        # Botão copiar
        def copiar_mensagem():
            janela.clipboard_clear()
            # Copia exatamente como está (sem alterar)
            janela.clipboard_append(mensagem.strip())
            label_status.config(text="✓ Mensagem copiada para o clipboard com formatação preservada!", fg="green")
            janela.after(4000, lambda: label_status.config(text=""))
        
        btn_copiar = tk.Button(
            frame_botoes,
            text="📋 Copiar para Clipboard",
            command=copiar_mensagem,
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=8,
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            cursor="hand2"
        )
        btn_copiar.pack(side=tk.LEFT, padx=5)
        
        btn_fechar = tk.Button(
            frame_botoes,
            text="✕ Fechar",
            command=janela.quit,
            bg="#f44336",
            fg="white",
            padx=20,
            pady=8,
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            cursor="hand2"
        )
        btn_fechar.pack(side=tk.LEFT, padx=5)
        
        label_status = tk.Label(
            frame_botoes, 
            text="Clique em 'Copiar para Clipboard' para copiar a mensagem", 
            fg="#666666",
            font=("Arial", 9)
        )
        label_status.pack(side=tk.LEFT, padx=20)
        
        # Caixa de texto com scroll - MONOESPACIAL para preservar formatação
        text_widget = scrolledtext.ScrolledText(
            janela,
            wrap=tk.WORD,
            font=("Courier New", 11),
            padx=20,
            pady=20,
            bg="#ffffff",
            fg="#000000",
            relief=tk.FLAT,
            insertwidth=2
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Inserir mensagem - exatamente como está
        text_widget.insert("1.0", mensagem.strip())
        text_widget.config(state=tk.DISABLED)  # Somente leitura
        
        # Centralizar janela na tela
        janela.update_idletasks()
        largura = janela.winfo_width()
        altura = janela.winfo_height()
        x = (janela.winfo_screenwidth() // 2) - (largura // 2)
        y = (janela.winfo_screenheight() // 2) - (altura // 2)
        janela.geometry(f'{largura}x{altura}+{x}+{y}')
        
        janela.mainloop()
        return True
    except ImportError:
        return False

def sugerir_mensagem_atm(cluster_name):
    """
    Sugere ao usuário se deseja usar a mensagem padrão ATM
    
    Args:
        cluster_name: Nome do cluster da máquina
        
    Returns:
        bool: True se o usuário quer usar a mensagem
    """
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.panel import Panel
    
    console = Console()
    
    if eh_maquina_atm(cluster_name) or (cluster_name and cluster_name.upper().startswith("TRNP")):
        console.print(Panel(
            f"[bold blue]Máquina ATM detectada![/bold blue]\n"
            f"[cyan]Cluster: {cluster_name}[/cyan]",
            style="blue"
        ))
        
        resposta = Prompt.ask(
            "[bold cyan]Usar mensagem padrão para integração?[/bold cyan]",
            choices=["s", "n"],
            default="s"
        )
        
        if resposta.lower() == "s":
            mensagem = obter_mensagem_atm_padrao()
            
            # Tentar exibir em GUI primeiro
            console.print(Panel(
                "[bold green]Abrindo mensagem em janela...[/bold green]",
                style="green"
            ))
            
            if exibir_mensagem_gui(mensagem):
                # GUI funcionou
                return True
            else:
                # GUI falhou, tenta arquivo
                console.print(Panel(
                    "[bold yellow]Abrindo mensagem em arquivo de texto...[/bold yellow]",
                    style="yellow"
                ))
                if exibir_mensagem_em_arquivo(mensagem):
                    return True
                else:
                    # Última opção: exibir no terminal
                    console.print(Panel(
                        "[bold green]MENSAGEM PADRÃO ATM:[/bold green]\n" + mensagem,
                        style="green"
                    ))
                    
                    # Tentar copiar para clipboard
                    try:
                        import pyperclip
                        pyperclip.copy(mensagem.strip())
                        console.print("[bold green]✓ Mensagem copiada para o clipboard![/bold green]")
                    except ImportError:
                        console.print("[yellow]Nota: Para copiar automaticamente, instale: pip install pyperclip[/yellow]")
                    return True
        
        return False
    
    return False
