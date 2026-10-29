import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from download_public_archive import run


class PublicDownloadTest(unittest.TestCase):
    def test_exact_range_prefix_and_full_checksum(self):
        payload = bytes(range(256))*12
        class Response:
            def __init__(self, begin, end):
                self.status_code = 206
                self.content = payload[begin:end+1]
                self.headers = {'Content-Range': 'bytes %d-%d/%d' % (begin, end, len(payload))}
            def raise_for_status(self): pass
            def __enter__(self): return self
            def __exit__(self, *_): pass
        def get(url, headers, timeout):
            begin, end = map(int, headers['Range'][6:].split('-'))
            return Response(begin, end)
        with tempfile.TemporaryDirectory() as tmp, patch('download_public_archive.requests.get', side_effect=get):
            root = Path(tmp)
            prefix = root/'old.partial'
            prefix.write_bytes(payload[:1024])
            evidence = root/'evidence'; evidence.mkdir()
            target = root/'new.tar'
            run('https://source.invalid/data', hashlib.sha256(payload).hexdigest(), target, evidence,
                workers=2, chunk_mib=1, prefix_source=prefix, prefix_bytes=1024)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(prefix.read_bytes(), payload[:1024])
            self.assertTrue(json.loads((evidence/'ARCHIVE_DOWNLOAD.json').read_text())['sha_match'])
            self.assertEqual(len((evidence/'CHUNKS.jsonl').read_text().splitlines()), 1)
            bad_evidence = root/'bad'; bad_evidence.mkdir()
            with self.assertRaises(ValueError):
                run('https://source.invalid/data', 'wrong', root/'bad.tar', bad_evidence, workers=1)
            self.assertTrue((root/'bad.tar').exists())


if __name__ == '__main__': unittest.main()
