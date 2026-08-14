#!/usr/bin/env python3
"""
MyWhoosh FIT 目录监视器 — 自动增强并上传到 Garmin Connect

用法:
  python3 watch_and_sync.py

环境变量同 mywhoosh2garmin.py，MYWHOOSH_FIT_DIR 必须设置。
依赖 watchdog 可获得即时检测 (pip install watchdog)，否则回退到轮询。
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mywhoosh2garmin import check_deps, enhance_fit, load_env, upload_to_garmin


def process_file(fit_file: Path, out_dir: Path, ftp: float, email: str, password: str, is_cn: bool) -> None:
    out_path = out_dir / f'enhanced_{fit_file.name}'
    print(f'\n🆕 新文件: {fit_file.name}')
    print(f'   🔧 增强中...', end=' ', flush=True)
    try:
        enhance_fit(fit_file, out_path, ftp)
        print('OK')
    except Exception as e:
        print(f'失败: {e}')
        return

    if not email or not password:
        print(f'   ⚠️  未配置 Garmin 账号，仅增强，跳过上传')
        print(f'   增强文件: {out_path}')
        return

    results = upload_to_garmin([str(out_path)], email, password, is_cn)
    status = results[0]['status'] if results else 'error'
    if status == 'ok':
        print(f'   ✅ 上传成功')
    elif status == 'duplicate':
        print(f'   ⏭️  重复活动，已跳过')
    else:
        msg = results[0].get('message', '') if results else ''
        print(f'   ❌ 上传失败: {msg}')


def _wait_for_file(path: Path, timeout: float = 30.0) -> bool:
    """等待文件写入完成（大小稳定）。"""
    deadline = time.monotonic() + timeout
    prev_size = -1
    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            time.sleep(0.5)
            continue
        if size == prev_size and size > 0:
            return True
        prev_size = size
        time.sleep(1)
    return False


def watch_with_watchdog(fit_dir: Path, out_dir: Path, ftp: float, email: str, password: str, is_cn: bool) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class FitHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() == '.fit':
                if _wait_for_file(path):
                    process_file(path, out_dir, ftp, email, password, is_cn)
                else:
                    print(f'\n⚠️  文件写入超时，跳过: {path.name}')

    observer = Observer()
    observer.schedule(FitHandler(), str(fit_dir), recursive=False)
    observer.start()
    print(f'👁  FSEvents 监视已启动: {fit_dir}')
    print(f'   等待新 .fit 文件... (Ctrl+C 停止)\n')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        print('\n监视已停止')


def watch_with_polling(fit_dir: Path, out_dir: Path, ftp: float, email: str, password: str, is_cn: bool, interval: int = 5) -> None:
    seen = {f for f in fit_dir.glob('*.fit')}
    print(f'👁  轮询监视已启动: {fit_dir}  (间隔 {interval}s)')
    print(f'   已忽略现有 {len(seen)} 个文件')
    print(f'   等待新 .fit 文件... (Ctrl+C 停止)\n')
    try:
        while True:
            time.sleep(interval)
            current = {f for f in fit_dir.glob('*.fit')}
            new_files = current - seen
            for f in sorted(new_files):
                if _wait_for_file(f):
                    process_file(f, out_dir, ftp, email, password, is_cn)
                else:
                    print(f'\n⚠️  文件写入超时，跳过: {f.name}')
            seen = current
    except KeyboardInterrupt:
        print('\n监视已停止')


def main() -> None:
    print('=' * 50)
    print('  MyWhoosh FIT 目录监视器')
    print('  自动增强 + 上传到 Garmin Connect')
    print('=' * 50)

    load_env()
    check_deps()

    email = os.environ.get('GARMIN_GLOBAL_USERNAME', '')
    password = os.environ.get('GARMIN_GLOBAL_PASSWORD', '')
    is_cn = os.environ.get('GARMIN_DOMAIN', '').strip() == 'garmin.cn'
    fit_dir_str = os.environ.get('MYWHOOSH_FIT_DIR', '')
    enhanced_dir = os.environ.get('ENHANCED_DIR', './enhanced_fit')
    ftp = float(os.environ.get('FTP', '0'))

    if not fit_dir_str:
        print('\n❌ 请在 .env 中设置 MYWHOOSH_FIT_DIR')
        sys.exit(1)

    fit_dir = Path(fit_dir_str)
    if not fit_dir.exists():
        print(f'\n❌ 目录不存在: {fit_dir}')
        sys.exit(1)

    out_dir = Path(enhanced_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'\n📂 监视目录: {fit_dir}')
    print(f'📂 输出目录: {out_dir.resolve()}')
    if ftp > 0:
        print(f'⚡ FTP: {ftp:.0f}w')
    if email:
        print(f'👤 Garmin 账号: {email}')
    else:
        print('⚠️  未配置 Garmin 账号（仅增强，不上传）')

    try:
        import watchdog  # noqa: F401
        watch_with_watchdog(fit_dir, out_dir, ftp, email, password, is_cn)
    except ImportError:
        print('\n提示: 安装 watchdog 可获得即时文件检测 (pip install watchdog)')
        watch_with_polling(fit_dir, out_dir, ftp, email, password, is_cn)


if __name__ == '__main__':
    main()
