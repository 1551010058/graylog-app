"""Điểm vào khi cài bằng uv: `graylog-app` mở app, `gl` là dòng lệnh."""
import filecmp, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def gl():
    sys.exit(subprocess.call([sys.executable, os.path.join(HERE, 'gl.py')] + sys.argv[1:]))


def app():
    if sys.platform != 'darwin' or not shutil.which('swiftc'):
        # Windows, hoặc macOS chưa có Xcode Command Line Tools: cửa sổ Edge/Chrome dạng app
        sys.exit(subprocess.call([sys.executable, os.path.join(HERE, 'gl-ui.py'), '-', 'browser']))
    # Graylog.app chạy code ở ~/.local/bin: chép file đã đổi sang đó, build lại khi phần Swift đổi
    bin_, built = os.path.expanduser('~/.local/bin'), os.path.expanduser('~/Applications/Graylog.app')
    os.makedirs(bin_, exist_ok=True)
    changed = [f for f in ('gl.py', 'gl-ui.py', 'gl-app.swift', 'gl-icon.swift', 'gl-app-build')
               if not (os.path.exists(os.path.join(bin_, f)) and filecmp.cmp(os.path.join(HERE, f), os.path.join(bin_, f), shallow=False))]
    for f in changed: shutil.copy(os.path.join(HERE, f), os.path.join(bin_, f))
    if not os.path.exists(built) or any(not f.endswith('.py') for f in changed):
        subprocess.check_call(['/bin/zsh', os.path.join(bin_, 'gl-app-build')])
    elif changed:   # chỉ đổi phần Python: tắt app để lần mở dưới đây chạy code mới
        subprocess.call(['osascript', '-e', 'tell application id "local.linhmai.graylog" to quit'], stderr=subprocess.DEVNULL)
    subprocess.call(['open', built])
