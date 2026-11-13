# chạy: python3 test_gl.py — kiểm tra việc đổi giá trị status (mã HTTP / level) về 3 nhóm của Dashboard
import importlib.util, os
s = importlib.util.spec_from_file_location('glmod', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'graylog_app', 'gl.py'))
g = importlib.util.module_from_spec(s); s.loader.exec_module(g)
assert [g.bucket('level', x) for x in ('3', '4', '6')] == ['ERROR', 'BUSINESS_ERROR', 'SUCCESS']
assert [g.bucket('http_status', x) for x in ('200', '404.0', '503', 'OK')] == ['SUCCESS', 'BUSINESS_ERROR', 'ERROR', 'OK']
assert g.bucket('api_status', '500') == '500'
assert g.why('{"message":"","toastMessage":"Hết hàng\\nchi tiết","errorReason":"E1"}') == ('Hết hàng', '"Hết hàng"')
assert g.why('{"error":true,"errorReason":"no.map"}')[0] == 'no.map' and g.why('<html>502 "x"</html>') == ('<html>502 "x"</html>', '"<html>502 \\"x\\"</html>"')
print('ok')
