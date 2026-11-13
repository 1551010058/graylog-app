#!/usr/bin/python3
# Giao diện web của gl: server tạm trên 127.0.0.1, mọi việc thật đều gọi lại script gl.
# Chạy: gl-ui.py <đường dẫn gl> app — Graylog.app khởi động, in URL ra stdout, thoát khi app thoát.
from concurrent.futures import ThreadPoolExecutor
import glob, threading
import datetime, html, http.server, json, os, re, secrets, subprocess, sys, time, urllib.parse

WIN = os.name == 'nt'
if WIN and not sys.flags.utf8_mode:   # Windows mặc định không phải UTF-8 -> chạy lại ở chế độ UTF-8
    sys.exit(subprocess.call([sys.executable, '-X', 'utf8'] + sys.argv))
PY = sys.executable
if WIN and os.path.basename(PY).lower() == 'pythonw.exe': PY = os.path.join(os.path.dirname(PY), 'python.exe')
# mọi việc thật do gl.py nằm cạnh file này làm (tham số đầu của dòng lệnh là đường dẫn gl cũ, không còn dùng)
GL = [PY] + (['-X', 'utf8'] if WIN else []) + [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gl.py')]
NOWIN = {'creationflags': 0x08000000} if WIN else {}   # không nháy cửa sổ đen trên Windows
CONF = os.path.expanduser('~/.config/gl')
SEP = '   —   '
SECS = {'15 phút': 900, '1 giờ': 3600, '2 giờ': 7200, '6 giờ': 21600, '24 giờ': 86400, '7 ngày': 604800}
TIMES = list(SECS)
RANGE = re.compile(r'(\d{4}-\d\d-\d\dT\d\d:\d\d)~(\d{4}-\d\d-\d\dT\d\d:\d\d)')   # "từ~đến" theo giờ máy, từ ô datetime-local
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def span(tm):
    m = RANGE.fullmatch(tm)
    try: a, b = (datetime.datetime.fromisoformat(x) for x in m.groups())
    except (AttributeError, ValueError): return None
    return (a, b) if a < b else None


def rng(tm):   # tham số thời gian cho gl _search: số giây gần đây, hoặc "từ~đến" đổi sang UTC
    if tm in SECS: return str(SECS[tm])
    return '~'.join(x.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z') for x in span(tm))


def tml(tm):   # chữ hiển thị của khoảng thời gian, kèm múi giờ
    if tm in SECS: return tm
    a, b = span(tm)
    return '%s → %s (GMT%s)' % (a.strftime('%d/%m/%Y %H:%M'), b.strftime('%H:%M' if a.date() == b.date() else '%d/%m/%Y %H:%M'), a.astimezone().strftime('%z')[:3])
TOK = secrets.token_urlsafe(16)   # nằm trong mọi đường dẫn: trang web khác không gọi được server này
B = '/' + TOK
E = html.escape

CSS = """<meta charset=utf-8><style>
:root{color-scheme:light dark}
body{font:15px/1.5 -apple-system,sans-serif;max-width:760px;margin:40px auto;padding:0 20px}
a{color:#2f6fed}
.card{display:flex;align-items:center;gap:12px;border:1px solid #8885;border-radius:10px;padding:14px 16px;margin:10px 0}
.card .i{flex:1;min-width:0}.card small{display:block;opacity:.65;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card form{margin:0}
button,.btn{font:inherit;padding:7px 14px;border:1px solid #8888;border-radius:8px;background:none;color:inherit;cursor:pointer;text-decoration:none;white-space:nowrap}
.p{background:#2f6fed;border-color:#2f6fed;color:#fff;font-weight:600}.d{color:#d33}
.nav .r{margin-left:auto}.nav{position:sticky;top:0;z-index:9;display:flex;gap:8px;padding:10px 0;margin:-40px 0 10px;background:Canvas;border-bottom:1px solid #8885}
.flash{white-space:pre-wrap;border-left:4px solid #2f6fed;background:#2f6fed1a;padding:10px 14px;border-radius:6px}
label{display:block;margin:14px 0 5px;font-weight:600}
input,select,textarea{font:inherit;width:100%;box-sizing:border-box;padding:9px 12px;border:1px solid #8888;border-radius:8px;background:none;color:inherit}
.box{border:1px solid #8885;border-radius:10px;padding:4px 16px 16px;margin:18px 0}
summary{cursor:pointer;font-weight:600;padding:10px 0}
.row{margin-top:18px;display:flex;gap:10px}
#l{border:1px solid #8888;border-radius:8px;margin-top:4px;box-shadow:0 6px 18px #0003}#l:empty{display:none}
#l div{padding:8px 12px;cursor:pointer}#l div:hover{background:#2f6fed33}#l .a{color:#2f6fed;border-top:1px solid #8884}
.m{border-top:1px solid #8885;padding:8px 0}.m .h{display:flex;justify-content:space-between;font-weight:700}.m .h span{font-weight:400;opacity:.7}
.m pre{margin:4px 0 0;font:12.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:22em;overflow:auto}
.wide{max-width:1200px}
#ld{position:fixed;top:0;left:0;z-index:99;height:3px;width:30vw;background:#2f6fed;border-radius:3px;display:none;animation:ld 1s linear infinite}
@keyframes ld{from{transform:translateX(-30vw)}to{transform:translateX(100vw)}}@keyframes sp{to{transform:rotate(360deg)}}
html.ld #ld{display:block}html.ld{cursor:progress}html.ld .btn,html.ld button{pointer-events:none;opacity:.55}html.ld .going{opacity:1}
#ait{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:99;padding:12px 20px;border-radius:12px;background:#2f6fed;color:#fff;font-weight:600;font-size:14px;box-shadow:0 8px 30px #000a;white-space:nowrap}
.going::after{content:"";display:inline-block;width:.75em;height:.75em;margin-left:8px;vertical-align:-1px;border:2px solid currentColor;border-right-color:transparent;border-radius:9px;animation:sp .6s linear infinite}
.ctx{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0 4px;font-size:13px}
.ctx span{padding:3px 11px;border-radius:99px;background:#8882;border:1px solid #8884;white-space:nowrap}
.ctx span:first-child{background:#2f6fed;border-color:#2f6fed;color:#fff;font-weight:600}
</style><div id=ld></div><script>
(()=>{const H=document.documentElement;let tm,iv;
const on=(el,ai)=>{H.classList.add('ld');el&&el.classList.add('going');clearTimeout(tm);tm=setTimeout(off,ai?600000:60000);
if(ai){const t=document.createElement('div'),t0=Date.now();t.id='ait';document.body.append(t);(t.f=()=>{t.textContent='AI đang đọc log và phân tích… '+Math.round((Date.now()-t0)/1000)+' giây (thường 30 giây – vài phút, cứ để yên)'})();iv=setInterval(t.f,1000)}};
const off=()=>{clearInterval(iv);document.querySelectorAll('#ait').forEach(e=>e.remove());H.classList.remove('ld');document.querySelectorAll('.going').forEach(e=>e.classList.remove('going'))};
addEventListener('pageshow',off);
addEventListener('click',e=>{const a=e.target.closest('a[href]');if(a&&(!e.defaultPrevented||a.getAttribute('onclick')))on(a)});
addEventListener('submit',e=>{if(!e.defaultPrevented){const s=e.submitter,a=e.target.elements.act;on(s,(s&&s.value=='ai')||(a&&a.value=='ai'))}});})();
</script>"""


def gl(*args, stdin=''):
    r = subprocess.run(GL + list(args), input=stdin, capture_output=True, text=True, encoding='utf-8', errors='replace', **NOWIN)
    return r.returncode, (r.stdout + r.stderr).strip()


def partners():
    rows = []
    try:
        for line in open(os.path.join(CONF, 'partners'), encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) == 3: rows.append(p)
    except FileNotFoundError:
        pass
    return rows


def ico(n):   # icon nét mảnh, dùng chung cho trang đối tác
    d = {'search': '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
         'out': '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
         'dots': '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
         'edit': '<path d="m4 20 1-4L16 5l3 3L8 19z"/>', 'trash': '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
         'plus': '<path d="M12 5v14M5 12h14"/>', 'eye': '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
         'plug': '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>', 'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
         'x': '<path d="M5 5l14 14M19 5 5 19"/>', 'spark': '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z"/>',
         'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', 'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>', 'back': '<path d="M19 12H5M11 6l-6 6 6 6"/>',
         'copy': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>', 'link': '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
         'sort': '<path d="M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4"/>', 'full': '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', 'box': '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9"/>',
         'layers': '<path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/>', 'cal': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>', 'refresh': '<path d="M20 11a8 8 0 1 0-2.3 6.3M20 4v7h-7"/>'}[n]
    return '<svg class=ic viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % d


PCSS = """<style>
body{max-width:1240px}.ic{width:1.15em;height:1.15em;vertical-align:-.2em;flex:none}
.lay{display:grid;gap:18px;align-items:start}.lay.on{grid-template-columns:minmax(0,1fr) 370px}
@media(max-width:860px){.lay.on{grid-template-columns:1fr}}
.ls,.pn{border:1px solid #8884;border-radius:14px;background:#8881;padding:24px}
.ey{font-size:12px;font-weight:600;letter-spacing:.08em;opacity:.6;text-transform:uppercase}
.ls h1,.pn h2{margin:4px 0 2px;font-size:28px}.pn h2{font-size:22px;margin-top:0}.sub{margin:0;opacity:.65}
.pill{display:inline-block;margin:12px 0 0;padding:3px 12px;border-radius:99px;background:#8882;border:1px solid #8884;font-size:13px;font-weight:600}
.bar{display:flex;gap:12px;margin:16px 0}.bar .sw{flex:1;position:relative}.bar .sw .ic{position:absolute;left:12px;top:11px;opacity:.6}.bar input{padding-left:38px}
.tbl{border:1px solid #8884;border-radius:12px}.tr{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr) auto;gap:16px;align-items:center;padding:12px 16px;border-top:1px solid #8883}
.tr.hd{border:0;background:#8881;border-radius:12px 12px 0 0;font-size:12px;font-weight:600;letter-spacing:.06em;opacity:.65;text-transform:uppercase}.tr[hidden]{display:none}
.nm{display:flex;align-items:center;gap:12px;font-weight:600;min-width:0}.nm span:last-child{overflow:hidden;text-overflow:ellipsis}
.av{width:36px;height:36px;border-radius:8px;background:#2f6fed33;color:#6ea0ff;display:grid;place-items:center;font-size:13px;flex:none}
.cn{min-width:0;font:13px ui-monospace,Menlo,monospace}.cn div{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cn small{display:block;font:13px -apple-system,sans-serif;opacity:.6;margin-top:2px}
.ac{display:flex;gap:8px;align-items:center;min-width:262px}.ac form{margin:0}.ac .btn,.ac button{display:inline-flex;gap:7px;align-items:center}
.mn{position:relative}.mn summary{list-style:none;padding:7px 12px;font-weight:400}.mn summary::-webkit-details-marker{display:none}.mn[open] summary{border-color:#2f6fed}
.mnu{position:absolute;right:0;top:calc(100% + 6px);z-index:5;min-width:190px;padding:6px;border:1px solid #8886;border-radius:10px;background:Canvas;box-shadow:0 10px 30px #0006}
.mnu a,.mnu button{display:flex;gap:10px;align-items:center;width:100%;padding:8px 10px;border:0;border-radius:6px;color:inherit;text-decoration:none;box-sizing:border-box}
.mnu a:hover,.mnu button:hover{background:#8882}.mnu .d{color:#e5484d}
.ft{padding:12px 16px;border-top:1px solid #8883;font-size:13px;opacity:.6}
.pn{position:sticky;top:16px}.pn .x{float:right;border:0;padding:4px;opacity:.7}.pn small.h{display:block;margin-top:5px;font-size:12.5px;opacity:.6}
.pw{position:relative}.pw input{padding-right:44px}.pw button{position:absolute;right:4px;top:4px;border:0;padding:6px 8px;opacity:.7}
.ck{display:flex;gap:12px;align-items:center;margin-top:18px;font-size:13.5px}.ck button{display:inline-flex;gap:8px;align-items:center}.ck span{opacity:.75}.ck .ok{color:#3dd68c;opacity:1}.ck .no{color:#ff6369;opacity:1}
.end{display:flex;justify-content:flex-end;gap:10px;margin-top:24px;padding-top:16px;border-top:1px solid #8883}
</style>"""


def partner_form(old):
    cur = next((p for p in partners() if p[0] == old), ['', '', '']) if old else ['', '', '']
    close = ('<a class="btn%s" href="@B@"%s>%s</a>' if old else '<button type=button class="%s" onclick="panel(0)"%s>%s</button>')
    h = """<aside class=pn id=pn@HID@>@X@<h2>@TITLE@</h2><p class=sub>Thông tin kết nối Graylog</p>
<form method=post action="@B@/save" id=pf><input type=hidden name=old value="@OLD@">
<label>Tên đối tác</label><input name=name value="@N@" placeholder="vd: shop-prod" required onchange="this.value=this.value.toLowerCase().replace(/ /g,'-').replace(/[^a-z0-9._-]/g,'')"><small class=h>Chữ thường, số và dấu . _ -</small>
<label>Địa chỉ Graylog</label><input name=url value="@U@" placeholder="http://10.0.0.1:9000" required>
<label>Tài khoản</label><input name=user value="@USER@" placeholder="Nhập tên đăng nhập" required>
<label>Mật khẩu</label><div class=pw><input name=pw type=password @PW@><button type=button title="Hiện / ẩn mật khẩu" onclick="(async()=>{const i=this.previousElementSibling,o=pf.elements.old.value;if(!i.value&&o){i.value=await(await fetch('@B@/pw',{method:'POST',body:new URLSearchParams({name:o})})).text();i.type='text'}else i.type=i.type=='password'?'text':'password'})()">@EYE@</button></div>
<div class=ck><button type=button id=tb>@PLUG@ Kiểm tra kết nối</button><span id=ts>Chưa kiểm tra kết nối</span></div>
<div class=end>@CANCEL@<button class=p>Lưu đối tác</button></div></form></aside>
<script>tb.onclick=async()=>{ts.className='';ts.textContent='Đang kiểm tra…';tb.disabled=true;
try{const t=await(await fetch('@B@/test',{method:'POST',body:new URLSearchParams(new FormData(pf))})).text();ts.textContent=t;ts.className=t[0]=='✓'?'ok':'no'}
catch(e){ts.textContent='✕ Không gọi được app';ts.className='no'}tb.disabled=false}</script>"""
    for k, v in [('@X@', close % ('x', '', ico('x')) if not old else close % (' x', '', ico('x'))),
                 ('@CANCEL@', close % ('', '', 'Hủy')), ('@HID@', '' if old or not partners() else ' hidden'),
                 ('@TITLE@', 'Sửa %s' % E(old) if old else 'Thêm đối tác'), ('@OLD@', E(old)), ('@N@', E(cur[0])), ('@U@', E(cur[1])),
                 ('@USER@', E(cur[2])), ('@PW@', 'placeholder="để trống = giữ nguyên"' if old else 'required'),
                 ('@EYE@', ico('eye')), ('@PLUG@', ico('plug')), ('@B@', B)]:
        h = h.replace(k, v)
    return h


def main_page(msg, edit):
    ps = partners()
    rows = ''.join("""<div class=tr><div class=nm><span class=av>%(av)s</span><span>%(n)s</span></div>
<div class=cn><div title="%(u)s">%(host)s</div><small>%(iu)s %(user)s</small></div>
<div class=ac><a class=btn href="%(b)s/ask?name=%(q)s">%(is)s Tìm log</a>
<form method=post action="%(b)s/open"><input type=hidden name=name value="%(n)s"><button title="Mở Graylog trên trình duyệt">%(io)s</button></form>
<details class=mn><summary class=btn title="Thao tác khác">%(id)s</summary><div class=mnu><a href="%(b)s?edit=%(q)s">%(ie)s Chỉnh sửa</a>
<form method=post action="%(b)s/rm" onsubmit="return confirm('Xoá hẳn %(n)s?')"><input type=hidden name=name value="%(n)s"><button class=d>%(it)s Xóa đối tác</button></form></div></details></div>
</div>""" % {'b': B, 'n': E(n), 'u': E(u), 'user': E(user), 'q': urllib.parse.quote(n), 'host': E(re.sub(r'^https?://', '', u).rstrip('/')),
             'av': E(''.join(w[0] for w in re.split(r'[._-]+', n) if w)[:2].upper() if re.search(r'[._-]', n) else n[:2].upper()),
             'is': ico('search'), 'io': ico('out'), 'id': ico('dots'), 'ie': ico('edit'), 'it': ico('trash'), 'iu': ico('user')} for n, u, user in ps)
    on = bool(edit) or not ps
    return CSS + PCSS + '<title>Graylog</title>' + ('<p class=flash>%s</p>' % E(msg) if msg else '') + """<div class="lay%s" id=lay><section class=ls>
<div class=ey>Không gian làm việc</div><h1>Graylog - Đối tác</h1><p class=sub>Chọn kết nối để tìm log và phân tích sự cố.</p><span class=pill>%d đối tác</span>
<div class=bar><div class=sw>%s<input id=fq placeholder="Tìm đối tác…" autocomplete=off></div><button type=button class=p onclick="panel(1)" style="display:inline-flex;gap:8px;align-items:center">%s Thêm đối tác</button></div>
<div class=tbl><div class="tr hd"><div>Đối tác</div><div>Kết nối</div><div style="min-width:262px">Thao tác</div></div>%s<div class=ft>%s</div></div>
</section>%s</div><script>
function panel(o){%spn.hidden=!o;lay.classList.toggle('on',!!o);if(o)pf.elements.name.focus()}
fq.oninput=()=>{const k=fq.value.trim().toLowerCase();document.querySelectorAll('.tr:not(.hd)').forEach(r=>r.hidden=!(r.children[0].textContent+r.children[1].textContent).toLowerCase().includes(k))};
if(location.hash=='#add')panel(1);
addEventListener('click',e=>document.querySelectorAll('.mn[open]').forEach(m=>{if(!m.contains(e.target))m.open=false}));
</script>""" % (' on' if on else '', len(ps), ico('search'), ico('plus'), rows,
                '%d kết nối đã lưu' % len(ps) if ps else 'Chưa có đối tác nào — điền form bên cạnh để thêm.',
                partner_form(edit), "if(o&&%s){location='%s#add';return}" % ('true' if edit else 'false', B))


def usage(name, key=None):
    # đếm số lần mỗi stream ("s:<id>") / application ("a:<tên>") được dùng, theo từng đối tác -> xếp cái hay dùng lên đầu
    f = os.path.join(CONF, 'usage.json')
    try: d = json.load(open(f))
    except (OSError, ValueError): d = {}
    u = d.setdefault(name, {})
    if key:
        u[key] = u.get(key, 0) + 1
        json.dump(d, open(f + '.tmp', 'w')); os.replace(f + '.tmp', f)
    return u


KEEP = 30 * 86400   # lịch sử (hội thoại AI, lần tìm) chỉ giữ 30 ngày


def prune():
    # xoá hội thoại AI không có câu hỏi mới nào trong 30 ngày (tính theo lần hỏi cuối của cả cuộc hội thoại)
    d, cut, keep = os.path.join(CONF, 'ask'), time.time() - KEEP, set()
    try:
        for t in glob.glob(os.path.join(d, '*.thread')):
            if os.path.getmtime(t) >= cut: keep |= {os.path.basename(t)[:-7]} | {f.split('.')[0] for f in open(t).read().split()}
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if re.match(r'\d{8}-\d{6}\.', f) and f.split('.')[0] not in keep and os.path.getmtime(p) < cut: os.remove(p)
    except OSError: pass


def history(name):
    prune()
    # các cuộc trò chuyện AI của đối tác này (file <tid>.who ghi tên đối tác), mới nhất trước
    d, out = os.path.join(CONF, 'ask'), []
    for w in sorted(glob.glob(os.path.join(d, '*.who')), reverse=True):
        try:
            if open(w).read().strip() != name: continue
            tid = os.path.basename(w)[:-4]
            files = open(os.path.join(d, tid + '.thread')).read().split()
            meta = open(os.path.join(d, files[0][:-5] + '.meta'), encoding='utf-8').read().split('\n')
        except (OSError, IndexError): continue
        out.append('<a class=h href="%s/c/%s/%s"><b>%s</b><small>%s/%s %s:%s · %s · %d câu</small></a>' % (
            B, urllib.parse.quote(name), tid, E(meta[4][:90]), tid[6:8], tid[4:6], tid[9:11], tid[11:13], E(meta[2]), len(files)))
        if len(out) == 200: break
    return out


def searches(name, item=None):
    # các lần tìm log gần đây của từng đối tác: [sid, tên stream, app, tm, q, lúc tìm], mới nhất trước, giữ 30
    f = os.path.join(CONF, 'searches.json')
    try: d = json.load(open(f))
    except (OSError, ValueError): d = {}
    l = d[name] = [x for x in d.get(name, []) if len(x) < 7 or x[6] > time.time() - KEEP]
    if item:
        d[name] = l = ([item + [datetime.datetime.now().strftime('%d/%m %H:%M'), time.time()]] + [x for x in l if x[:5] != item])[:30]
        json.dump(d, open(f + '.tmp', 'w'), ensure_ascii=False); os.replace(f + '.tmp', f)
    return [x[:6] for x in l]


ACSS = """<style>
[hidden]{display:none!important}
.top{display:flex;align-items:center;gap:10px;margin:-16px 0 14px}.bc{flex:1;opacity:.7}.bc a{color:inherit}.bc b{opacity:1}
.top .btn,.top button,.go{display:inline-flex;gap:8px;align-items:center}
.lay.on{grid-template-columns:minmax(0,1fr) 300px}
.hdr{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-bottom:6px}.hdr div:first-child{flex:1;min-width:240px}.ls h1{margin-top:0}
.seg{display:inline-flex;gap:3px;padding:3px;border:1px solid #8885;border-radius:10px}.seg button{border:0;padding:6px 14px;display:inline-flex;gap:7px;align-items:center;opacity:.75}
.seg .on,.tc .on{background:#2f6fed2e;color:#5b93ff;box-shadow:inset 0 0 0 1px #2f6fed;opacity:1;font-weight:600}
.st{display:flex;gap:10px;align-items:center;font-weight:700;margin:26px 0 4px;padding-top:20px;border-top:1px solid #8883}
.st b{width:24px;height:24px;border-radius:99px;background:#2f6fed2e;color:#5b93ff;display:grid;place-items:center;font-size:13px}
.g2{display:flex;flex-wrap:wrap;gap:0 18px}.g2>div{flex:1;min-width:200px}
.lb{display:flex;justify-content:space-between;align-items:baseline;margin:14px 0 5px;font-weight:600}.lb button{border:0;padding:0;color:#5b93ff;font-weight:400;font-size:13px}
.hint{display:block;margin-top:5px;font-size:12.5px;opacity:.6}
.kw{position:relative}.kw input{padding-right:38px}.kw>button{position:absolute;right:4px;top:4px;border:0;padding:6px 8px;opacity:.7}
#l{position:absolute;left:0;right:0;z-index:6;background:Canvas}#l div{display:flex;gap:10px;align-items:center}#l span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#l i{font-style:normal;font-size:11.5px;padding:1px 8px;border-radius:99px;background:#8882;border:1px solid #8884}#l small{margin-left:auto;opacity:.6;white-space:nowrap}
#ch{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}#ch:empty{display:none}.chip{padding:3px 10px;font-size:13px;border-radius:99px}
.tc{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.tc button{padding:6px 14px}
.ex{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px;font-size:13px}.ex button{padding:3px 10px;font:12.5px ui-monospace,Menlo,monospace;border-radius:6px}
.ex details{flex-basis:100%}.ex summary{padding:2px 0;font-weight:400;color:#5b93ff}.ex pre{margin:6px 0 0;font:12.5px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap;opacity:.8}
.fo{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:24px;padding-top:16px;border-top:1px solid #8883}
.fo #sum{flex:1;min-width:0;font-size:13px;opacity:.7;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fo kbd{font:12px -apple-system,sans-serif;opacity:.55;border:1px solid #8885;border-radius:6px;padding:2px 7px}
.sd{display:grid;gap:18px;grid-template-columns:minmax(0,1fr)}.cd{border:1px solid #8884;border-radius:14px;background:#8881;padding:18px}.cd h3{margin:0 0 10px;font-size:15px}.cd p{margin:8px 0 0;font-size:13px;opacity:.65}
.kvs{display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px 14px;font-size:13.5px}.kvs span{opacity:.6}.kvs b{text-align:right;font-weight:600;overflow:hidden;text-overflow:ellipsis}
.rt{display:flex;gap:16px;border-bottom:1px solid #8883;margin-bottom:10px}.rt button{border:0;border-radius:0;padding:6px 0;opacity:.65;font-size:13.5px}.rt .on{opacity:1;font-weight:600;box-shadow:inset 0 -2px #2f6fed}
.rl{max-height:420px;overflow:auto;margin-top:6px}.rl form{margin:0}.rl .no{font-size:13px;opacity:.6;padding:8px 2px}
.h[hidden]{display:none}.h{display:block;width:100%;box-sizing:border-box;text-align:left;white-space:normal;padding:8px 10px;margin:6px 0;border:1px solid #8884;border-radius:8px;color:inherit;text-decoration:none;font-size:13.5px}
.h:hover{background:#8882}.h b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.h small{display:block;opacity:.6;margin-top:2px;font-weight:400}
</style>"""


def ask_page(name, streams):
    u = usage(name)
    streams = sorted([[t, i, '', u.get('s:' + i, 0)] for t, i in streams] +
                     [[k[2:], '', k[2:], c] for k, c in u.items() if k.startswith('a:')], key=lambda x: -x[3])
    hist = history(name)
    srch = ''.join('<form method=post><input type=hidden name=name value="%s"><input type=hidden name=sid value="%s"><input type=hidden name=app value="%s">'
                   '<input type=hidden name=tm value="%s"><input type=hidden name=q value="%s"><button class=h title="Tìm lại"><b>%s</b><small>%s · %s · %s</small></button></form>'
                   % (E(name), E(sid), E(app), E(tm), E(q), E(q) or '(mọi log)', E(title or app or 'Tất cả stream'), E(tml(tm) if tm in SECS or span(tm) else tm), E(at))
                   for sid, title, app, tm, q, at in searches(name))
    t = """<title>Graylog — @n@</title><div class=top><div class=bc><a href="@b@">Đối tác</a> &nbsp;/&nbsp; <b>@n@</b></div><a class=btn id=fw hidden href="javascript:history.forward()">Tới →</a><script>{const S=sessionStorage,fn=()=>+S.fwd||0;addEventListener(`pageshow`,()=>{fw.hidden=!(fn()>0||(window.navigation&&navigation.canGoForward))});addEventListener(`click`,e=>{const a=e.target.closest(`a`);if(!a)return;S.fwd=a.id==`fw`?fn()-1:a.getAttribute(`onclick`)?fn()+1:0},true);addEventListener(`submit`,e=>{if(!e.defaultPrevented)S.fwd=0});}</script><button type=button id=og title="Mở Graylog trên trình duyệt">@io@ Mở Graylog</button></div>
<div class="lay on"><form method=post id=f class=ls><input type=hidden name=name value="@n@"><input type=hidden name=sid id=sid><input type=hidden name=app id=app><input type=hidden name=tm id=tm><input type=hidden name=act id=act>
<div class=hdr><div><h1 id=hh></h1><p class=sub>Tìm log theo phạm vi rõ ràng hoặc đặt câu hỏi cho AI.</p></div>
<div class=seg><button type=button data-m=0>@is@ Tìm log</button><button type=button data-m=1>@ia@ Hỏi AI</button></div></div>
<div class=st><b>1</b>Phạm vi tìm kiếm</div>
<div class=g2><div><div class=lb>Đối tác</div><select id=pt>@pts@</select></div>
<div><div class=lb>Loại lọc</div><div class=seg><button type=button data-k=s>Stream</button><button type=button data-k=a>Application</button></div><small class=hint>Chọn loại bộ lọc trước khi nhập tên.</small></div></div>
<div class=lb><span id=kl></span><button type=button id=all>Tất cả stream</button></div>
<div class=kw><input id=k autocomplete=off><button type=button id=kx title="Xoá chữ đang gõ" hidden>@ix@</button><div id=l></div></div><div id=ch></div>
<div class=st><b>2</b>Thời gian</div>
<div class=tc>@tcs@<button type=button data-t=custom>Tùy chỉnh</button></div>
<div class=g2><div><div class=lb>Từ</div><input type=datetime-local id=tf></div><div><div class=lb>Đến</div><input type=datetime-local id=tt></div></div>
<small class=hint id=tz></small>
<div class=st><b>3</b><span id=qt></span></div>
<div class=lb><span id=ql></span></div><textarea name=q id=q rows=2 autofocus></textarea><small class=hint id=qh></small>
<div class=ex id=ex><span style="opacity:.6">Ví dụ</span><button type=button>level:3</button><button type=button>trace_id:</button><button type=button>"cụm từ chính xác"</button>
<details><summary>Hướng dẫn cú pháp</summary><pre>DH000123            tìm chữ này ở mọi trường
"connection reset"    đúng cả cụm từ
level:3               theo trường (3 = lỗi, 4 = cảnh báo)
a AND b · a OR b · NOT a
source:pos-*          dấu * thay cho phần còn lại</pre></details></div>
<div class=fo><span id=sum></span><kbd>⌘ Enter</kbd><button class="p go" id=go></button></div>
</form>
<aside class=sd><div class=cd><h3>Phạm vi đã chọn</h3><div class=kvs><span>Đối tác</span><b>@n@</b><span>Loại lọc</span><b id=v1></b><span id=v2k></span><b id=v2></b><span>Khoảng thời gian</span><b id=v3></b></div><p>Kết quả mở ngay trong cửa sổ này.</p></div>
<div class=cd><h3>Gần đây <small style="font-weight:400;opacity:.55;font-size:12px">· giữ 30 ngày, cũ hơn tự xoá</small></h3><div class=rt><button type=button data-r=0>Tìm kiếm (@ns@)</button><button type=button data-r=1>Hội thoại AI (@nh@)</button></div>
<input id=hs placeholder="Lọc trong danh sách…" autocomplete=off>
<div class=rl id=r0>@srch@</div><div class=rl id=r1>@hist@</div></div>
<div class=cd id=tip><h3>@ia@ Cần giải thích log?</h3><p style="margin:0 0 12px">Chuyển sang Hỏi AI để mô tả vấn đề bằng ngôn ngữ tự nhiên.</p><button type=button data-m=1>Hỏi AI</button></div></aside></div>
<script>
const S=@s@,SECS=@secs@,NAME=@nj@,B=@bj@,$=i=>document.getElementById(i),QA=(s,f)=>document.querySelectorAll(s).forEach(f);
const F=$('f'),k=$('k'),l=$('l'),ch=$('ch'),q=$('q'),tf=$('tf'),tt=$('tt'),go=$('go'),hs=$('hs'),KEY='form:'+NAME;
let sel=[],kind='s',ai=0,tmv='1 giờ',rtab=0;
const el=(t,x,c)=>{const e=document.createElement(t);e.textContent=x;if(c)e.className=c;return e};
const iso=d=>new Date(d-d.getTimezoneOffset()*6e4).toISOString().slice(0,16),fmt=v=>v.slice(8,10)+'/'+v.slice(5,7)+' '+v.slice(11);
function show(){const kw=k.value.trim().toLowerCase();l.replaceChildren();
  S.filter(s=>!!s[2]==(kind=='a')&&s[0].toLowerCase().includes(kw)&&!(kind=='s'&&sel.some(x=>x[1]==s[1]))).slice(0,8).forEach(s=>{
    const d=el('div','');d.append(el('span',s[0]),el('i',kind=='s'?'Stream':'Application'));if(s[3])d.append(el('small','Đã dùng '+s[3]+' lần'));
    d.onmousedown=e=>{e.preventDefault();if(kind=='a')k.value=s[0];else{sel.push([s[0],s[1]]);k.value=''}l.replaceChildren();draw()};l.append(d)})}
function draw(){
  $('sid').value=kind=='s'?sel.map(x=>x[1]).join():'';$('app').value=kind=='a'?k.value.trim():'';$('act').value=ai?'ai':'search';
  ch.replaceChildren(...(kind=='s'?sel:[]).map((x,i)=>{const b=el('button',x[0]+'  ✕','chip');b.type='button';b.title='Bỏ stream này';b.onclick=()=>{sel.splice(i,1);draw()};return b}));
  QA('[data-k]',b=>b.classList.toggle('on',b.dataset.k==kind));QA('[data-t]',b=>b.classList.toggle('on',b.dataset.t==tmv));
  QA('.seg [data-m]',b=>b.classList.toggle('on',+b.dataset.m==ai));QA('[data-r]',b=>b.classList.toggle('on',+b.dataset.r==rtab));
  $('r0').hidden=rtab!=0;$('r1').hidden=rtab!=1;$('kx').hidden=!k.value;$('all').hidden=kind!='s'||!sel.length;
  const kn=kind=='s'?'Stream':'Application',sc=kind=='s'?(sel.length?sel.map(x=>x[0]).join(', '):'Tất cả stream'):($('app').value||'Mọi application');
  const tl=tmv=='custom'?(tf.value&&tt.value?fmt(tf.value)+' → '+fmt(tt.value):'Chưa chọn'):tmv;
  $('kl').textContent=$('v1').textContent=$('v2k').textContent=kn;$('v2').textContent=sc;$('v2').title=sc;$('v3').textContent=tl;$('sum').textContent=NAME+' · '+sc+' · '+tl;
  k.placeholder=kind=='s'?'Gõ để tìm, chọn được nhiều stream (không chọn = tất cả stream)':'Gõ tên application (để trống = mọi application)';
  $('hh').textContent=ai?'Bạn muốn hỏi gì?':'Bạn muốn tìm gì?';$('qt').textContent=ai?'Câu hỏi cho AI':'Nội dung tìm kiếm';
  $('ql').textContent=ai?'Mô tả vấn đề bằng lời thường':'Từ khóa hoặc cú pháp Graylog';q.placeholder=ai?'vd: 1 giờ qua có lỗi gì đáng chú ý không?':'vd: DH000123';
  $('qh').textContent=ai?'AI tự truy vấn log trong phạm vi đã chọn rồi trả lời. Enter để xuống dòng.':'Để trống để xem mọi log trong phạm vi đã chọn. Enter để tìm.';
  $('ex').hidden=$('tip').hidden=!!ai;go.replaceChildren(ai?'Hỏi AI ':'Tìm log ',$('ar').content.cloneNode(true))}
function preset(t){tmv=t;const n=new Date();tt.value=iso(n);tf.value=iso(new Date(n-SECS[t]*1e3));draw()}
k.oninput=()=>{show();draw()};k.onfocus=show;k.onblur=()=>l.replaceChildren();
$('kx').onclick=()=>{k.value='';k.focus();show();draw()};$('all').onclick=()=>{sel=[];draw()};
QA('[data-k]',b=>b.onclick=()=>{kind=b.dataset.k;k.value='';draw();k.focus()});
QA('[data-t]',b=>b.onclick=()=>{if(b.dataset.t=='custom'){tmv='custom';draw();tf.focus()}else preset(b.dataset.t)});
QA('[data-m]',b=>b.onclick=()=>{ai=rtab=+b.dataset.m;draw();q.focus()});QA('[data-r]',b=>b.onclick=()=>{rtab=+b.dataset.r;draw()});
tf.oninput=tt.oninput=()=>{tmv='custom';draw()};
QA('#ex>button',b=>b.onclick=()=>{q.value=(q.value.trim()?q.value.trim()+' AND ':'')+b.textContent;q.focus()});
q.onkeydown=e=>{if(e.key=='Enter'&&!e.isComposing&&(e.metaKey||e.ctrlKey||(!ai&&!e.shiftKey))){e.preventDefault();F.requestSubmit(go)}};
addEventListener('keydown',e=>{if(e.key=='Enter'&&(e.metaKey||e.ctrlKey)&&e.target!=q){e.preventDefault();F.requestSubmit(go)}});
$('pt').onchange=e=>{document.documentElement.classList.add('ld');location=B+'/ask?name='+encodeURIComponent(e.target.value)};
$('og').onclick=()=>{$('og').classList.add('going');fetch(B+'/open',{method:'POST',body:new URLSearchParams({name:NAME})}).finally(()=>$('og').classList.remove('going'))};
hs.oninput=()=>{const w=hs.value.trim().toLowerCase();QA('.rl .h',a=>a.hidden=!a.textContent.toLowerCase().includes(w))};
QA('.rl:empty',d=>d.append(el('div','Chưa có gì.','no')));
F.onsubmit=e=>{draw();let m='';
  if(kind=='s'&&k.value.trim()&&!sel.length)m='Chọn stream trong danh sách, hoặc xoá chữ đang gõ để tìm tất cả stream.';
  else if(kind=='a'&&!/^[A-Za-z0-9._-]*$/.test($('app').value))m='Tên application chỉ gồm chữ, số và dấu . _ -';
  else if(ai&&!q.value.trim())m='Gõ câu hỏi cho AI trước.';
  else if(tmv=='custom'&&(!tf.value||!tt.value||tf.value>=tt.value))m='Chọn đủ Từ và Đến; Từ phải trước Đến.';
  if(m){e.preventDefault();alert(m);return}
  $('tm').value=tmv=='custom'?tf.value+'~'+tt.value:tmv;
  sessionStorage[KEY]=JSON.stringify([k.value,sel,kind,tmv,q.value,tf.value,tt.value,ai])};
{const d=new Date(),o=-d.getTimezoneOffset();$('tz').textContent=Intl.DateTimeFormat().resolvedOptions().timeZone+' · UTC'+(o<0?'−':'+')+Math.abs(o)/60}
const back=()=>{try{const v=JSON.parse(sessionStorage[KEY]);k.value=v[0];sel=Array.isArray(v[1])?v[1]:[];kind=v[2]=='a'?'a':'s';q.value=v[4];ai=rtab=v[7]?1:0;
  if(v[3]=='custom'){tmv='custom';tf.value=v[5];tt.value=v[6]}else if(SECS[v[3]])tmv=v[3]}catch(e){}tmv=='custom'?draw():preset(tmv)};
addEventListener('pageshow',()=>{back();setTimeout(back,0);setTimeout(back,150)});
</script><template id=ar>@iw@</template>"""
    for key, v in {'b': B, 'n': E(name), 'io': ico('out'), 'is': ico('search'), 'ia': ico('spark'), 'ix': ico('x'), 'iw': ico('arrow'),
                   'pts': ''.join('<option%s>%s</option>' % (' selected' if p[0] == name else '', E(p[0])) for p in partners()),
                   'tcs': ''.join('<button type=button data-t="%s">%s</button>' % (x, x) for x in TIMES),
                   'ns': str(len(searches(name))), 'nh': str(len(hist)), 'srch': srch, 'hist': ''.join(hist),
                   'secs': json.dumps(SECS, ensure_ascii=False), 'nj': json.dumps(name), 'bj': json.dumps(B),
                   's': json.dumps(streams, ensure_ascii=False).replace('</', '<\\/')}.items():
        t = t.replace('@%s@' % key, v)
    return CSS + PCSS + ACSS + t


RCSS = """<style>
body{max-width:none;margin:0;padding:10px 14px;height:100vh;box-sizing:border-box;display:flex;flex-direction:column;gap:10px}
[hidden]{display:none!important}.ic{width:1.15em;height:1.15em;vertical-align:-.2em;flex:none}
.hd{border:1px solid #8884;border-radius:12px;background:#8881;padding:10px 12px;display:flex;flex-direction:column;gap:9px}.hd form{margin:0}
.top,.hr2,.hr3{display:flex;align-items:center;gap:10px;min-width:0}.top>.btn{padding:6px 9px;display:inline-flex}.ttl{font-weight:700;font-size:16px;white-space:nowrap}.vr{flex:none;width:1px;height:22px;background:#8886}
.sx{position:relative;display:inline-flex;align-items:center;gap:8px;border:1px solid #8886;border-radius:9px;padding:5px 26px 5px 10px;margin:0;font-size:13.5px;min-height:38px;box-sizing:border-box;cursor:pointer;min-width:0;white-space:nowrap;text-align:left;background:none}.sx:hover{background:#8882;border-color:#5b93ff}
.sx::after{content:"";position:absolute;right:10px;top:50%;width:6px;height:6px;border-right:1.5px solid;border-bottom:1.5px solid;transform:translateY(-70%) rotate(45deg);opacity:.7}
.sx select{-webkit-appearance:none;appearance:none;background:none;border:0;color:inherit;font:inherit;font-weight:600;padding:0;margin:0;width:auto;cursor:pointer;outline:0}
.c1,.c2{flex:0 1 auto}.sx{--c:#8b8b8b;border-color:color-mix(in srgb,var(--c) 45%,transparent);background:color-mix(in srgb,var(--c) 11%,transparent)}.sx:hover{border-color:var(--c);background:color-mix(in srgb,var(--c) 20%,transparent)}.sx>svg,.sx::after,.sx .two small{color:var(--c);opacity:1}.sx.c0{--c:#4c8dff}.sx.c1{--c:#a56bff}.sx.c2{--c:#f0a020}.two{display:flex;flex-direction:column;line-height:1.25;min-width:0}.two small{font-size:11.5px;opacity:.65}.two b{font-weight:600;overflow:hidden;text-overflow:ellipsis}.c2 select{position:absolute;inset:0;width:100%;height:100%;opacity:0}
.pop{position:fixed;z-index:30;background:Canvas;border:1px solid #8886;border-radius:12px;padding:12px;box-shadow:0 14px 44px #000a;width:340px;display:flex;flex-direction:column;gap:10px}.pop label{font-size:13px}#sl{max-height:46vh;overflow:auto;display:flex;flex-direction:column}#sl label{display:flex;gap:8px;padding:6px 4px;font-size:13.5px;cursor:pointer;align-items:center;border-radius:6px}#sl label:hover{background:#8882}#sl input{width:auto;margin:0}.pr2{display:flex;gap:8px;align-items:center}#dash{flex:1;overflow:auto;padding:16px 18px;gap:14px}#dash h3{margin:0;font-size:14px}#dash h3 small{font-weight:400;opacity:.6;margin-left:8px}.dch{display:grid;grid-template-columns:132px 250px minmax(0,1fr);gap:18px;align-items:center}.dn{width:132px}.dn circle{cursor:pointer}.dn text{fill:currentColor;font-size:6.5px;font-weight:700}.dn text.s{font-size:3px;font-weight:400;opacity:.6}.dlg{display:flex;flex-direction:column;gap:2px}.dab{all:unset;display:grid;grid-template-columns:230px minmax(0,1fr) auto;gap:14px;align-items:center;box-sizing:border-box;width:100%;padding:6px 10px;border-radius:8px;cursor:pointer;font-size:13px;border:1px solid transparent}.dab:hover{background:#8882}.dab.on{border-color:#5b93ff;background:#5b93ff1f}.dab b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dab .br{display:flex;height:10px;border-radius:3px;overflow:hidden}.dab u{display:block}.dab span:last-child{font-variant-numeric:tabular-nums}.dab small{opacity:.6;margin-left:6px}.dsb{all:unset;display:flex;gap:10px;align-items:center;box-sizing:border-box;padding:6px 10px;border-radius:8px;cursor:pointer;font-size:13px;border:1px solid transparent}.dsb:hover{background:#8882}.dsb.on{border-color:var(--c);background:color-mix(in srgb,var(--c) 12%,transparent)}.dsb b{color:var(--c);flex:1}.dsb b::before{content:"";display:inline-block;width:9px;height:9px;border-radius:3px;background:var(--c);margin-right:8px}.dsb span{font-variant-numeric:tabular-nums}.dsb span small{opacity:.6;margin-left:6px}.dtl{display:flex;flex-direction:column;gap:4px;min-width:0}.dtl div{display:flex;justify-content:space-between;font-size:11.5px;color:GrayText}.dtl svg{height:104px;width:100%;border-bottom:1px solid #8885}.dsl{float:right;font-size:12.5px;font-weight:400;color:GrayText}.dsl select{width:auto;font-size:12.5px;padding:2px 6px;margin-left:6px}.dsl input{width:84px;font-size:12.5px;padding:2px 6px;margin:0 4px 0 6px}.dt th i{font-style:normal;opacity:.45}.dt th sup{font-size:9px;margin-left:1px}.dsr{all:unset;float:right;cursor:pointer;color:#5b93ff;font-size:12.5px;font-weight:400;margin:3px 16px 0 0}.dsr:hover{text-decoration:underline}.dt{width:100%;border-collapse:collapse;font-size:13px}.dt th{text-align:right;font-size:12px;font-weight:600;color:GrayText;padding:7px 10px;border-bottom:1px solid #8884;cursor:pointer;white-space:nowrap;position:sticky;top:-16px;background:Canvas}.dt th:first-child,.dt td:first-child{text-align:left}.dt th.on{color:#5b93ff}.dt th:first-child{width:100%}.dt td{padding:7px 10px;border-bottom:1px solid #8882;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.dt td:first-child{font:12.5px ui-monospace,Menlo,monospace;white-space:normal;word-break:break-all}.dt tr:hover td{background:#8881}.dt td[data-s]{cursor:pointer}.dt td[data-s]:hover{text-decoration:underline}.dt .z{opacity:.3}.pop.cm{width:auto;padding:5px;gap:0;border-radius:9px}.cm button{all:unset;padding:6px 12px;font-size:13px;border-radius:6px;cursor:pointer;white-space:nowrap}.cm button:hover{background:#3b82f6;color:#fff}.gh{padding:6px 12px;font-size:12px;color:GrayText;background:linear-gradient(#8882,#8882),Canvas;border-bottom:1px solid #8883;position:sticky;top:0;z-index:1}
.sq{flex:1;min-width:160px;position:relative;display:block}.sq .ic{position:absolute;left:12px;top:11px;opacity:.6}.sq input{padding-left:38px;padding-right:40px}.sq input:focus{border-color:#5b93ff;outline:0;box-shadow:0 0 0 2px #2f6fed40}.sq .sb{position:absolute;left:0;top:0;height:100%;width:38px;min-height:0;background:none;border:0;padding:0;margin:0;cursor:pointer;z-index:1}.sq .sb:hover .ic{opacity:1}
.sq kbd{position:absolute;right:9px;top:50%;transform:translateY(-50%);font:12px ui-monospace,Menlo,monospace;border:1px solid #8886;border-radius:5px;padding:1px 6px;opacity:.6;pointer-events:none}
.b,.hd button{display:inline-flex;gap:7px;align-items:center}.hr3{font-size:13.5px}#cnt{white-space:nowrap;opacity:.9}.up{display:inline-flex;gap:6px;align-items:center;opacity:.7;font-size:12.5px;white-space:nowrap}
#ar{width:auto;padding:4px 8px;font-size:13px}#ar.on{background-color:#30a46c33;border-color:#30a46c;color:#3dd68c}
.mdt{border:0;gap:18px}.mdt button{font-size:14px;padding:6px 0;white-space:nowrap}
.fc .on{background:#2f6fed2e;color:#5b93ff;box-shadow:inset 0 0 0 1px #2f6fed;opacity:1;font-weight:600}
@media(max-width:980px){.ttl,.ttl+.vr{display:none}}
.note{font-size:12.5px;opacity:.65;margin:-4px 2px 0}
.g3{flex:1;min-height:0;display:grid;grid-template-columns:var(--lw,290px) 12px minmax(0,1fr)}.g3.fs{grid-template-columns:12px minmax(0,1fr)}.vsp{position:relative;cursor:col-resize;touch-action:none}.g3.fs .vsp{cursor:default}.vsp::after{content:"";position:absolute;left:5px;top:12px;bottom:12px;border-left:2px solid transparent}.vsp:hover::after{border-color:#5b93ff}.vsp button{all:unset;position:absolute;left:-3px;top:50%;margin-top:-24px;width:16px;height:48px;border:1px solid #8886;border-radius:8px;background:Canvas;z-index:2;cursor:pointer;text-align:center;font-size:14px;line-height:46px;color:GrayText;box-sizing:border-box}.vsp button:hover{color:#fff;background:#3b82f6;border-color:#3b82f6}.g3.fs .lp{display:none}
.rc{display:flex;flex-direction:column;min-height:0;min-width:0}.mp{flex:1;min-height:130px}#dp{flex:none;height:44%;min-height:110px;max-height:calc(100% - 150px)}
.spl{flex:none;height:10px;cursor:row-resize;display:flex;align-items:center;justify-content:center;touch-action:none}.spl::after{content:"";width:34px;height:3px;border-top:1px solid #8889;border-bottom:1px solid #8889}.spl:hover::after{border-color:#5b93ff}
.pane{border:1px solid #8884;border-radius:12px;background:#8881;display:flex;flex-direction:column;min-height:0;min-width:0;overflow:hidden}
.ph{padding:10px 12px;border-bottom:1px solid #8883;display:flex;flex-direction:column;gap:8px}.pr{display:flex;gap:8px;align-items:center;flex-wrap:wrap;min-width:0}
.ph h2{margin:0;font-size:17px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:0 1 auto}#mh>.pr:first-child{flex-wrap:nowrap}#mh .b,#mk,#mk .bd{flex:none}#mk{flex-wrap:nowrap}.ph h3{margin:0;font-size:16px}
.sub{margin:0;font-size:12.5px;opacity:.85;gap:3px 16px}.sub .pth{font-family:ui-monospace,Menlo,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}.sub .id{display:inline-flex;gap:5px;align-items:center;white-space:nowrap}.sub .id:hover{text-decoration:underline}.sub svg{width:12px;height:12px}
.fi{position:relative;flex:1;min-width:110px}.fi .ic{position:absolute;left:10px;top:8px;opacity:.6}.fi input{padding:5px 10px 5px 34px;font-size:13.5px}
.tb{padding:8px 12px;border-bottom:1px solid #8883}.tb>b{white-space:nowrap;font-size:14px}
.sc{flex:1;overflow:auto;min-height:0}.pf{padding:6px 12px;border-top:1px solid #8883;font-size:12.5px;display:flex;gap:10px;align-items:center;opacity:.9}.pf span{flex:1}
#tpf{justify-content:center}#tpf span{flex:none;font-variant-numeric:tabular-nums}
#pgr{display:flex;gap:4px;align-items:center}#pgr span{flex:none;opacity:.6}#pgr button{padding:2px 8px;min-width:28px;font-size:12.5px}#pgr .on{background:#2f6fed;border-color:#2f6fed;color:#fff}
.sm{padding:4px 10px;font-size:13px}.fc{display:flex;gap:6px;flex-wrap:wrap}.fc button{padding:4px 10px;font-size:13px}
.pill{padding:2px 10px;border-radius:99px;background:#8882;border:1px solid #8884;font-size:13px;font-weight:600}
.id{font:12.5px ui-monospace,Menlo,monospace;color:#5b93ff;cursor:pointer}
.bd{font-size:11.5px;font-weight:600;padding:2px 8px;border-radius:6px;white-space:nowrap}.bd.ok{background:#30a46c2e;color:#3dd68c}.bd.bad{background:#e5484d2e;color:#ff6369}.bd.warn{background:#f5a5242e;color:#ffc53d}.bd.unk,.bd.inf{background:#8883}.bd.inf{color:#5b93ff;background:#2f6fed26}
.ti,.lr{display:grid;width:100%;box-sizing:border-box;text-align:left;border:0;border-bottom:1px solid #8883;border-radius:0;white-space:normal;font-size:13.5px}
.ti{grid-template-columns:auto minmax(0,1fr) auto;gap:3px 8px;padding:9px 12px;align-items:center}.ti b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}.ti .tm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;opacity:.7;font-variant-numeric:tabular-nums}
.ti>b{grid-column:1/3}.ti>.bd{grid-column:3}.ti>b:last-child{grid-column:1/-1}.tid{grid-column:2/4;justify-self:end;font:11.5px ui-monospace,Menlo,monospace;color:#22b8cf;white-space:nowrap;text-align:left;cursor:copy;display:flex;align-items:center;gap:6px}.tid:hover{text-decoration:underline}.tid svg{width:12px;height:12px;opacity:.7}.ti:hover,.lr:hover{background:#8882}.ti.on,.lr.on{background:#2f6fed26;box-shadow:inset 3px 0 #2f6fed}
.lr{grid-template-columns:88px 70px minmax(0,1fr) var(--aw,132px) 72px;gap:0 8px;padding:6px 12px;align-items:center;font-size:13px}.lr>*{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.lr time{font-variant-numeric:tabular-nums;opacity:.85}.lr .lv{display:flex;gap:6px;align-items:center}.lr i{flex:none;width:8px;height:8px;border-radius:9px;background:#5b93ff}.lr.w i{background:#ffc53d}.lr.e i{background:#ff6369}.lr.hit{background:#f5c5421a}
.lr b{font-weight:500}.lr b small{opacity:.55;font:11.5px ui-monospace,Menlo,monospace}.lr .sv{opacity:.75}.lr .du{text-align:right;font-variant-numeric:tabular-nums;opacity:.85}
.lh .ap{position:relative;padding-left:10px;margin-left:-10px}.rz{position:absolute;left:0;top:-4px;bottom:-4px;width:9px;cursor:col-resize;border-left:2px solid #8887;touch-action:none}.rz:hover{border-color:#5b93ff}
.lh,.lh:hover{font-size:12px;font-weight:600;opacity:.65;padding:5px 12px;background:none;cursor:default}
.lose{display:flex;gap:8px;align-items:center;width:100%;box-sizing:border-box;border:0;border-top:1px solid #8883;border-radius:0;padding:9px 12px;font-size:13px;text-align:left}.lose span{flex:1}.lose.on{background:#2f6fed45}
.emp{padding:20px 14px;opacity:.6;font-size:13.5px}
.dh{padding:6px 12px;border-bottom:1px solid #8883;flex-wrap:nowrap}.dh h3{margin:0;font-size:12.5px;letter-spacing:.06em}.dh span{font-size:13px;white-space:nowrap}
#dp .bdy{padding:10px 12px;overflow:auto;flex:1;min-height:0}#dp h2{font-size:16px;margin:0 0 6px;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.al{display:flex;gap:10px;margin:6px 0;padding:7px 10px;border-radius:8px;font-size:13px;overflow-wrap:anywhere;white-space:pre-wrap;max-height:6em;overflow:auto}.al.e{border:1px solid #e5484d99;background:#e5484d1f}.al.w{border:1px solid #f5a52488;background:#f5a5241f}
.meta{font-size:12.5px;opacity:.75;margin:4px 0;overflow-wrap:anywhere}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 16px;font-size:13px;margin:0 0 10px}.kv>*{padding:6px 0;border-bottom:1px solid #8883}.kv span{opacity:.65}.kv b{font:12.5px ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.tabs{display:flex;gap:16px;border-bottom:1px solid #8883}.tabs button{border:0;border-radius:0;padding:6px 0;opacity:.65;font-size:13.5px}.tabs .on{opacity:1;color:#5b93ff;font-weight:600;box-shadow:inset 0 -2px #2f6fed}
.ph .tabs{border:0;margin-bottom:-10px}.tbr{border-bottom:1px solid #8883;margin:4px 0 8px;gap:6px;flex-wrap:nowrap}.tbr .tabs{border:0;gap:14px}.tbr .b{flex:none}
.code{margin:0;padding:8px 10px 8px 0;font:12.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere;counter-reset:l;border:1px solid #8884;border-radius:8px}
.fo{position:absolute;left:3em;width:1.1em;text-align:center;cursor:pointer;opacity:.55;text-decoration:none}.fo:hover{opacity:1}.fo::before{content:"▾"}.cl>.fo::before{content:"▸"}.cl::after{content:" … ";opacity:.55}
.code>div{counter-increment:l;padding-left:4.3em;position:relative;min-height:1.5em}.code>div::before{content:counter(l);position:absolute;left:0;width:2.8em;text-align:right;opacity:.4;-webkit-user-select:none;user-select:none}
.jk{color:#79b8ff}.js{color:#f6a56b}.jn{color:#b392f0}.jb{color:#ff7b72}
.pl{border:1px solid #8884;border-radius:8px;margin-bottom:10px}.pl>div:first-child{padding:6px 10px;font-size:12.5px;font-weight:600;border-bottom:1px solid #8883}.pl .code{border:0}
.ft{font-size:12.5px;opacity:.8;display:flex;gap:12px;align-items:center;padding:0 4px}.ft a{cursor:pointer;color:#5b93ff;font-weight:600}
.top>.btn,.sm:not(.p),.nv button,.da button:not(.p),.fc button,.lose{background:#2f6fed24;border-color:#2f6fed80;color:#5b93ff;font-weight:600}
.top>.btn:hover,.sm:not(.p):hover,.nv button:hover,.da button:not(.p):hover,.lose:hover{background:#2f6fed45}
.fc [data-v=e]{background:#e5484d24;border-color:#e5484d80;color:#ff6369}.fc [data-v=w]{background:#f5a52424;border-color:#f5a52480;color:#ffc53d}
.fc [data-v=e].on{background:#e5484d55;color:#ff6369;box-shadow:inset 0 0 0 1px #e5484d}.fc [data-v=w].on{background:#f5a52450;color:#ffc53d;box-shadow:inset 0 0 0 1px #f5a524}
#dx{background:#e5484d24;border-color:#e5484d80;color:#ff6369}
mark{background:#f5c54266;color:inherit;border-radius:3px}
@media(max-width:1000px){.tb>b{display:none}}
@media(max-width:760px){.g3{grid-template-columns:var(--lw,230px) 12px minmax(0,1fr)}}
@media(prefers-color-scheme:light){.bd.ok{color:#18794e}.bd.bad{color:#cd2b31}.bd.warn{color:#ad5700}.jk{color:#0550ae}.js{color:#9a3412}.jn{color:#6f42c1}.jb{color:#cf222e}}
</style>"""

RJS = r"""<script>
const $=i=>document.getElementById(i),IC=n=>$('ic-'+n).innerHTML;
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const QR=/^[\w.-]{3,}$/.test(D.q)?D.q:'',hl=s=>{s=esc(s);return QR?s.split(QR).join('<mark>'+QR+'</mark>'):s};
const short=id=>id.length>16?id.slice(0,8)+'…'+id.slice(-4):id;
const KD={ok:['ok','✓ Thành công'],bad:['bad','✕ Thất bại'],unk:['unk','? Chưa rõ']},LV={i:['INFO','inf'],w:['WARN','warn'],e:['ERROR','bad']};
const LOOSE={id:'',name:'Log không có trace ID',path:'Xem riêng, không tự gán vào trace',full:1};
const ALL={id:'',name:'Tất cả log',path:'Mọi log trong kết quả, không gom theo trace',full:1};
let MD=0;
function prep(){D.T.forEach(t=>{t.nb=t.logs.filter(x=>x.lv=='e').length;t.nw=t.logs.filter(x=>x.lv=='w').length;t.logs.forEach(x=>x.tid=t.id)});LOOSE.logs=D.L;ALL.logs=[].concat(...D.T.map(t=>t.logs),D.L);MD=new Set(ALL.logs.map(x=>x.d)).size>1}
prep();
let pg=0;const PS=50;let cur=null,li=-1,tf='all',lf='all',tdesc=1,lasc=0,tab='',DSH=0,grp=localStorage.glgrp||'';const GK={sv:'Application',lv:'Mức log'},gk=x=>grp=='lv'?LV[x.lv][0]:x[grp]||'(không có)';
async function cp(s,b){try{await navigator.clipboard.writeText(s)}catch(x){const a=document.createElement('textarea');a.value=s;document.body.append(a);a.select();document.execCommand('copy');a.remove()}
  if(b){const o=b.innerHTML;b.textContent='✓ đã copy';setTimeout(()=>b.innerHTML=o,1200)}}
function post(q,act){af.q.value=q;af.act.value=act;af.requestSubmit()}
function chips(box,arr,val,fn){box.innerHTML=arr.map(([v,t])=>`<button type=button class="${v==val?'on':''}" data-v="${v}">${t}</button>`).join('');box.onclick=e=>{const b=e.target.closest('button');if(b)fn(b.dataset.v)}}
let tpg=0;const TPS=20;
// chuỗi JSON lồng trong JSON (vd "payload":"{\"clazz\":…}") -> bung ra cho dễ đọc
const dec=v=>{if(typeof v=='string'&&/^\s*[{[]/.test(v)){try{return dec(JSON.parse(v))}catch(e){return v}}if(v&&typeof v=='object')for(const k in v)v[k]=dec(v[k]);return v};
const dj=s=>{try{return JSON.stringify(dec(JSON.parse(s)),null,2)}catch(e){return s}};
const svs=s=>s.replace(/^erp-|-service$/g,'');
const bdg=t=>t.kind=='bad'?'<span class="bd bad">Thất bại</span>':t.nb?`<span class="bd bad">${t.nb} lỗi</span>`:t.nw?`<span class="bd warn">${t.nw} cảnh báo</span>`:`<span class="bd ${KD[t.kind][0]}">${KD[t.kind][1].slice(2)}</span>`;
function code(s){if(!s)return '<div class=emp>(trống)</div>';let h='',p=0;
  if(/^\s*[{[]/.test(s)&&s.length<3e5)s.replace(/("(?:\\.|[^"\\])*")(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,(m,str,col,i)=>{h+=hl(s.slice(p,i))+'<span class='+(str?col?'jk':'js':/^[tfn]/.test(m)?'jb':'jn')+'>'+hl(str||m)+'</span>'+(col||'');p=i+m.length;return m});
  h+=hl(s.slice(p));const R=s.split('\n');return '<pre class=code>'+h.split('\n').map((l,i)=>{const r=R[i]||'';return '<div data-d='+r.search(/\S|$/)+'>'+(/[{[]\s*$/.test(r)&&R.length>1?'<u class=fo title="Đóng / mở"></u>':'')+l+'</div>'}).join('')+'</pre>'}
// đóng/mở object, mảng JSON: ẩn các dòng thụt sâu hơn dòng đang đóng
function refold(pre){let h=-1;for(const d of pre.children){const n=+d.dataset.d;if(h>=0&&n>h){d.hidden=true;continue}d.hidden=false;h=d.classList.contains('cl')?n:-1}}
document.addEventListener('click',e=>{const f=e.target.closest('.fo');if(!f)return;f.parentNode.classList.toggle('cl');refold(f.closest('pre'))});
function rt(f){const w=$('tq').value.trim().toLowerCase();
  let a=D.T.map((t,i)=>[t,i]).filter(([t])=>(tf=='all'||(tf=='e'?t.nb||t.kind=='bad':t.nw))&&(t.id+' '+t.name+' '+t.path).toLowerCase().includes(w));if(!tdesc)a.reverse();
  const np=Math.ceil(a.length/TPS)||1;if(f===0)tpg=0;if(f===1){const k=a.findIndex(p=>p[0]==cur);if(k>=0)tpg=Math.floor(k/TPS)}tpg=Math.min(tpg,np-1);const s=a.slice(tpg*TPS,tpg*TPS+TPS);
  $('tc').textContent=a.length;$('ts').innerHTML=(tdesc?'Mới nhất ↓':'Cũ nhất ↑');
  chips($('tfc'),[['all','Tất cả'],['e','Có lỗi'],['w','Cảnh báo']],tf,v=>{tf=v;rt(0)});
  $('tl').innerHTML=s.map(([t,i])=>`<button type=button class="ti${cur==t?' on':''}" data-i=${i}><b title="${esc(t.name)}">${hl(t.name)}</b>${bdg(t)}<small class=tm>${MD?t.d+' ':''}${t.t} · ${t.logs.length} log${t.dur?' · '+esc(t.dur):''}</small>${t.id?`<small class=tid data-id="${esc(t.id)}" title="${esc(t.id)} — bấm để copy">${hl(short(t.id))} ${IC('copy')}</small>`:''}</button>`).join('')||'<div class=emp>Không có trace nào khớp.</div>';
  $('tpf').hidden=np<2;$('tpn').textContent=(a.length?tpg*TPS+1+'–'+(tpg*TPS+s.length):0)+' / '+a.length+' trace';$('tpp').disabled=!tpg;$('tpx').disabled=tpg>=np-1;
  $('lose').hidden=!D.L.length;$('lose').classList.toggle('on',cur==LOOSE);$('ln').textContent=D.L.length;
  document.querySelectorAll('[data-md]').forEach(b=>b.classList.toggle('on',!DSH&&(b.dataset.md=='a')==(cur==ALL)))}
function vis(){const w=$('lq').value.trim().toLowerCase();
  return cur.logs.map((x,i)=>[x,i]).filter(([x])=>(lf=='all'||x.lv==lf)&&(!w||(x.ti+' '+x.sv+' '+x.m+' '+(x.api?JSON.stringify(x.api):'')).toLowerCase().includes(w))).sort((p,q)=>(grp&&gk(p[0]).localeCompare(gk(q[0])))||(p[0].k-q[0].k)*(lasc?1:-1))}
function pick(t,auto){cur=t;li=-1;lf='all';$('lq').value='';
  if(t&&auto){const a=vis(),h=a.find(p=>p[0].hit)||a.find(p=>p[0].lv=='e')||a.find(p=>p[0].lv=='w');if(h)li=h[1]}
  rt(1);rh();rl(1);rd()}
function rh(){const t=cur;$('mh').hidden=!t;if(!t)return;const nb=t.logs.filter(x=>x.lv=='e').length,nw=t.logs.filter(x=>x.lv=='w').length,ns=new Set(t.logs.map(x=>x.sv).filter(Boolean)).size;
  $('mn').innerHTML=hl(t.name);$('mn').title=t.name;
  $('mk').innerHTML=(t.kind?`<span class="bd ${KD[t.kind][0]}">Kết quả cuối: ${KD[t.kind][1].slice(2)}</span>`:'')+(nb?`<span class="bd bad">${nb} lỗi</span>`:'')+(nw?`<span class="bd warn">${nw} cảnh báo</span>`:'');
  $('mp').innerHTML=`<span class=pth title="${esc(t.path)}">${hl(t.path)}</span>`+(t.id?`<span class=id id=cid title="Bấm để copy trace ID">Trace ID: ${hl(t.id)} ${IC('copy')}</span>`:'')+`<span>${t.logs.length} log · ${ns} dịch vụ${t.dur?' · '+esc(t.dur):''}</span>`;
  if(t.id)$('cid').onclick=()=>cp(t.id,$('cid'));$('ma').hidden=!t.id}
function rl(f){if(!cur){$('ll').innerHTML='<div class=emp>Không có log nào khớp. Thử nới khoảng thời gian hoặc đổi từ khoá.</div>';$('mf').hidden=true;return}
  const A=vis(),n=c=>cur.logs.filter(x=>x.lv==c).length,np=Math.ceil(A.length/PS)||1;
  if(f===0)pg=0;if(f===1&&li>=0)pg=Math.max(0,Math.floor(A.findIndex(p=>p[1]==li)/PS));pg=Math.min(pg,np-1);const a=A.slice(pg*PS,pg*PS+PS);
  chips($('lfc'),[['all','Tất cả '+cur.logs.length],['e','Lỗi '+n('e')],['w','Cảnh báo '+n('w')]],lf,v=>{lf=v;rl(0)});$('ls').innerHTML=IC('sort')+(lasc?' Cũ → mới':' Mới → cũ');
  $('lq').placeholder='Tìm trong '+cur.logs.length+' log…';
  const gc={};if(grp)A.forEach(p=>gc[gk(p[0])]=(gc[gk(p[0])]||0)+1);
  $('ll').innerHTML=a.map(([x,i],k)=>(grp&&(!k||gk(a[k-1][0])!=gk(x))?`<div class=gh>${GK[grp]}: <b>${esc(gk(x))}</b> · ${gc[gk(x)]} log</div>`:'')+`<button type=button class="lr ${x.lv}${i==li?' on':''}${x.hit?' hit':''}" data-i=${i}><time>${x.t}</time><span class=lv><i></i><span class="bd ${LV[x.lv][1]}">${LV[x.lv][0]}</span></span><b title="${esc(x.ti)}">${x.api&&x.api.Step?'#'+esc(x.api.Step)+' ':''}${hl(x.ti)}${cur==ALL&&x.tid?' <small>'+short(x.tid)+'</small>':''}</b><span class=sv title="${esc(x.sv)}">${hl(x.sv)}</span><span class=du>${esc(x.api&&x.api.Duration||'')}</span></button>`).join('')||'<div class=emp>Không có log nào khớp bộ lọc.</div>';
  const ps=[...new Set([0,pg-1,pg,pg+1,np-1])].filter(i=>i>=0&&i<np).sort((x,y)=>x-y);
  $('pgr').hidden=np<2;$('pgr').innerHTML=`<button type=button class=sm data-p=${pg-1} ${pg?'':'disabled'}>‹</button>`+ps.map((i,k)=>(k&&i-ps[k-1]>1?'<span>…</span>':'')+`<button type=button class="sm${i==pg?' on':''}" data-p=${i}>${i+1}</button>`).join('')+`<button type=button class=sm data-p=${pg+1} ${pg<np-1?'':'disabled'}>›</button>`;
  $('mf').hidden=false;$('mfn').textContent='Hiển thị '+(A.length?pg*PS+1+'–'+(pg*PS+a.length):0)+' / '+A.length+' log'+(A.length<cur.logs.length?' (lọc từ '+cur.logs.length+')':'')+(cur.full?'':' — mới chỉ có các bước khớp từ khoá');$('more').hidden=!!cur.full}
function rd(){const x=cur&&cur.logs[li];$('dp').hidden=$('spl').hidden=!x;if(!x)return;const a=vis(),p=a.findIndex(q=>q[1]==li),A=x.api;
  const raw=A?Object.entries(A).map(([k,v])=>k+': '+v).join('\n'):x.m,j=A?'':dj(x.m);
  const tabs=[['Tổng quan',null]].concat(A?[['Request',dj(A['Request Body']||'')],['Response',dj(A.Response||'')],['Headers',A.Headers||'']]:[[j!=x.m?'JSON':'Nội dung',j]],A||j!=x.m?[['Raw',raw]]:[]);
  const tn=(tabs.find(t=>t[0]==tab)||tabs[A?2:1])[0],tv=tabs.find(t=>t[0]==tn)[1],whole=tv==null||tn=='Raw';
  const kv=[['Service',x.sv],['Trace ID',x.tid],['Thời gian',x.d+' '+x.t]].concat(A?[['Step',A.Step],['URL',A.URL],['Status',A.Status],['Duration',A.Duration]]:[]).filter(r=>r[1]);
  const warn=x.lv!='i'?(A?'Status: '+(A.Status||'?')+(A.Response?'\n'+A.Response.split('\n').slice(0,6).join('\n').slice(0,300):''):(x.ex||x.m.split('\n')[0]).slice(0,300)):'';
  $('dpn').textContent='Log '+(p+1)+' / '+a.length;$('dpv').disabled=p<=0;$('dnx').disabled=p<0||p>=a.length-1;
  $('dpv').onclick=()=>{const n=a[p-1];if(n)sel(n[1])};$('dnx').onclick=()=>{const n=a[p+1];if(n)sel(n[1])};
  $('db').innerHTML=`<h2>${hl(x.ti)}</h2>${warn?`<div class="al ${x.lv}">${x.lv=='e'?'✕':'⚠'} <span>${hl(warn)}</span></div>`:''}
<div class=meta>${hl([x.d+' '+x.t,x.sv,A&&(A.Step?'#'+A.Step+' ':'')+A.URL].filter(Boolean).join('  ·  '))}</div>
<div class="pr tbr"><div class=tabs>${tabs.map(t=>`<button type=button data-tab="${t[0]}" class="${t[0]==tn?'on':''}">${t[0]}</button>`).join('')}</div><span style="flex:1"></span><button type=button class="sm b" id=dc>${IC('copy')} Copy</button><button type=button class="p sm b" id=da>${IC('spark')} Phân tích</button></div>
${tv==null?`<div class=kv>${kv.map(([k,v])=>`<span>${k}</span><b${k=='Trace ID'?' class=id data-cp title="Bấm để copy"':''}>${hl(v)}</b>`).join('')}</div>${x.ex?'<div class=pl><div>exceptionMessage</div>'+code(x.ex)+'</div>':''}`:code(tv)}
${!A&&!whole&&j!=x.m?'<p class=note>Payload đã giải mã · bản gốc trong tab Raw</p>':''}`;
  $('db').onclick=e=>{const b=e.target.closest('[data-tab],[data-cp]');if(!b)return;if(b.dataset.tab){tab=b.dataset.tab;rd()}else cp(x.tid)};
  $('dc').onclick=()=>cp(whole?raw:tv,$('dc'));
  $('da').onclick=()=>post(x.tid?'Trong trace '+x.tid+', giải thích log lúc '+x.t+' ('+x.ti.slice(0,120)+'): ý nghĩa, nguyên nhân và cách xử lý nếu là lỗi.':'Giải thích log này: ý nghĩa, nguyên nhân và cách xử lý nếu là lỗi.\n'+x.m.slice(0,1500),'ai')}
function sel(i){li=i;rl(1);rd();const e=$('ll').querySelector('.on');if(e)e.scrollIntoView({block:'nearest'})}
$('tl').onclick=e=>{const c=e.target.closest('.tid');if(c)return cp(c.dataset.id,c);const b=e.target.closest('.ti');if(b)pick(D.T[b.dataset.i],1)};$('ll').onclick=e=>{const b=e.target.closest('.lr');if(b)sel(+b.dataset.i)};
$('tq').oninput=()=>rt(0);$('lq').oninput=()=>rl(0);$('ts').onclick=()=>{tdesc=!tdesc;rt(0)};$('ls').onclick=()=>{lasc=!lasc;rl(0)};
$('pgr').onclick=e=>{const b=e.target.closest('button');if(b&&!b.disabled){pg=+b.dataset.p;rl();$('ll').scrollTop=0}};
$('tpp').onclick=()=>{tpg--;rt();$('tl').scrollTop=0};$('tpx').onclick=()=>{tpg++;rt();$('tl').scrollTop=0};
$('lose').onclick=()=>pick(LOOSE,1);$('dx').onclick=()=>{li=-1;rl();rd()};const tfs=v=>{const c=$('g3').classList.toggle('fs',v);localStorage.glfs=c?1:'';$('vtg').textContent=c?'›':'‹';$('vtg').title=c?'Mở danh sách trace':'Đóng danh sách trace'};tfs(!!localStorage.glfs);$('fs').onclick=$('vtg').onclick=()=>tfs();
if(+localStorage.gllw)$('g3').style.setProperty('--lw',localStorage.gllw+'px');
$('vsp').onpointerdown=e=>{if(e.target.id=='vtg'||$('g3').classList.contains('fs'))return;e.preventDefault();const x0=e.clientX,w0=document.querySelector('.lp').offsetWidth,mv=v=>{const w=Math.round(Math.max(180,Math.min(innerWidth-360,w0+v.clientX-x0)));$('g3').style.setProperty('--lw',w+'px');localStorage.gllw=w},up=()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up)};addEventListener('pointermove',mv);addEventListener('pointerup',up)};
if($('nar'))$('nar').onclick=()=>openp($('tpop'),$('stm'));
// kéo thanh ngang để đổi chiều cao phần chi tiết; nhớ lại cho lần sau
if(+localStorage.gldh)$('dp').style.height=localStorage.gldh+'px';
// kéo mép trái tiêu đề cột Application để đổi độ rộng cột
if(+localStorage.glaw)$('g3').style.setProperty('--aw',localStorage.glaw+'px');
$('rz').onpointerdown=e=>{e.preventDefault();const x0=e.clientX,w0=$('rz').parentNode.offsetWidth-10,mv=v=>{const w=Math.round(Math.max(60,Math.min(420,w0+x0-v.clientX)));$('g3').style.setProperty('--aw',w+'px');localStorage.glaw=w},up=()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up)};addEventListener('pointermove',mv);addEventListener('pointerup',up)};
$('spl').onpointerdown=e=>{e.preventDefault();const mv=v=>{const r=$('rc').getBoundingClientRect(),h=Math.round(Math.max(110,Math.min(r.height-150,r.bottom-v.clientY)));$('dp').style.height=h+'px';localStorage.gldh=h},up=()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up)};addEventListener('pointermove',mv);addEventListener('pointerup',up)};
document.querySelectorAll('[data-md]').forEach(b=>b.onclick=()=>pick(b.dataset.md=='a'?ALL:D.T[0]||(D.L.length?LOOSE:null),1));
$('ma').onclick=()=>post('Tổng quan trace '+cur.id+': đi qua những bước nào, kết quả, có lỗi gì không?','ai');$('more').onclick=()=>post(cur.id,'search');
addEventListener('keydown',e=>{if(/INPUT|TEXTAREA/.test(e.target.tagName)||!cur)return;const d={ArrowDown:1,ArrowUp:-1}[e.key];
  if(e.key=='Escape'&&li>=0)$('dx').onclick();else if(d){e.preventDefault();const a=vis(),p=a.findIndex(q=>q[1]==li),n=a[p<0?0:p+d];if(n)sel(n[1])}});
pick(D.T[0]||(D.L.length?LOOSE:null),1);
// làm mới tại chỗ: tải lại dữ liệu, giữ trace/log/bộ lọc đang xem
let busy=0,art;
async function reload(){if(busy)return;busy=1;if(DSH)dash();$('rb').classList.add('going');try{
  const b=new URLSearchParams([...new FormData(af)].filter(x=>x[0]!='q'&&x[0]!='act'));b.set('q',D.q);b.set('act','search');b.set('auto','1');
  const m=(await(await fetch(af.action,{method:'POST',body:b})).text()).match(/<script>const D=(.*?)<\/script>/s);if(!m)throw 0;
  const N=JSON.parse(m[1]),s=cur&&cur.logs[li],old=cur;D.T=N.T;D.L=N.L;prep();
  cur=old==ALL?ALL:old==LOOSE&&D.L.length?LOOSE:old&&D.T.find(t=>t.id==old.id)||D.T[0]||(D.L.length?LOOSE:null);
  li=s&&cur?cur.logs.findIndex(x=>x.k==s.k&&x.ti==s.ti&&x.tid==s.tid):-1;rt();rh();rl();rd();
  $('cnt').textContent=D.T.length+' trace · '+ALL.logs.length+' log đã tải';trng();
}catch(e){$('upd').textContent='Làm mới lỗi '+new Date().toTimeString().slice(0,8)}busy=0;$('rb').classList.remove('going')}
// ponytail: chờ xong lượt trước rồi mới hẹn lượt sau, nên Graylog chậm thì tự giãn ra chứ không chồng truy vấn
function auto(){clearTimeout(art);const n=+$('ar').value;$('ar').classList.toggle('on',n>0);if(n)art=setTimeout(async()=>{if(!document.hidden)await reload();auto()},n*1000)}
// đổi phạm vi ngay trên thanh: đối tác / stream / thời gian -> tìm lại với cùng từ khoá
function rescope(o){for(const k in o)af.elements[k].value=o[k];post(D.q,'search')}
function openp(p,at){p.hidden=false;const r=at.getBoundingClientRect();p.style.left=Math.max(8,Math.min(r.left,innerWidth-p.offsetWidth-10))+'px';p.style.top=r.bottom+8+'px'}
// ô thời gian 2 dòng: tên khoảng + giờ cụ thể (tính lại mỗi lần làm mới)
function trng(){const f=d=>('0'+d.getDate()).slice(-2)+'/'+('0'+(d.getMonth()+1)).slice(-2),h=d=>d.toTimeString().slice(0,5),m=SC.tm.split('~'),b=m[1]?new Date(m[1]):new Date(),a=m[1]?new Date(m[0]):new Date(b-SC.secs*1000),z=-b.getTimezoneOffset()/60;
  $('tml').textContent=m[1]?'Tuỳ chọn':SC.tm+' gần nhất';$('tmr').textContent=f(a)+' '+h(a)+'–'+(f(a)==f(b)?'':f(b)+' ')+h(b)+' · UTC'+(z<0?'':'+')+z;$('upd').textContent='Cập nhật '+new Date().toTimeString().slice(0,8)}
trng();
$('sp').onchange=()=>rescope({name:$('sp').value,sid:'',app:''});
$('stm').onchange=()=>{const v=$('stm').value;if(v=='?'){$('stm').value=SC.tm;openp($('tpop'),$('stm'))}else rescope({tm:v})};
{const m=SC.tm.split('~');if(m[1]){$('tf').value=m[0];$('tt').value=m[1]}}
$('tok').onclick=()=>{const a=$('tf').value,b=$('tt').value;if(!a||!b||a>=b)return alert('Chọn "Từ" trước "Đến".');rescope({tm:a+'~'+b})};
$('sl').innerHTML=[...SC.streams].sort((a,b)=>SC.sid.includes(b[1])-SC.sid.includes(a[1])).map(([t,i])=>`<label><input type=checkbox value="${i}"${SC.sid.includes(i)?' checked':''}> ${esc(t)}</label>`).join('');
document.querySelectorAll('.c1').forEach(b=>b.onclick=()=>{openp($('spop'),b);$('sf').focus()});
$('sf').oninput=()=>{const w=$('sf').value.trim().toLowerCase();$('sl').querySelectorAll('label').forEach(l=>l.hidden=!l.textContent.toLowerCase().includes(w))};
$('sno').onclick=()=>$('sl').querySelectorAll(':checked').forEach(x=>x.checked=false);
$('sok').onclick=()=>{const v=[...$('sl').querySelectorAll(':checked')].map(x=>x.value);if(v.length>20)return alert('Tối đa 20 stream.');rescope({sid:v.join(),app:''})};
addEventListener('mousedown',e=>{for(const p of[$('spop'),$('tpop')])if(!p.hidden&&!p.contains(e.target)&&!e.target.closest('.bc'))p.hidden=true});
{const m=document.createElement('div');m.className='pop cm';m.hidden=true;document.body.append(m);
document.querySelector('.mp').addEventListener('contextmenu',e=>{if(!cur||!e.target.closest('.lr,.gh,#ll'))return;e.preventDefault();
  const r=e.target.closest('#ll .lr'),x=r&&cur.logs[r.dataset.i];
  m.innerHTML=Object.keys(GK).map(k=>`<button type=button data-g=${k}>${grp==k?'✓ ':''}Nhóm theo ${GK[k]}</button>`).join('')+(grp?'<button type=button data-g="">Bỏ nhóm</button>':'')+(x&&x.sv?`<button type=button data-f="${esc(x.sv)}">Chỉ xem ${esc(x.sv)}</button>`:'')+($('lq').value?'<button type=button data-f="">Bỏ lọc</button>':'');
  m.hidden=false;m.style.left=Math.min(e.clientX,innerWidth-m.offsetWidth-8)+'px';m.style.top=Math.min(e.clientY,innerHeight-m.offsetHeight-8)+'px'});
m.onclick=e=>{const b=e.target.closest('button');if(!b)return;if('g' in b.dataset)localStorage.glgrp=grp=b.dataset.g;else $('lq').value=b.dataset.f;m.hidden=true;rl(0)};
addEventListener('mousedown',e=>{if(!m.contains(e.target))m.hidden=true});}
// Dashboard: số do Graylog đếm (không dính giới hạn 500 bản ghi); bấm status -> api có status đó; bấm số -> mở log tương ứng
let DG=null,dst='',dso=[],dap='',DAP=[];const DF=()=>DG&&DG.f||{st:'api_status',api:'url_path',app:'application'},sq=s=>(DG.sq||{})[s]||DF().st+':'+s,dq=()=>[D.q&&'('+D.q+')',dap&&DF().app+':"'+dap.replace(/(["\\])/g,'\\$1')+'"'].filter(Boolean).join(' AND ');const SCOL={SUCCESS:'#2fb170',BUSINESS_ERROR:'#f0a020',ERROR:'#ef5350'},SLW=[200,500,1000,2000,3000,5000,10000],fms=v=>v%1000?v+' ms':v/1000+' giây';let dsl=+localStorage.glslow||1000,dsc=!SLW.includes(dsl);
async function dash(){if(!DG)$('dash').innerHTML='<div class=emp>Đang đếm…</div>';
  try{const b=new URLSearchParams([...new FormData(af)].filter(x=>x[0]!='q'&&x[0]!='act'));b.set('q',dq());b.set('slow',dsl);
    DG=await(await fetch(af.action.replace(/ask$/,'agg'),{method:'POST',body:b})).json();if(!dap)DAP=DG.app;rdash()}
  catch(e){$('dash').innerHTML='<div class=emp>Không đếm được. Kiểm tra từ khoá đang tìm (phải là cú pháp Graylog hợp lệ) hoặc kết nối tới server.</div>'}}
function rdash(){if(dst&&!DG.st.some(x=>x[0]==dst))dst='';sessionStorage.gldst=JSON.stringify({dst,dso});const tot=DG.st.reduce((s,x)=>s+x[1],0),slow=Object.fromEntries(DG.slow),last=Object.fromEntries(DG.last),A={},sl=fms(dsl);
  DG.api.forEach(([p,s,n])=>{const a=A[p]=A[p]||{p,n:0,slow:slow[p]||0,last:Math.floor((last[p]||0)/1000)*1000};a[s]=n;a.n+=n});
  Object.values(A).forEach(a=>a.pe=((a.BUSINESS_ERROR||0)+(a.ERROR||0))/a.n*100);
  // sắp xếp nhiều cột: mỗi lần bấm là sắp lại trên bảng đã sắp trước đó (số = thứ tự bấm), nên cột bấm sau cùng quyết định, các cột trước giữ thứ tự khi bằng nhau
  const ks=dso.length?dso:[[dst||'n',1]],rows=Object.values(A).filter(a=>!dst||a[dst]).sort((x,y)=>{for(const[k,d]of[...ks].reverse()){const c=(k=='p'?x.p.localeCompare(y.p):(y[k]||0)-(x[k]||0))*d;if(c)return c}return 0}),col=s=>SCOL[s]||'#8b8b8b',
    th=(c,l)=>{const i=ks.findIndex(x=>x[0]==c);return `<th data-o=${c}${i<0?'':' class=on'}>${l} ${i<0?'<i>↕</i>':(ks[i][1]>0?'↓':'↑')+(ks.length>1?'<sup>'+(i+1)+'</sup>':'')}</th>`},td=(a,c,s)=>a[c]?`<td data-s="${s}">${a[c]}</td>`:'<td class=z>0</td>';
  // donut: chu vi 100 nên phần trăm chính là độ dài nét
  let off=25;const donut=DG.st.map(([s,n])=>{const p=n/tot*100,c=`<circle data-st="${esc(s)}" r=15.915 cx=21 cy=21 fill=none stroke="${col(s)}" stroke-width=${dst==s?7:5} stroke-dasharray="${p} ${100-p}" stroke-dashoffset=${off} opacity=${!dst||dst==s?1:.3}><title>${esc(s)}: ${n} (${p.toFixed(1)}%)</title></circle>`;off-=p;return c}).join('');
  // cột theo thời gian: chồng các status; đang chọn một status thì chỉ vẽ status đó để lỗi ít không bị SUCCESS đè
  const T=DG.time.map(([t,v])=>[Date.parse(t),v]),ss=(dst?[dst]:['SUCCESS','BUSINESS_ERROR','ERROR'].concat(DG.st.map(x=>x[0]).filter(s=>!SCOL[s]))),
    step=Math.min(...T.slice(1).map((x,i)=>x[0]-T[i][0]),36e5)||6e4,t0=T.length?T[0][0]:0,nb=T.length?Math.round((T[T.length-1][0]-t0)/step)+1:1,
    hmax=Math.max(1,...T.map(([,v])=>ss.reduce((a,s)=>a+(v[s]||0),0))),tf=t=>{const d=new Date(t);return (MD||nb*step>864e5-1?('0'+d.getDate()).slice(-2)+'/'+('0'+(d.getMonth()+1)).slice(-2)+' ':'')+d.toTimeString().slice(0,5)},
    bars=T.map(([t,v])=>{let y=100;const x=(t-t0)/step;return ss.map(s=>{const h=(v[s]||0)/hmax*100;y-=h;return h?`<rect x=${x+.1} y=${y} width=.8 height=${h} fill="${col(s)}"><title>${tf(t)} · ${esc(s)}: ${v[s]}</title></rect>`:''}).join('')}).join('');
  // nhiều application: mỗi cái một thanh, bấm để xem riêng cả dashboard cho application đó
  const AP={};DAP.forEach(([p,s,n])=>{const a=AP[p]=AP[p]||{p,n:0};a[s]=n;a.n+=n});const aps=Object.values(AP).sort((x,y)=>y.n-x.n),amax=Math.max(1,...aps.map(a=>a.n)),
    aph=aps.length>1?'<h3>Theo application<small>bấm một application để xem riêng biểu đồ và bảng API của nó</small></h3><div class=dlg>'+aps.map(a=>`<button type=button class="dab${dap==a.p?' on':''}" data-ap="${esc(a.p)}"><b>${esc(a.p)}</b><span class=br>${Object.keys(a).filter(s=>s!='p'&&s!='n').sort((x,y)=>(x!='SUCCESS')-(y!='SUCCESS')||(x=='ERROR')-(y=='ERROR')).map(s=>`<u style="width:${a[s]/amax*100}%;background:${col(s)}" title="${esc(s)}: ${a[s]}"></u>`).join('')}</span><span>${a.n}<small>${(a.BUSINESS_ERROR||0)+(a.ERROR||0)} lỗi</small></span></button>`).join('')+'</div>':'';
  $('dash').innerHTML=aph+`<h3>Status${dap?' · '+esc(dap):''}<small>${tot} log API${D.q?' khớp “'+esc(D.q)+'”':''} · bấm một status để xem các API có status đó</small></h3>`+(tot?`<div class=dch><svg class=dn viewBox="0 0 42 42">${donut}<text x=21 y=20.5 text-anchor=middle>${tot}</text><text x=21 y=25.5 text-anchor=middle class=s>log API</text></svg><div class=dlg>`+
    DG.st.map(([s,n])=>`<button type=button class="dsb${dst==s?' on':''}" data-st="${esc(s)}" style="--c:${col(s)}"><b>${esc(s)}</b><span>${n}<small>${(n/tot*100).toFixed(1)}%</small></span></button>`).join('')+
    `</div><div class=dtl><div><span>${dst?esc(dst):'Số log API'} theo thời gian</span><span>cao nhất ${hmax} / cột</span></div><svg viewBox="0 0 ${nb} 100" preserveAspectRatio=none>${bars}</svg><div><span>${T.length?tf(t0):''}</span><span>${T.length?tf(t0+(nb-1)*step):''}</span></div></div></div>`:'<div class=emp>Không có log API nào trong phạm vi này.</div>')+
    `<h3>${dst?'API có '+esc(dst):'Theo API'}<small>${rows.length} API · bấm tên API hoặc một con số để mở log tương ứng</small><label class=dsl>Ngưỡng chậm <select id=dsl>${SLW.map(v=>`<option value=${v}${!dsc&&v==dsl?' selected':''}>≥ ${fms(v)}`).join('')}<option value=0${dsc?' selected':''}>Nhập số…</select>${dsc?`<input id=dsn type=number min=1 max=9999999 value=${dsl}> ms`:''}</label>${dso.length?'<button type=button class=dsr id=dsr>Bỏ sắp xếp</button>':''}</h3><table class=dt><tr>${th('p','API')}${th('n','Số call')}${th('BUSINESS_ERROR','Business error')}${th('ERROR','Error')}${th('pe','% lỗi')}${th('last','Gần nhất')}${th('slow','≥ '+sl)}</tr>`+
    rows.map(a=>`<tr data-p="${esc(a.p)}"><td data-s="${dst?esc(sq(dst)):''}">${esc(a.p)}</td>${td(a,'n','')}${td(a,'BUSINESS_ERROR',esc(sq('BUSINESS_ERROR')))}${td(a,'ERROR',esc(sq('ERROR')))}<td>${a.pe.toFixed(1)}%</td><td>${a.last?tf(a.last)+new Date(a.last).toTimeString().slice(5,8):''}</td>${td(a,'slow',esc(DG.slowq))}</tr>`).join('')+'</table>';
  if($('dsl'))$('dsl').onchange=()=>{const v=+$('dsl').value;dsc=!v;if(v){localStorage.glslow=dsl=v;dash()}else{rdash();$('dsn').select()}};
  if($('dsn'))$('dsn').onchange=()=>{const v=Math.floor(+$('dsn').value);if(v>0&&v<1e7){localStorage.glslow=dsl=v;dash()}}}
function setd(v){DSH=v;sessionStorage.gldsh=v?1:'';$('g3').hidden=v;$('dash').hidden=!v;$('dbt').classList.toggle('on',!!v);if(v){document.querySelectorAll('[data-md]').forEach(b=>b.classList.remove('on'));dash()}}
$('dbt').onclick=()=>setd(1);
// mở log từ Dashboard xong thì có nút quay lại đúng Dashboard lúc nãy (từ khoá, status, application, sắp xếp)
{let k;try{k=JSON.parse(sessionStorage.glrest||'null')}catch(e){}sessionStorage.removeItem('glrest');if(k){dst=k.dst;dso=k.dso;dap=k.dap;setTimeout(()=>setd(1))}
 // đang ở Dashboard mà tìm lại / đổi stream / đổi thời gian thì trang mới vẫn mở Dashboard, giữ status và sắp xếp
 else if(sessionStorage.gldsh){try{const o=JSON.parse(sessionStorage.gldst);dst=o.dst||'';dso=o.dso||[]}catch(e){}setTimeout(()=>setd(1))}
 let b;try{b=JSON.parse(sessionStorage.glback||'null')}catch(e){}if(b&&b.nm==af.name.value&&!k){const x=document.createElement('button');x.type='button';x.className='dsr';x.style.cssText='float:none;margin:0 0 0 14px';x.textContent='← Quay lại Dashboard';
  x.onclick=()=>{sessionStorage.glrest=sessionStorage.glback;sessionStorage.removeItem('glback');post(b.q,'search')};$('dbt').after(x)}}
document.querySelectorAll('[data-md]').forEach(b=>b.addEventListener('click',()=>setd(0)));
$('dash').onclick=e=>{const b=e.target.closest('[data-st]'),h=e.target.closest('th[data-o]'),c=e.target.closest('td[data-s]');
  const ap=e.target.closest('[data-ap]');if(ap){dap=dap==ap.dataset.ap?'':ap.dataset.ap;dst='';dash()}else if(b){dst=dst==b.dataset.st?'':b.dataset.st;dso=[];rdash()}else if(e.target.id=='dsr'){dso=[];rdash()}else if(h){const x=dso.find(x=>x[0]==h.dataset.o);dso=dso.filter(y=>y!=x).concat([[h.dataset.o,x?-x[1]:1]]);rdash()}
  else if(c){const p=c.parentNode.dataset.p;sessionStorage.glback=JSON.stringify({nm:af.name.value,q:D.q,dst,dso,dap});sessionStorage.gldsh='';post([dq(),c.dataset.s,p=='(Empty Value)'?'NOT _exists_:'+DF().api:DF().api+':"'+p.replace(/(["\\])/g,'\\$1')+'"',c.dataset.s?'':'_exists_:'+DF().st].filter(Boolean).join(' AND '),'search')}};
$('rb').onclick=reload;$('ar').value=sessionStorage.ar||0;$('ar').onchange=()=>{sessionStorage.ar=$('ar').value;auto()};auto();
</script>"""


def parse_api(msg):
    # log khuôn "== INFO API ==\nTrace ID: …\nStep: …\nURL: …" -> dict các trường; khuôn khác -> None
    p = re.split(r'^(Trace ID|Step|URL|Description|Headers|Request Body|Duration|Status|Response): ', msg, flags=re.M)
    d = dict(zip(p[1::2], (re.sub(r'\n=+[^\n]*=+\s*$', '', v.strip()).strip() for v in p[2::2])))
    return d if 'Trace ID' in d and 'URL' in d else None


def pretty(v):
    try: return json.dumps(json.loads(v), ensure_ascii=False, indent=2)
    except ValueError: return v


def search_page(name, sid, title, app, tm, q):
    # trace id trần bị Graylog tách theo dấu '-' rồi OR từng mảnh -> khớp nhầm log khác; tự bọc ngoặc kép
    code, out = gl('_search', name, sid, app, rng(tm), re.sub(r'(?<![\w"-])(%s)(?![\w"-])' % UUID, r'"\1"', q))
    scope = (title or ('application ' + app if app else 'Tất cả stream')) + ' · ' + tml(tm)
    head = CSS + """<title>Graylog — %s</title><body class=wide><div class=nav><a class=btn href="%s/ask?name=%s" onclick="if(history.length>1){history.back();return false}">← Quay lại</a><a class=btn id=fw hidden href="javascript:history.forward()">Tới →</a><script>const S=sessionStorage,fn=()=>+S.fwd||0;addEventListener(`pageshow`,()=>{fw.hidden=!(fn()>0||(window.navigation&&navigation.canGoForward))});addEventListener(`click`,e=>{const a=e.target.closest(`a`);if(!a)return;S.fwd=a.id==`fw`?fn()-1:a.getAttribute(`onclick`)?fn()+1:0},true);addEventListener(`submit`,e=>{if(!e.defaultPrevented)S.fwd=0});</script><a class="btn r" href="%s">🏠 Đối tác</a></div>
%s<h2 style="margin-top:10px">%s</h2>""" % (E(name), B, urllib.parse.quote(name), B, ctx(name, scope), E(q or 'Mọi log'))
    try: data = json.loads(out) if not code else None
    except ValueError: data = None
    if data is None:
        if get_streams(name) is None:   # phân biệt lỗi kết nối với lỗi cú pháp: thử một lệnh khác tới cùng server
            return head + '<p class=flash>🔌 Không kết nối được tới Graylog của %s (mạng/VPN, hoặc sai mật khẩu). Từ khoá chưa được kiểm tra.</p>' % E(name)
        tips = [t for t, hit in [('thiếu dấu " đóng', q.count('"') % 2), ('ngoặc ( ) chưa đóng đủ', q.count('(') != q.count(')')),
                                 ('ngoặc [ ] chưa đóng đủ', q.count('[') != q.count(']')), ('sau dấu : chưa có giá trị', re.search(r':\s*[(\[]?\s*($|\)|AND\b|OR\b)', q))] if hit]
        return head + ('<p class=flash>✏️ Kết nối tốt, nhưng Graylog không chạy được từ khoá <code>%s</code>%s.\n'
                       'Cách sửa: tìm nguyên văn thì bọc trong ngoặc kép: <code>"%s"</code> · tìm theo field: <code>field:giá_trị</code> · ghép điều kiện bằng AND / OR viết hoa.</p>' % (
                           E(q), ' — ' + ', '.join(tips) if tips else ' (sai cú pháp, hoặc truy vấn nặng quá 30 giây)', E(q.replace('"', '\\"'))))
    scope_in = ''.join('<input type=hidden name=%s value="%s">' % (k, E(v)) for k, v in [('name', name), ('sid', sid), ('app', app), ('tm', tm)])
    seen, groups = set(), {}   # gộp bản trùng (Graylog lưu mỗi log 2 lần), gom theo trace id; dict giữ thứ tự mới nhất trước
    msgs = list(data.get('messages', []))
    ids = list(dict.fromkeys(a['Trace ID'] for a in (parse_api(str(m.get('message', {}).get('message', ''))) for m in msgs)
                             if a and re.fullmatch(r'[\w-]+', a['Trace ID'])))
    full = set(ids[:75]) if q and q not in ids else set()   # ponytail: 75 trace = 3 truy vấn; quá số đó thì trace chỉ hiện bước khớp
    # Graylog từ chối truy vấn quá ~16 trace id -> lô 12, chạy song song
    for c, o in ThreadPoolExecutor(8).map(lambda i: gl('_search', name, sid, app, rng(tm), ' OR '.join('"%s"' % t for t in ids[i:i + 12])), range(0, len(full), 12)):
        try: msgs += json.loads(o).get('messages', []) if not c else []
        except ValueError: pass
    idset = set(ids)
    for m in msgs:
        m = m.get('message', {})
        msg = str(m.get('message', ''))
        if (m.get('timestamp'), msg) in seen: continue
        seen.add((m.get('timestamp'), msg))
        try: ts = datetime.datetime.fromisoformat(m.get('timestamp', '').replace('Z', '+00:00')).astimezone()
        except ValueError: ts = None
        api, lvn = parse_api(msg), str(m.get('level', ''))
        if api: lv = 'i' if api.get('Status', 'SUCCESS') == 'SUCCESS' else 'e'
        else: lv = 'e' if lvn in ('0', '1', '2', '3') or re.search(r'error|exception|fail', msg, re.I) else 'w' if lvn == '4' else 'i'
        # log lẻ (không theo khuôn API) vẫn có field trace_id -> gom chung vào trace của nó
        # service log dạng JSON (vd order-service) không có field trace_id, id nằm trong message
        gid = (api['Trace ID'] if api else m.get('trace_id') or ''.join(re.findall(r'trace_id[\\":\s]{1,12}(%s)' % UUID, msg)[:1])) or ''
        # service phía sau (vd order-service) tự sinh trace id riêng, id của trace gốc nằm ở header x-requestid -> gom về trace gốc
        x = re.search(r'x-request-?id\W{1,6}(%s)' % UUID, msg, re.I)
        if x: gid = x.group(1)
        elif not gid: gid = next((u for u in re.findall(UUID, msg) if u in idset), '')   # log không có id riêng nhưng nhắc tới một trace đã biết
        if api:
            method, _, url = api['URL'].partition(' ')
            ti = api.get('Description') or method + ' ' + (urllib.parse.urlsplit(url).path or url)
            api = dict((k, pretty(v) if k in ('Request Body', 'Response') else v) for k, v in api.items() if k != 'Trace ID')
        else: ti = msg.split('\n')[0][:200]
        groups.setdefault(gid, []).append({
            'k': ts.timestamp() if ts else 0, 't': ts.strftime('%H:%M:%S.%f')[:-3] if ts else '', 'd': ts.strftime('%d/%m') if ts else '', 'lv': lv,
            'sv': str(m.get('application') or m.get('source') or ''), 'ti': ti, 'api': api, 'm': '' if api else pretty(msg) if msg[:1] == '{' else msg,
            'ex': '\n'.join(str(m[k]) for k in ('exceptionClass', 'exceptionMessage') if m.get(k)),
            'hit': bool(gid in full and q.lower() in msg.lower())})
    T, L = [], []
    for gid, logs in groups.items():
        logs.sort(key=lambda x: x['k'])
        apis = [x for x in logs if x['api']]
        if not gid: L += logs; continue
        if not apis:   # trace chỉ có log lẻ (service không ghi theo khuôn API, vd order-service) -> vẫn là một trace
            T.append({'id': gid, 't': logs[0]['t'][:8], 'd': logs[0]['d'], 'name': logs[0]['sv'] or 'Trace', 'path': logs[-1]['ti'][:120], 'dur': '',
                      'kind': 'bad' if any(x['lv'] == 'e' for x in logs) else 'unk', 'full': not q or q == gid or gid in full, 'logs': logs}); continue
        last = max(apis, key=lambda x: (int(x['api']['Step']) if x['api'].get('Step', '').isdigit() else 0, x['k']))   # bước số lớn nhất = API đầu vào -> kết quả cuối của trace
        method, _, url = last['api']['URL'].partition(' ')
        T.append({'id': gid, 't': logs[0]['t'][:8], 'd': logs[0]['d'], 'name': last['api'].get('Description') or urllib.parse.urlsplit(url).path or url,
                  'path': method + ' ' + (urllib.parse.urlsplit(url).path or url), 'dur': last['api'].get('Duration', ''),
                  'kind': 'bad' if last['lv'] == 'e' else 'ok' if last['api'].get('Status') else 'unk', 'full': not q or q == gid or gid in full, 'logs': logs})
    L.sort(key=lambda x: x['k'])
    total, notes = data.get('total_results', 0), []
    if total > len(data.get('messages', [])): notes.append('Đã tải %s / %s bản ghi mới nhất (đã gộp bản trùng) trong khoảng thời gian đã chọn.' % tuple('{:,}'.format(n).replace(',', '.') for n in (len(data['messages']), total)))
    if len(ids) > len(full) and full: notes.append('%d trace cuối chỉ có các bước khớp từ khoá.' % (len(ids) - len(full)))
    dq = E(q or 'Tóm tắt các log trong phạm vi này: đang xử lý nghiệp vụ gì, có lỗi hay điểm bất thường nào đáng chú ý không?')
    return CSS + RCSS + """<title>Graylog — %(n)s</title><div class=hd><div class=top><a class=btn href="%(b)s/ask?name=%(nq)s" onclick="if(history.length>1){history.back();return false}" title="Quay lại form tìm">%(ib)s</a><a class=btn id=fw hidden href="javascript:history.forward()">Tới →</a><script>{const S=sessionStorage,fn=()=>+S.fwd||0;addEventListener(`pageshow`,()=>{fw.hidden=!(fn()>0||(window.navigation&&navigation.canGoForward))});addEventListener(`click`,e=>{const a=e.target.closest(`a`);if(!a)return;S.fwd=a.id==`fw`?fn()-1:a.getAttribute(`onclick`)?fn()+1:0},true);addEventListener(`submit`,e=>{if(!e.defaultPrevented)S.fwd=0});}</script>
<span class=ttl>Log Explorer</span><i class=vr></i>
<label class="sx c0" title="Đổi đối tác (tìm trên tất cả stream của đối tác đó)">%(iu)s<select id=sp>%(po)s</select></label>
<button type=button class="sx c1" title="%(stt)s — bấm để đổi stream">%(ily)s<span class=two><small>%(stn)s</small><b>%(stl)s</b></span></button>
<label class="sx c2" title="Đổi khoảng thời gian">%(ical)s<span class=two><b id=tml></b><small id=tmr></small></span><select id=stm>%(to)s</select></label></div>
<div class=pop id=spop hidden><input id=sf placeholder="Lọc stream…" autocomplete=off><div id=sl></div><div class=pr2><button type=button class=sm id=sno>Bỏ chọn hết</button><span style="flex:1"></span><button type=button class="p sm" id=sok>Áp dụng</button></div><small style="opacity:.6">Không chọn stream nào = tìm trên tất cả stream.</small></div>
<div class=pop id=tpop hidden><label>Từ<input type=datetime-local id=tf></label><label>Đến<input type=datetime-local id=tt></label><div class=pr2><button type=button class="p sm" id=tok>Áp dụng</button></div></div>
<div class=hr2><form method=post action="%(b)s/ask" class=sq id=sqf>%(scope)s<input type=hidden name=act value=search><button class=sb title="Tìm">%(is)s</button><input name=q value="%(q)s" placeholder="Tìm endpoint, nội dung hoặc trace ID… (để trống = mọi log)" autocomplete=off><kbd>↵</kbd></form>
<button class="p b" form=sqf>Tìm log</button>
<form method=post action="%(b)s/ask">%(scope)s<input type=hidden name=q value="%(dq)s"><button class=b name=act value=ai title="Nhờ AI phân tích kết quả này">%(ia)s Phân tích với AI</button></form></div>
<div class=hr3><div class="tabs mdt"><button type=button data-md=t>Theo trace</button><button type=button data-md=a>Tất cả log</button><button type=button id=dbt>Dashboard</button></div><i class=vr></i><span id=cnt>%(nt)d trace · %(nl)d log đã tải</span><span style="flex:1"></span>
<span class=up>%(icl)s<span id=upd></span></span><button type=button class="b sm" id=rb title="Lấy log mới nhất với cùng phạm vi và từ khoá, giữ nguyên trace/log đang xem">%(irf)s Làm mới</button><select id=ar title="Tự làm mới sau mỗi khoảng thời gian"><option value=0>Tự động: Tắt<option value=5>Tự động: 5 giây<option value=10>Tự động: 10 giây<option value=15>Tự động: 15 giây<option value=30>Tự động: 30 giây</select></div></div>
<form method=post action="%(b)s/ask" id=af hidden>%(scope)s<input type=hidden name=q><input type=hidden name=act></form>
<div class=g3 id=g3>
<section class="pane lp"><div class=ph><div class=pr><h3>Trace</h3><span class=pill id=tc></span><span style="flex:1"></span><button type=button class=sm id=ts></button></div>
<div class=fi>%(is)s<input id=tq placeholder="Lọc trace…" autocomplete=off></div><div class=tabs id=tfc></div></div>
<div class=sc id=tl></div>
<button type=button class=lose id=lose>%(il)s<span>Log không có trace ID</span><b class=pill id=ln></b>›</button>
<div class=pf id=tpf><button type=button class=sm id=tpp>‹</button><span id=tpn></span><button type=button class=sm id=tpx>›</button></div></section>
<div class=vsp id=vsp title="Kéo để đổi độ rộng"><button type=button id=vtg></button></div><div class=rc id=rc>
<section class="pane mp"><div class=ph id=mh><div class=pr><h2 id=mn></h2><span class=pr id=mk></span><span style="flex:1"></span><button type=button class="p b sm" id=ma title="Nhờ AI phân tích trace này">%(ia)s Phân tích</button><button type=button class="sm b" id=fs title="Phóng to / thu nhỏ vùng log">%(ifs)s</button></div><div class="sub pr" id=mp></div></div>
<div class="pr tb"><b>Log trong trace</b><div class=fi>%(is)s<input id=lq placeholder="Tìm trong trace này…" autocomplete=off></div><div class=fc id=lfc></div><button type=button class="sm b" id=ls></button></div>
<div class="lr lh"><span>Thời gian</span><span>Mức log</span><span>Nội dung</span><span class=ap><u class=rz id=rz title="Kéo để đổi độ rộng cột"></u>Application</span><span class=du>Thời lượng</span></div>
<div class=sc id=ll></div><div class=pf id=mf><span id=mfn></span><button type=button class="sm b" id=more>Tải cả trace</button><div id=pgr></div></div></section>
<div class=spl id=spl hidden title="Kéo để đổi chiều cao"></div>
<section class=pane id=dp hidden><div class="pr dh"><h3>CHI TIẾT LOG</h3><span style="flex:1"></span><button type=button class=sm id=dpv title="Log trước (↑)">‹</button><span id=dpn></span><button type=button class=sm id=dnx title="Log sau (↓)">›</button><button type=button class=sm id=dx title="Đóng (Esc)">%(ix)s</button></div>
<div class=bdy id=db></div></section>
</div></div><section class=pane id=dash hidden></section>%(ft)s<template id=ic-copy>%(ic)s</template><template id=ic-sort>%(io)s</template><template id=ic-spark>%(ia)s</template>
<script>const SC=%(sc)s</script><script>const D=%(data)s</script>""" % {
        'n': E(name), 'b': B, 'nq': urllib.parse.quote(name), 'stt': E(title or 'Tất cả stream'), 'stn': 'Stream (%d)' % len(title.split(', ')) if title else 'Stream', 'stl': E((lambda p: p[0] + (' +%d' % (len(p) - 1) if len(p) > 1 else ''))((title or ('application ' + app if app else 'Tất cả stream')).split(', '))),
        'ily': ico('layers'), 'ical': ico('cal'), 'irf': ico('refresh'), 'po': ''.join('<option%s>%s' % (' selected' if p[0] == name else '', E(p[0])) for p in partners()),
        'to': ''.join('<option value="%s"%s>%s' % (E(v), ' selected' if v == tm else '', E(l)) for v, l in [(t, t) for t in TIMES] + ([] if tm in SECS else [(tm, tml(tm))]) + [('?', 'Tuỳ chọn từ – đến…')]),
        'sc': json.dumps({'tm': tm, 'secs': SECS.get(tm, 0), 'sid': sid.split(',') if sid else [], 'streams': (lambda u: sorted(get_streams(name, live=False) or [], key=lambda x: -u.get('s:' + x[1], 0)))(usage(name))}, ensure_ascii=False).replace('</', '<\\/'),
        'iu': ico('user'), 'icl': ico('clock'), 'scope': scope_in, 'q': E(q), 'dq': dq, 'nt': len(T), 'nl': len(seen),
        'ft': '<div class=ft><span>%s</span><a id=nar>Thu hẹp thời gian</a></div>' % E(' '.join(notes)) if notes else '', 'ifs': ico('full'),
        'ib': ico('back'), 'is': ico('search'), 'ia': ico('spark'), 'il': ico('link'), 'ix': ico('x'), 'ic': ico('copy'), 'io': ico('sort'),
        'data': json.dumps({'q': q, 'T': T, 'L': L}, ensure_ascii=False).replace('</', '<\\/')} + RJS


CHAT = """<style>
body{max-width:900px}
.q{scroll-margin-top:70px;margin:24px 0 10px auto;max-width:80%;width:fit-content;background:#2f6fed;color:#fff;padding:10px 14px;border-radius:14px 14px 4px 14px;white-space:pre-wrap;overflow-wrap:anywhere}
.ans{border:1px solid #8885;border-radius:4px 14px 14px 14px;padding:6px 18px 12px;background:#8881;overflow-wrap:break-word;line-height:1.6}
.ans>p:first-child{border-left:4px solid #2f6fed;background:#2f6fed1a;padding:10px 14px;border-radius:6px}
.ans h3{font-size:15px;margin:22px 0 8px}.ans li{margin:4px 0}
.ans code{font:12.5px ui-monospace,Menlo,monospace;color:#5b9dff}.ans h4{font-size:13px;font-weight:600;opacity:.6;margin:22px 0 8px}.ans h4+ul{list-style:none;padding:0;margin:0 0 6px;display:flex;flex-wrap:wrap;gap:8px}.ans h4+ul li{margin:0;border:1px solid #2f6fed88;border-radius:16px;padding:5px 12px;cursor:pointer;font-size:14px}.ans h4+ul li:hover{background:#2f6fed33}
.ans pre{background:#8882;padding:12px;border-radius:8px;overflow:auto;max-height:26em;font:12.5px/1.5 ui-monospace,Menlo,monospace}.ans pre code{background:none;padding:0}
.ans table{display:block;width:fit-content;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:10px 0;font-size:14px}
.ans th,.ans td{border-bottom:1px solid #8884;padding:7px 14px 7px 0;text-align:left;vertical-align:top}.ans th{font-size:12.5px;opacity:.6;font-weight:600;white-space:nowrap}
.wait{padding:14px 18px}.wait>span{animation:pulse 1.4s infinite}@keyframes pulse{50%{opacity:.45}}.wait small{opacity:.6;margin:0 12px}.stop,.retry{padding:3px 12px;font-size:13px}.ans code.tr{cursor:pointer;text-decoration:underline dotted}
#f{position:sticky;bottom:0;display:flex;gap:8px;align-items:flex-end;background:Canvas;padding:12px 0 16px;margin-top:24px;border-top:1px solid #8885}
#f textarea{flex:1;resize:none;max-height:9em}#f button:disabled{opacity:.45;cursor:default}
</style><title>Graylog AI — @N@</title>
<div class=nav><a class=btn href="@FORM@" onclick="if(history.length>1){history.back();return false}">← Quay lại</a><a class=btn id=fw hidden href="javascript:history.forward()">Tới →</a>
<a class="btn p" href="@FORM@">🔍 Tìm / hỏi câu khác</a><a class="btn r" href="@B@">🏠 Đối tác</a></div>
@CTX@
<div id=chat>@ITEMS@</div>
<form id=f method=post action="@B@/more"><input type=hidden name=name value="@N@"><input type=hidden name=tid value="@TID@">
<textarea name=q rows=1 autofocus></textarea><button class=p>Gửi ↑</button></form>@SF@
<script>
const S=sessionStorage,fn=()=>+S.fwd||0;addEventListener(`pageshow`,()=>{fw.hidden=!(fn()>0||(window.navigation&&navigation.canGoForward))});addEventListener(`click`,e=>{const a=e.target.closest(`a`);if(!a)return;S.fwd=a.id==`fw`?fn()-1:a.getAttribute(`onclick`)?fn()+1:0},true);addEventListener(`submit`,e=>{if(!e.defaultPrevented)S.fwd=0});
const chat=document.getElementById('chat'),f=document.getElementById('f'),t=f.q,btn=f.querySelector('button');
function mark(){if(document.getElementById('sf'))chat.querySelectorAll('.ans code').forEach(c=>{if(/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(c.textContent.trim())){c.className='tr';c.title='Mở log của trace này'}})}
function busy(){mark();const w=!!chat.querySelector('.wait');btn.disabled=w;t.placeholder=w?'AI đang trả lời…':'Hỏi tiếp về kết quả này… (Enter để gửi, Shift+Enter xuống dòng)'}
function last(){const q=chat.querySelectorAll('.q');q.length&&q[q.length-1].scrollIntoView({block:'start'})}
async function poll(){
  try{const d=new DOMParser().parseFromString(await(await fetch(location.href)).text(),'text/html').getElementById('chat');
    if(d.innerHTML!=chat.innerHTML){const more=d.children.length!=chat.children.length;chat.innerHTML=d.innerHTML;if(more)last()}}catch(e){}
  busy();if(chat.querySelector('.wait'))setTimeout(poll,3000)}
f.onsubmit=async e=>{e.preventDefault();if(btn.disabled||!t.value.trim())return;
  const b=new URLSearchParams(new FormData(f));t.value='';t.style.height='auto';btn.disabled=true;
  const r=await fetch(f.action,{method:'POST',body:b});if(!r.ok)alert('Không gửi được câu hỏi.');poll()};
chat.onclick=e=>{const li=e.target.closest('h4+ul li'),c=e.target.closest('code.tr');
  if(e.target.closest('.stop')){e.target.disabled=true;fetch('@B@/stop',{method:'POST',body:new URLSearchParams({name:f.elements.name.value,tid:f.elements.tid.value})});return}
  if(e.target.closest('.retry')){const qs=chat.querySelectorAll('.q');t.value=qs[qs.length-1].textContent;f.requestSubmit();return}
  if(c){const sf=document.getElementById('sf');sf.elements.q.value=c.textContent.trim();sf.requestSubmit(sf.querySelector('button'));return}
  if(li){t.value=li.textContent.trim();t.oninput();t.focus()}};
t.onkeydown=e=>{if(e.key=='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();f.requestSubmit()}};
t.oninput=()=>{t.style.height='auto';t.style.height=t.scrollHeight+2+'px'};
last();busy();if(chat.querySelector('.wait'))setTimeout(poll,3000);
</script>"""


def chat_page(name, tid):
    d = os.path.join(CONF, 'ask')
    try: files = open(os.path.join(d, tid + '.thread')).read().split()
    except FileNotFoundError: return None
    items, label = [], ''
    for f in files:
        meta = open(os.path.join(d, f[:-5] + '.meta'), encoding='utf-8').read().split('\n')
        label = meta[2]
        mp, n = os.path.join(d, f[:-5] + '.meta'), 0
        age = time.time() - os.path.getmtime(mp)
        if not os.path.exists(os.path.join(d, f)) and age > 900:
            # AI tự dừng sau 8 phút; quá 15 phút vẫn chưa có file = tiến trình đã chết (máy tắt/ngủ) -> ghi thành câu hỏng để còn thử lại
            open(os.path.join(d, f), 'w', encoding='utf-8').write('<!--fail--><p>⚠️ Câu này bị ngắt giữa chừng (máy tắt hoặc ngủ lúc AI đang trả lời).</p>')
        try:
            ans = open(os.path.join(d, f), encoding='utf-8').read()   # đã qua safehtml của gl
            if ans.startswith('<!--fail-->') and f == files[-1]: ans += '<p><button type=button class=retry>↻ Thử lại câu này</button></p>'
            ans = '<div class=ans>%s</div>' % ans
        except FileNotFoundError:
            try: n = open(os.path.join(d, f + '.log'), encoding='utf-8', errors='replace').read().count('"type":"tool_use"')
            except OSError: pass
            ans = '<div class="ans wait"><span>%s</span><small>đã chờ %d:%02d · tự dừng sau 8:00</small><button type=button class=stop>⏹ Dừng</button></div>' % (
                '🔎 Đã chạy %d truy vấn log — đang đọc và phân tích…' % n if n else '🤖 Đang khởi động AI, chưa truy vấn log…', age // 60, age % 60)
        items.append('<div class=q>%s</div>%s' % (E(meta[4]), ans))
    out = CSS + CHAT
    try:   # phạm vi của cuộc hỏi (stream, thời gian) -> bấm vào trace id trong câu trả lời là mở đúng log làm bằng chứng
        sc = json.load(open(os.path.join(d, tid + '.scope')))
        sf = '<form id=sf hidden method=post action="%s/ask">%s<input name=q><button name=act value=search></button></form>' % (
            B, ''.join('<input name=%s value="%s">' % (k, E(v)) for k, v in [('name', name)] + sorted(sc.items())))
    except (OSError, ValueError): sf = ''
    out = out.replace('@SF@', sf)
    for k, v in [('@ITEMS@', ''.join(items)), ('@FORM@', '%s/ask?name=%s' % (B, urllib.parse.quote(name))), ('@B@', B),
                 ('@N@', E(name)), ('@CTX@', ctx(name, label)), ('@TID@', tid)]:
        out = out.replace(k, v)
    return out


def trace_logs(name, sid, app, tm, q):
    # câu hỏi có trace id -> lấy sẵn TOÀN BỘ log của trace (kể cả log lẻ) đưa cho AI, không phụ thuộc AI tự tìm đủ
    ids = list(dict.fromkeys(re.findall(UUID, q)))[:3]
    if not ids: return ''
    code, out = gl('_search', name, sid, app, rng(tm), ' OR '.join('"%s"' % i for i in ids))
    try: msgs = json.loads(out)['messages'] if not code else []
    except (ValueError, KeyError): return ''
    logs = sorted(set((str(m['message'].get('timestamp', '')), str(m['message'].get('message', ''))) for m in msgs))
    if not logs: return ''
    # ponytail: cắt ở 300k ký tự (giới hạn độ dài tham số lệnh); trace dài hơn thì AI tự truy vấn phần còn lại
    return ('%d log của trace %s (timestamp là giờ UTC, khi trả lời đổi sang giờ Việt Nam +7):\n\n' % (len(logs), ', '.join(ids))
            + '\n\n'.join('[%s] %s' % x for x in logs))[:300000]


def ctx(name, label):
    # dòng ngữ cảnh: đối tác · stream/application · khoảng thời gian (phần cuối của label luôn là thời gian)
    parts = label.split(' \u00b7 ')
    icons = ['\U0001F4C2'] * (len(parts) - 1) + ['\U0001F552']
    return '<div class=ctx><span>%s</span>%s</div>' % (E(name), ''.join('<span>%s %s</span>' % (i, E(x)) for i, x in zip(icons, parts)))


def get_streams(name, live=True):
    # live=False: trả ngay danh sách đã lưu (mạng tới Graylog có lúc chậm 10-30s), rồi làm mới ngầm cho lần sau
    f = os.path.join(CONF, 'streams-%s.json' % name)
    if not live:
        try: r = json.load(open(f))
        except (OSError, ValueError): r = None
        if r:
            threading.Thread(target=get_streams, args=(name,), daemon=True).start()
            return r
    code, out = gl('_streams', name)
    if code: return None
    r = [l.rsplit(SEP, 1) for l in out.split('\n') if SEP in l]
    json.dump(r, open(f + '.tmp', 'w')); os.replace(f + '.tmp', f)
    return r


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def page(self, body, code=200):
        b = body.encode()
        self.send_response(code); self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def go(self, path='', msg=''):
        self.send_response(303)
        self.send_header('Location', B + path + ('?m=' + urllib.parse.quote(msg) if msg else ''))
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        names = [p[0] for p in partners()]
        if u.path == B:
            edit = q.get('edit', '')
            return self.page(main_page(q.get('m', ''), edit if edit in names else ''))
        if u.path == B + '/ask' and q.get('name') in names:
            streams = get_streams(q['name'], live=False)
            if streams is None: return self.go(msg='Không lấy được danh sách stream của %s (sai mật khẩu hoặc không tới được server).' % q['name'])
            return self.page(ask_page(q['name'], streams))
        m = re.fullmatch(re.escape(B) + r'/c/([a-z0-9._-]+)/(\d{8}-\d{6})', u.path)
        body = m and m.group(1) in names and chat_page(m.group(1), m.group(2))
        if body: return self.page(body)
        self.page('', 404)

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        f = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode(), keep_blank_values=True)
        g = lambda n: f.get(n, [''])[0].strip()
        names = [p[0] for p in partners()]
        if u.path == B + '/save':
            return self.go(msg=gl('_save', g('old'), g('name'), g('url'), g('user'), stdin=f.get('pw', [''])[0])[1])
        if u.path == B + '/test': return self.page(gl('_test', g('old'), g('url'), g('user'), stdin=f.get('pw', [''])[0])[1])
        if g('name') not in names: return self.page('Không có đối tác này', 400)
        if u.path == B + '/pw': return self.page(gl('_pw', g('name'))[1])   # con mắt ở form Sửa: xem mật khẩu đã lưu
        if u.path == B + '/open': return self.go(msg=gl(g('name'))[1])
        if u.path == B + '/rm': return self.go(msg=gl('rm', g('name'))[1])
        if u.path == B + '/more':
            try: sc = json.load(open(os.path.join(CONF, 'ask', os.path.basename(g('tid')) + '.scope')))
            except (OSError, ValueError): sc = None
            code, out = gl('_more', g('name'), g('tid'), g('q'), stdin=trace_logs(g('name'), sc['sid'], sc['app'], sc['tm'], g('q')) if sc else '')
            return self.page('', 400 if code else 200)
        if u.path == B + '/stop' and re.fullmatch(r'\d{8}-\d{6}', g('tid')):
            d = os.path.join(CONF, 'ask')
            try:
                f = open(os.path.join(d, g('tid') + '.thread')).read().split()[-1]
                ai = open(os.path.join(d, f[:-5] + '.meta')).readline().strip()
            except (OSError, IndexError): return self.page('', 404)
            if not os.path.exists(os.path.join(d, f)) and re.fullmatch(UUID, ai):
                open(os.path.join(d, f[:-5] + '.stop'), 'w').close()   # gl đọc cờ này để ghi "Đã dừng theo yêu cầu"
                gl('_stop', f[:-5])
            return self.page('')
        if u.path == B + '/agg':   # Dashboard: Graylog tự đếm log API theo status / api trong đúng phạm vi đang chọn
            ids = [i for t, i in get_streams(g('name'), live=False) or []]
            sid, tm = g('sid'), g('tm')
            if any(i not in ids for i in sid.split(',') if i) or not (tm in SECS or span(tm)): return self.page('', 400)
            code, out = gl('_agg', g('name'), sid, g('app') if not sid else '', rng(tm), g('q'), g('slow'))
            return self.page('' if code else out, 502 if code else 200)
        if u.path == B + '/ask':
            ids = dict((i, t) for t, i in get_streams(g('name'), live=False) or [])
            sid, tm = g('sid'), g('tm')
            sids = sid.split(',') if sid else []
            title = ', '.join(ids.get(i, '') for i in sids)
            if len(sids) > 20 or any(i not in ids for i in sids) or not (tm in SECS or span(tm)): return self.page('Dữ liệu không hợp lệ', 400)
            if g('auto'): pass   # tự làm mới: không tính vào hay-dùng / gần đây
            elif sids: [usage(g('name'), 's:' + i) for i in sids]
            elif re.fullmatch(r'[A-Za-z0-9._-]+', g('app')): usage(g('name'), 'a:' + g('app'))
            if g('act') != 'ai' and not g('auto'): searches(g('name'), [sid, title, g('app') if not sid else '', tm, g('q')])
            if g('act') != 'ai': return self.page(search_page(g('name'), sid, title, g('app'), tm, g('q')))
            if not g('q'): return self.page('Thiếu câu hỏi', 400)
            app = g('app') if not sid else ''
            code, out = gl('_ask', g('name'), sid, title, g('app'), tml(tm), g('q'), stdin=trace_logs(g('name'), sid, app, tm, g('q')))
            if code: return self.go(msg='Không hỏi được: ' + out)
            json.dump({'sid': sid, 'app': app, 'tm': tm}, open(os.path.join(CONF, 'ask', out + '.scope'), 'w'))
            open(os.path.join(CONF, 'ask', out + '.who'), 'w').write(g('name'))
            return self.go('/c/%s/%s' % (g('name'), out))
        self.page('', 404)


srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
URL = 'http://127.0.0.1:%d%s' % (srv.server_address[1], B)
if sys.stdout: print(URL, flush=True)
if sys.argv[2:] == ['app']:
    # chạy dưới Graylog.app: sống cùng app, app thoát (stdin đóng) thì thoát theo
    import threading
    threading.Thread(target=lambda: (sys.stdin.read(), os._exit(0)), daemon=True).start()
    srv.serve_forever()
elif sys.argv[2:] == ['browser']:
    # không có app native (Windows): mở một cửa sổ Edge/Chrome dạng app, đóng cửa sổ thì thoát
    import threading, webbrowser
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pf = [os.environ.get(k, '') for k in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
    exe = next((p for p in [os.path.join(d, r) for r in (r'Microsoft\Edge\Application\msedge.exe', r'Google\Chrome\Application\chrome.exe') for d in pf if d]
                + ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'] if os.path.exists(p)), None)
    if exe:   # profile riêng để tiến trình này sống đúng bằng cửa sổ
        subprocess.call([exe, '--app=' + URL, '--user-data-dir=' + os.path.join(CONF, 'browser-profile'), '--window-size=900,720',
                         '--no-first-run', '--no-default-browser-check', '--disable-background-mode'], stderr=subprocess.DEVNULL)
    else:   # ponytail: không tìm thấy Edge/Chrome -> trình duyệt mặc định, server chạy tới khi tắt tiến trình
        webbrowser.open(URL)
        while True: time.sleep(3600)
