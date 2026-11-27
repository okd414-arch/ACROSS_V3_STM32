# Freerouting が DSN を正しく読めるか (SMD ピンや未配線の数が出るか) を、短時間で打ち切って調べる (2026-11-21)
# usage: python fr_parsecheck.py file.dsn [秒]
import sys, subprocess, os, re

J = 'C:/OneDrive_link/KiCAD/freerouting-2.5.0-jar'
dsn = os.path.abspath(sys.argv[1])
sec = int(sys.argv[2]) if len(sys.argv) > 2 else 40
log = dsn + '.check.log'
with open(log, 'w', encoding='utf8') as f:
    rules = dsn[:-4] + '.rules'
    extra = ['-dr', rules] if os.path.exists(rules) else []
    p = subprocess.Popen([J + '/jdk/jdk-25.0.5+8/bin/java.exe', '-jar', J + '/freerouting.jar', '-de', dsn, '-do', dsn + '.check.ses'] + extra +
                         ['-mp', '1', '-mt', '2', '--gui.enabled=false'], stdout=f, stderr=subprocess.STDOUT, cwd=os.path.dirname(dsn))
    try:
        p.wait(timeout=sec)
    except subprocess.TimeoutExpired:
        p.kill()
txt = open(log, encoding='utf8', errors='replace').read()
for line in txt.splitlines():
    if re.search(r'WARN|ERROR|SMD pins|unrouted items|violation|Exception', line) and 'Deprecated' not in line and 'HttpClient' not in line:
        print(line[:220])
for ext in ('.check.ses',):
    if os.path.exists(dsn + ext):
        os.remove(dsn + ext)
