@echo off
pushd "D:\Develop\AI 应用开发\AI应用开发项目\AwardIE-AgentFlow"
if not exist logs mkdir logs
"D:\venvs\awardie\Scripts\python.exe" "D:\Develop\AI 应用开发\AI应用开发项目\AwardIE-AgentFlow\scripts\backup.py" >> "D:\Develop\AI 应用开发\AI应用开发项目\AwardIE-AgentFlow\logs\backup_task.log" 2>&1
popd
