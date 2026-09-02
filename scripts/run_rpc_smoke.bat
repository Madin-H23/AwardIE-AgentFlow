@echo off
REM G6 真实 gRPC 冒烟一键脚本:前置=ai_worker 在线(50060)
REM 用法:scripts\run_rpc_smoke.bat

netstat -ano | findstr ":50060" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [!] ai_worker 未在线(50060)——请先启动 ai_worker 后重试
    exit /b 1
)

echo [1/3] 重启 Java(gRPC 模式)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
cd /d "%~dp0..\awardie-backend"
start /b "" "C:\Program Files\Java\jdk-21\bin\java.exe" -jar target\awardie-backend-0.1.0-SNAPSHOT.jar --ai.worker.mode=gRPC > %TEMP%\v2_java_rpc.log 2>&1
timeout /t 25 /nobreak >nul

echo [2/3] 运行 gRPC 冒烟测试...
call mvn test -Dtest=TaggedPerfSmokeIT
set RC=%ERRORLEVEL%

echo [3/3] 恢复 Java(fake 模式)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
start /b "" "C:\Program Files\Java\jdk-21\bin\java.exe" -jar target\awardie-backend-0.1.0-SNAPSHOT.jar > %TEMP%\v2_java.log 2>&1
timeout /t 20 /nobreak >nul

if %RC%==0 (echo [OK] gRPC 冒烟通过) else (echo [FAIL] 冒烟失败,详见上方输出)
exit /b %RC%
