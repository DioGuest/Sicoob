@echo off
REM Script para instalar dependências opcionais do projeto AUTOMACAO F5

echo.
echo ========================================
echo Instalando dependencias opcionais...
echo ========================================
echo.

REM Instala pyperclip para copia automatica para clipboard
echo Instalando pyperclip (para copia automatica para clipboard)...
pip install pyperclip

echo.
echo ========================================
echo Instalacao concluida!
echo ========================================
echo.
echo Agora voce pode usar a copia automatica para clipboard.
echo.
pause
