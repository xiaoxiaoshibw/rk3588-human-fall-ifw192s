@echo off
REM HR-06 PC 环境预热 — human_pcl conda 环境一键装
REM 可重复跑：幂等。已存在环境就升级到指定包，新建就装到 C:\Users\30680\miniconda3\envs\human_pcl\
setlocal

set CONDA=C:\Users\30680\miniconda3\Scripts\conda.exe
set ENV_NAME=human_pcl

if not exist %CONDA% (
    echo [ERROR] miniconda 未装，期望路径: %CONDA%
    exit /b 1
)

echo [INFO] 使用 conda: %CONDA%

REM 看环境存不存在
%CONDA% env list | findstr /C:"%ENV_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] 环境 %ENV_NAME% 已存在 — 检查核心包
) else (
    echo [INFO] 新建环境 %ENV_NAME% ^(python=3.9 来自 conda-forge^)
    %CONDA% create -y -n %ENV_NAME% -c conda-forge python=3.9 || (
        echo [ERROR] conda create 失败
        exit /b 2
    )
)

echo [INFO] 装 python-pcl + 顺带 numpy ^(conda-forge^)
%CONDA% install -y -n %ENV_NAME% -c conda-forge python-pcl numpy || (
    echo [ERROR] conda install 失败
    exit /b 3
)

echo [INFO] 环境列表
%CONDA% env list

echo.
echo [OK] %ENV_NAME% 就绪
echo 激活: "%CONDA% activate %ENV_NAME%"
echo 或直跑 python: C:\Users\30680\miniconda3\envs\%ENV_NAME%\python.exe
exit /b 0
