# OCR / 智谱 API 密钥「未配置」排查指南

当管理端「系统设置」页面显示 **「创建 Provider 'zhipu' 失败: Zhipu API key 未配置」** 时，说明运行环境中未读到智谱 API 密钥。按下面步骤排查。

## 1. 环境变量名必须一致

代码中使用的环境变量名是 **`ZHIPUAI_API_KEY`**（中间是 **AI**，不是 `ZHIPU_API_KEY`）。

- 在 `.env` 中应写：`ZHIPUAI_API_KEY=你的密钥`
- 若写成 `ZHIPU_API_KEY=...` 将不会被识别。

## 2. .env 文件位置

`.env` 必须放在 **项目根目录**（与 `run.py`、`config` 文件夹同级）。

- 正确示例：`/path/to/项目根/.env`
- 若放在用户目录（如 `~/.env`）或其它目录，应用不会自动加载。

## 3. 确保 .env 会被加载

应用在以下时机加载 `.env`：

- **`run.py` 启动**：执行 `python run.py` 时，会在项目根目录加载 `.env`。
- **通过 `config.flask`**：创建 Flask 应用时会 `import config.flask`，该模块会执行 `load_dotenv(BASE_DIR / ".env")`，同样要求项目根目录下有 `.env`。
- **通过 `ConfigLoader`**：首次调用 `get_config().load_config()` 时，若存在 `config/loader.py` 里配置的 `.env` 路径，也会加载。

若使用 **gunicorn / uwsgi** 等，且入口是 `app:app` 而不是 `run:app`，仍会通过 `config.flask` 加载 `.env`，只要 `.env` 在项目根目录即可。若部署时「当前工作目录」不是项目根，只要代码中的 `Path(__file__).parent.parent` 指向项目根，`.env` 路径仍然正确。

## 4. 安装 python-dotenv

加载 `.env` 依赖 `python-dotenv`。未安装时，不会报错，但 `.env` 不会生效。

在服务器上执行：

```bash
pip show python-dotenv
# 若未安装：
pip install python-dotenv
```

安装后重启应用。

## 5. 可选：使用 apikey.json

除 `.env` 外，可通过 `apikey/apikey.json` 注入密钥。在 `load_config()` 时会调用 `load_api_keys_into_env()`，将其中配置写入环境变量。

结构示例：

```json
{
  "ocr": {
    "zhipu": "你的智谱API密钥",
    "baidu": "百度API Key",
    "baidu_secret": "百度 Secret Key"
  },
  "llm": {
    "zhipu": "你的智谱API密钥"
  }
}
```

注意：`apikey.json` 通常不应提交到版本库，需在服务器上单独配置并保证路径正确（项目根下的 `apikey/apikey.json`）。

## 6. 在服务器上快速自检

在 **项目根目录** 下执行：

```bash
# 检查环境变量名与是否已加载（先加载 .env 再查看）
python -c "
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
import os
key = os.getenv('ZHIPUAI_API_KEY', '')
print('ZHIPUAI_API_KEY 已配置:', bool(key))
if key:
    print('前几位:', key[:8] + '...')
"
```

若输出 `ZHIPUAI_API_KEY 已配置: False`，说明当前目录下的 `.env` 中未正确设置 `ZHIPUAI_API_KEY`，或 `.env` 不在当前目录、或变量名拼写错误。

## 7. 百度 OCR「未配置」同理

百度 OCR 需要两个环境变量：

- `BAIDU_API_KEY`
- `BAIDU_SECRET_KEY`

`.env` 示例：

```env
BAIDU_API_KEY=你的API Key
BAIDU_SECRET_KEY=你的Secret Key
```

排查思路与上面一致：变量名正确、`.env` 在项目根、已安装 `python-dotenv`、重启应用。

---

**总结**：服务器上出现「Zhipu API key 未配置」时，请依次确认 (1) 环境变量名为 `ZHIPUAI_API_KEY`；(2) `.env` 在项目根；(3) 已安装 `python-dotenv` 并重启应用；(4) 必要时用上面自检命令验证。
