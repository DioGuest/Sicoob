#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste do módulo de mensagens ATM
Este script demonstra o funcionamento do fluxo de detecção e sugestão de mensagens ATM
"""

from atm_mensagens import (
    eh_maquina_atm, 
    obter_mensagem_atm_padrao, 
    sugerir_mensagem_atm
)

def teste_deteccao():
    """Testa a detecção de máquinas ATM"""
    print("\n" + "="*60)
    print("TESTE 1: Detecção de Máquinas ATM")
    print("="*60)
    
    casos_teste = [
        ("TRNPATM01", True, "Cluster ATM começando com TRNP"),
        ("TRNPATM-CORE", True, "Cluster ATM com hífen"),
        ("TRNPAGILE", True, "Cluster TRNP com ATM no nome"),
        ("WASPCORE", False, "Cluster WASP (não ATM)"),
        ("CTSPCORE", False, "Cluster sem ATM"),
        ("TRNPWEB", False, "Cluster TRNP sem ATM"),
        ("ATM-PRODUCAO", False, "Tem ATM mas não começa com TRNP"),
    ]
    
    for cluster, esperado, descricao in casos_teste:
        resultado = eh_maquina_atm(cluster)
        status = "✓" if resultado == esperado else "✗"
        print(f"{status} {cluster:20} -> {resultado:5} ({descricao})")

def teste_mensagem():
    """Testa a mensagem padrão"""
    print("\n" + "="*60)
    print("TESTE 2: Mensagem Padrão ATM")
    print("="*60)
    
    mensagem = obter_mensagem_atm_padrao()
    print("\nMensagem padrão:")
    print("-" * 60)
    print(mensagem)
    print("-" * 60)

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "TESTE DO MÓDULO ATM_MENSAGENS".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    teste_deteccao()
    teste_mensagem()
    
    print("\n" + "="*60)
    print("TESTE 3: Demonstração Interativa")
    print("="*60)
    print("\nPara testar a sugestão interativa, execute:")
    print("  >>> from atm_mensagens import sugerir_mensagem_atm")
    print("  >>> sugerir_mensagem_atm('TRNPATM01')")
    print("\nNote: A função interativa só funciona quando executada")
    print("      dentro do programa principal ou em ambiente interativo.")
    
    print("\n✓ Testes completados!")
