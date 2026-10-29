import json
import unittest
from pathlib import Path

from PIL import ImageFont
import render_video as video


class VideoTest(unittest.TestCase):
    def test_full_sessions_and_camera_pairs(self):
        for seq, (name, title) in enumerate(video.SESSIONS, 1):
            source = video.SOURCE / ('replay_' + name)
            rows = video.load_records(source / 'data/frames.js')
            summary = json.loads((source / 'SUMMARY.json').read_text(encoding='utf-8'))
            self.assertEqual(len(rows), summary['source']['frames'])
            counts = video.repeats(rows)
            self.assertTrue(all(n >= 1 for n in counts))
            self.assertLess(abs(sum(counts)/video.FPS - (rows[-1]['t'] + .1)), .2)
            for row in rows:
                if row['cam']:
                    self.assertTrue((source/'camera'/('c%03d.jpg' % row['cam'][0])).exists())
            fonts = (ImageFont.truetype(video.FONT, 19), ImageFont.truetype(video.BOLD, 24),
                     ImageFont.truetype(video.BOLD, 35))
            sample = rows[len(rows)//2]
            view = summary['display']['view']
            image = video.render(sample, title, seq, (view['tx'],view['ty']), source/'camera', fonts)
            self.assertEqual(image.size, (video.WIDTH, video.HEIGHT))
            self.assertEqual(image.getpixel((50, 660)), (69,22,27) if sample['st'] in ('suspected','confirmed') else (18,31,38))


if __name__ == '__main__':
    unittest.main()
