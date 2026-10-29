import unittest
import numpy as np
from PIL import Image
from render_enterprise import light_cloud, PANEL, ACCENT


class EnterpriseTest(unittest.TestCase):
    def test_pixel_recolour_keeps_point_positions(self):
        image=Image.fromarray(np.array([[[9,17,26],[70,232,154],[73,100,118]]],dtype=np.uint8))
        pixels=np.asarray(light_cloud(image))
        self.assertEqual(tuple(pixels[0,0]),PANEL)
        self.assertEqual(tuple(pixels[0,1]),ACCENT)
        self.assertEqual(tuple(pixels[0,2]),(155,148,136))


if __name__=='__main__': unittest.main()
