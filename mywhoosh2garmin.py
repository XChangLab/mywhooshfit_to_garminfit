#!/usr/bin/env python3
"""
MyWhoosh FIT → Garmin Connect
FIT 增强 + 自动上传（纯 Python）

用法:
  python3 mywhoosh2garmin.py

环境变量（.env）:
  GARMIN_GLOBAL_USERNAME  - Garmin 账号邮箱
  GARMIN_GLOBAL_PASSWORD  - Garmin 账号密码
  GARMIN_DOMAIN           - garmin.cn (中国区) 或留空 (国际区)
  MYWHOOSH_FIT_DIR        - FIT 文件目录（留空弹出选择）
  ENHANCED_DIR            - 增强后输出目录（默认 ./enhanced_fit）
  FTP                     - FTP 功率值（设置后计算 NP/IF/TSS）
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def load_env():
    """从 .env 文件加载环境变量（简易版，不依赖 python-dotenv）"""
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def check_deps():
    """检查 Python 依赖"""
    missing = []
    for pkg, import_name in [('garminconnect', 'garminconnect'), ('fit-tool', 'fit_tool')]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f'❌ 缺失依赖: {", ".join(missing)}')
        print(f'   请运行: pip install {" ".join(missing)}')
        sys.exit(1)


def enhance_fit(input_path, output_path, ftp):
    """增强单个 FIT 文件"""
    script = Path(__file__).parent / 'enhance_fit_cli.py'
    if not script.exists():
        raise FileNotFoundError(f'增强脚本不存在: {script}')

    result = subprocess.run(
        [sys.executable, str(script), str(input_path), str(output_path), str(ftp)],
        capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    if not data.get('success'):
        raise Exception(data.get('error', '增强失败'))
    return data.get('output', output_path)


def upload_to_garmin(files, email, password, is_cn):
    """登录 Garmin 并上传文件"""
    from garminconnect import Garmin

    print(f'\n🔑 登录 Garmin {"CN" if is_cn else "Global"}...')
    garmin = Garmin(email=email, password=password, is_cn=is_cn)
    garmin.login()
    full_name = garmin.full_name or garmin.display_name or email
    print(f'   登录成功: {full_name}')

    results = []
    for file_path in files:
        name = Path(file_path).name
        print(f'   📤 上传 {name}...', end=' ')
        try:
            garmin.upload_activity(file_path)
            print('OK')
            results.append({'file': file_path, 'status': 'ok'})
        except Exception as e:
            msg = str(e)
            if '409' in msg:
                print('重复, 跳过')
                results.append({'file': file_path, 'status': 'duplicate'})
            else:
                print(f'失败: {msg}')
                results.append({'file': file_path, 'status': 'error', 'message': msg})
    return results


def main():
    print('==================================================')
    print('  MyWhoosh FIT → Garmin Connect')
    print('  FIT 增强 + 自动上传（纯 Python）')
    print('==================================================')

    load_env()
    check_deps()

    # 配置
    email = os.environ.get('GARMIN_GLOBAL_USERNAME', '')
    password = os.environ.get('GARMIN_GLOBAL_PASSWORD', '')
    is_cn = os.environ.get('GARMIN_DOMAIN', '').strip() == 'garmin.cn'
    fit_dir = os.environ.get('MYWHOOSH_FIT_DIR', '')
    enhanced_dir = os.environ.get('ENHANCED_DIR', './enhanced_fit')
    ftp = float(os.environ.get('FTP', '0'))

    # ── 1. 选择 FIT 目录 ──────────────────────────────────
    if not fit_dir:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            fit_dir = filedialog.askdirectory(title='选择 MyWhoosh FIT 目录')
            root.destroy()
        except ImportError:
            print('\n❌ 请设置 MYWHOOSH_FIT_DIR 环境变量，或安装 tkinter')
            sys.exit(1)

    if not fit_dir or not Path(fit_dir).exists():
        print(f'\n❌ 目录不存在或未选择: {fit_dir}')
        sys.exit(1)

    fit_files = sorted(Path(fit_dir).glob('*.fit'))
    if not fit_files:
        print(f'\n📭 {fit_dir} 中未找到 .fit 文件')
        return

    print(f'\n📂 FIT 目录: {fit_dir}')
    print(f'📁 找到 {len(fit_files)} 个 FIT 文件:')
    for f in fit_files:
        print(f'   - {f.name}')

    # ── 2. 输出目录 ──────────────────────────────────────
    out_dir = Path(enhanced_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'\n📂 输出目录: {out_dir.resolve()}')
    if ftp > 0:
        print(f'⚡ FTP: {ftp:.0f}w')

    # ── 3. 增强每个 FIT ────────────────────────────────────
    print(f'\n🔧 增强 FIT 文件中...')
    enhanced = []

    for i, f in enumerate(fit_files, 1):
        out_path = out_dir / f'enhanced_{f.name}'
        print(f'   [{i}/{len(fit_files)}] {f.name}...', end=' ')
        try:
            enhance_fit(f, out_path, ftp)
            enhanced.append(out_path)
            print('OK')
        except Exception as e:
            print(f'失败: {e}')

    if not enhanced:
        print('\n没有成功增强的文件，退出')
        return

    # ── 4. 上传到 Garmin ──────────────────────────────────
    if not email or not password:
        print(f'\n❌ 请配置 Garmin 账号: GARMIN_GLOBAL_USERNAME, GARMIN_GLOBAL_PASSWORD')
        print(f'   增强后的文件已保存到 {out_dir.resolve()}')
        return

    results = upload_to_garmin([str(f) for f in enhanced], email, password, is_cn)

    # ── 5. 汇总 ───────────────────────────────────────
    upload_ok = sum(1 for r in results if r['status'] == 'ok')
    dup_count = sum(1 for r in results if r['status'] == 'duplicate')
    fail_count = sum(1 for r in results if r['status'] == 'error')

    print(f'\n{"=" * 50}')
    print(f'   增强:     {len(enhanced)}/{len(fit_files)}')
    print(f'   上传:     {upload_ok}/{len(enhanced)}')
    if dup_count:
        print(f'   重复跳过: {dup_count}')
    if fail_count:
        print(f'   失败:     {fail_count}')
    if fail_count > 0 or upload_ok == 0:
        print(f'\n   失败文件保存在: {out_dir.resolve()}')
    print(f'{"=" * 50}')


if __name__ == '__main__':
    main()
