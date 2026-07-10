#!/bin/bash

# 1. 进入项目目录
cd /home/ubuntu/csddata

# 2. 拉取最新代码（如果用 Git）
git pull

# 3. 如有依赖变更
source venv/bin/activate
pip install -r requirements.txt

# 4. 重启服务
sudo systemctl restart info-management

# 5. 确认运行正常
sudo systemctl status info-management
tail -f logs/app.log