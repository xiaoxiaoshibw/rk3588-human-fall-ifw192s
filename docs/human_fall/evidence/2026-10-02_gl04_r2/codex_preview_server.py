from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def end_headers(self):self.send_header('Cache-Control','no-store');super().end_headers()
HTTPServer(('127.0.0.1',8876),Handler).serve_forever()
