#!/usr/bin/env python
"""v3 基线 SQL 脱敏:芋道官方 sql/*.sql 种子数据含云厂商演示 Key 形态串
(GitHub push protection 会拦:Tencent Cloud Secret ID / Alibaba Cloud AccessKey ID),
以及芋道演示/测试号微信 AppID(wx+16位hex)与 Google API Key(AIza) 形态串
(secret scanning 会持续报 alert;09-24 定性:全部为芋道自带演示值,非本仓真实凭据)。

用法:python scripts/v3_sanitize_sql_secrets.py [--check]
  --check  只检查不落盘(退出码 1=仍有命中)
背景:芋道 infra_file_config 等演示行含 LTAIxxx/AKIDxxx 形态值,本仓库推送被
GH013 拦截后处置。上游重新导出(baseline 升级)后必须重跑本脚本再提交。
"""
import re
import sys
import glob
import io
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'awardie-v3', 'sql')
PATTERNS = [
    re.compile(r'LTAI[A-Za-z0-9]{8,}'),   # 阿里云 AccessKey ID 形态
    re.compile(r'AKID[A-Za-z0-9]{8,}'),   # 腾讯云 SecretId 形态
    re.compile(r'AKLT[A-Za-z0-9]{8,}'),   # 火山引擎 AccessKey ID 形态
    re.compile(r'wx[0-9a-f]{16}'),        # 微信 AppID 形态(芋道演示/测试号)
    re.compile(r'AIza[A-Za-z0-9_\-]{30,}'),  # Google API Key 形态
]
# 业务 SQL 非芋道种子,其中的 wx 串可能是真实业务配置,禁止自动替换
SKIP_FILES = {'awardie-business.sql'}
REPLACEMENT = 'DEMO-REMOVED-BY-AWARDIE'


def main() -> int:
    check_only = '--check' in sys.argv
    files = [f for f in sorted(glob.glob(os.path.join(ROOT, '*', '*.sql')))
             if os.path.basename(f) not in SKIP_FILES]
    dirty = 0
    for f in files:
        s = io.open(f, encoding='utf-8').read()
        orig = s
        for p in PATTERNS:
            s = p.sub(REPLACEMENT, s)
        if s != orig:
            dirty += 1
            if not check_only:
                io.open(f, 'w', encoding='utf-8', newline='').write(s)
            print(('HIT ' if check_only else 'FIXED ') + f)
    if check_only and dirty:
        print(f'仍有 {dirty} 个文件含命中串,禁止推送')
        return 1
    print(f'scanned {len(files)} files, {"dirty" if dirty else "clean"}={dirty}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
