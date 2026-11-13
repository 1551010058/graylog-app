"""gl.py giả để chụp ảnh giao diện mà không cần Graylog thật: trả dữ liệu bịa, ổn định giữa các lần chạy.
Dùng: chép gl-ui.py cạnh file này rồi chạy với HOME trỏ vào thư mục tạm có .config/gl/partners."""
import datetime, json, random, sys, uuid

a = sys.argv[1:] + [''] * 6
random.seed(7)
SEP = '   —   '
APPS = ['order-service', 'payment-service', 'catalog-service', 'notify-service']
APIS = [('order-service', 'POST', '/api/orders', 'Tạo đơn hàng'), ('order-service', 'GET', '/api/orders/search', 'Tìm đơn hàng'),
        ('order-service', 'GET', '/api/orders/detail', 'Chi tiết đơn hàng'), ('payment-service', 'POST', '/api/payments/charge', 'Thanh toán'),
        ('payment-service', 'POST', '/api/payments/refund', 'Hoàn tiền'), ('catalog-service', 'GET', '/api/products/price', 'Lấy giá sản phẩm'),
        ('catalog-service', 'GET', '/api/products/stock', 'Kiểm tra tồn kho'), ('notify-service', 'POST', '/api/notify/sms', 'Gửi SMS')]
now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
iso = lambda t: t.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (t.microsecond // 1000)

if a[0] == '_streams':
    print('\n'.join(s + SEP + '%024x' % i for i, s in enumerate(APPS, 1)))
elif a[0] == '_agg':
    apis = [x for x in APIS if not a[3] or x[0] == a[3]]
    api, app, st, slow, last = [], {}, {}, [], []
    for i, (sv, _, path, _) in enumerate(apis):
        for s, n in (('SUCCESS', random.randint(40, 900)), ('BUSINESS_ERROR', random.choice([0, 0, 3, 12, 31])), ('ERROR', random.choice([0, 0, 0, 2, 9]))):
            if n: api.append([path, s, n]); app[sv, s] = app.get((sv, s), 0) + n; st[s] = st.get(s, 0) + n
        if i % 2 == 0: slow.append([path, random.randint(1, 40)])
        last.append([path, (now - datetime.timedelta(seconds=random.randint(1, 3000))).timestamp() * 1000])
    time = [[iso(now - datetime.timedelta(seconds=30 * i)), dict((s, max(0, int(n / 120 * random.uniform(.3, 1.9)))) for s, n in st.items())] for i in range(120, 0, -1)]
    print(json.dumps({'st': sorted(st.items(), key=lambda x: -x[1]), 'api': api, 'slow': slow, 'app': [[k[0], k[1], n] for k, n in app.items()],
                      'last': last, 'time': time, 'slowq': 'duration_ms:>=' + (a[5] or '1000')}))
elif a[0] == '_search':
    msgs = []
    for i in range(14):
        tid = str(uuid.UUID(int=random.getrandbits(128), version=4))
        t = now - datetime.timedelta(seconds=40 * i + random.randint(0, 30))
        steps = random.sample(APIS, random.randint(2, 4))
        bad = i in (2, 9)
        for n, (sv, method, path, desc) in enumerate(steps, 1):
            status = ('BUSINESS_ERROR' if i == 2 else 'ERROR') if bad and n == len(steps) else 'SUCCESS'
            dur = random.randint(12, 180) * (9 if i == 5 else 1)
            body = {'orderId': 'DH%06d' % random.randint(1, 999999), 'quantity': random.randint(1, 5)}
            resp = {'code': 0, 'data': body} if status == 'SUCCESS' else {'code': 4001, 'message': 'Sản phẩm đã hết hàng'} if i == 2 else {'code': 500, 'message': 'Internal error'}
            msgs.append({'timestamp': iso(t + datetime.timedelta(milliseconds=70 * (len(steps) - n))), 'application': sv, 'level': 6 if status == 'SUCCESS' else 3, 'trace_id': tid,
                         'message': '== INFO API ==\nTrace ID: %s\nStep: %d\nURL: %s http://%s:8080%s\nDescription: %s\nHeaders: {"content-type":"application/json"}\nRequest Body: %s\n'
                                    'Duration: %d ms\nStatus: %s\nResponse: %s\n=====' % (tid, n, method, sv, path, desc, json.dumps(body), dur, status, json.dumps(resp, ensure_ascii=False))})
        if i == 9:
            msgs.append({'timestamp': iso(t + datetime.timedelta(milliseconds=30)), 'application': steps[-1][0], 'level': 3, 'trace_id': tid, 'message': 'Charge failed, retry 3/3',
                         'exceptionClass': 'java.net.SocketTimeoutException', 'exceptionMessage': 'Read timed out'})
    ids = [w.strip('"') for w in a[5].split() if len(w.strip('"')) == 36]
    msgs = [m for m in msgs if not ids or m['trace_id'] in ids]
    print(json.dumps({'messages': [{'message': m} for m in sorted(msgs, key=lambda m: m['timestamp'], reverse=True)], 'total_results': len(msgs)}))
else:
    print('demo')
