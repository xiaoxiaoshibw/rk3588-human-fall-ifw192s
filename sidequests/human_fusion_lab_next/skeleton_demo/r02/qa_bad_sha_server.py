"""只用于检验浏览器拒绝错误响应SHA；非用户入口。"""
from server_v3 import PreviewHandler, ThreadingHTTPServer


class BadShaHandler(PreviewHandler):
    def send(self, body, kind='application/json; charset=utf-8', extra=None, status=200):
        if extra and 'X-Content-SHA256' in extra:
            extra = dict(extra, **{'X-Content-SHA256': '0' * 64})
        return super().send(body, kind, extra, status)


if __name__ == '__main__':
    print('QA bad SHA localhost:8928', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8928), BadShaHandler).serve_forever()
