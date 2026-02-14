# Fluxo de Integração ATM - Guia de Uso

## 📋 Descrição

Este fluxo detecta automaticamente máquinas ATM (clusters começando com TRNP) durante o processo de **Restart Completo** (Opção 4) e oferece uma mensagem padrão para integração.

## 🔍 Como Funciona

### 1. Detecção Automática
- O sistema verifica se a máquina pertence a um cluster ATM que começa com `TRNP`
- Exemplo: `TRNPATM01` será detectado como máquina ATM

### 2. Fluxo do Restart Completo (Opção 4)

```
Menu Principal
    ↓
Opção 4 - Restart Completo
    ↓
Digite o nome da máquina (ex: TRNPATM01)
    ↓
Sistema faz restart da máquina
    ↓
SE máquina for ATM + cluster TRNP:
    ↓
Pergunta: "Deseja copiar a mensagem padrão para integração?"
    ↓
    [SIM] → Exibe mensagem padrão + copia para clipboard
    [NÃO] → Continua sem mensagem
```

### 3. Mensagem Padrão ATM

A mensagem exibida será:

```
*ATM* - Terminal de Auto Atendimento

*Incidente*: Rejeições para as transações da utilização da ATM

*Hora Inicio*: 10h12

*Impacto*: Instabilidade para as transações da ATM

*Causa*: Intermitência nos servidores que atendem a ATM.

*Acionados*: Área de Operações de TI

*Obs*: Executada ações de 1º nível para regularização

*Regularizado*: 10h29
```

## ⚙️ Instalação (Opcional)

Para ativar a cópia automática para clipboard, instale o `pyperclip`:

```bash
pip install pyperclip
```

Se não instalar, você poderá copiar manualmente a mensagem que será exibida no terminal.

## 📝 Personalização

Para alterar a mensagem padrão, edite o arquivo `atm_mensagens.py`:

- Função: `obter_mensagem_atm_padrao()`

Para adicionar outros tipos de máquinas/clusters, edite:

- Função: `eh_maquina_atm(cluster_name)`

## 🧪 Testando

1. Execute o programa principal
2. Escolha a opção **4 - Restart completo**
3. Digite o nome de uma máquina ATM (ex: `TRNPATM01`)
4. O sistema detectará automaticamente e oferecerá a mensagem

## 📂 Arquivos Relacionados

- `atm_mensagens.py` - Módulo de gerenciamento de mensagens ATM
- `backend.py` - Sistema principal com integração do fluxo ATM
- `Pesquisar_Cluster/Pesquisar.py` - Consulta cluster da máquina
