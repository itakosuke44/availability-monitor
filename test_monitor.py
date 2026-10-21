import io
import unittest
from PIL import Image, ImageDraw
from monitor import symbol, transitions

class MonitorTests(unittest.TestCase):
    def png(self, shape):
        im = Image.new('RGB', (20,20), 'white')
        draw = ImageDraw.Draw(im)
        if shape == 'circle': draw.ellipse((2,2,17,17), outline='#79758a', width=2)
        if shape == 'dash': draw.rectangle((2,9,17,11), fill='#79758a')
        if shape == 'filled': draw.ellipse((2,2,17,17), fill='#79758a')
        out = io.BytesIO(); im.save(out, format='PNG'); return out.getvalue()
    def test_pixels(self):
        for shape, expected in [('circle','available'),('dash','soldout'),('blank','unknown'),('filled','unknown')]:
            self.assertEqual(symbol(self.png(shape)), expected)
    def test_notifications_and_unknown(self):
        state, opened = transitions({}, {'day':'available'})
        self.assertEqual(opened, ['day'])
        state, opened = transitions(state, {'day':'unknown'})
        self.assertEqual(state['day'], 'available')
        self.assertEqual(opened, [])
        state, opened = transitions(state, {'day':'available'})
        self.assertEqual(opened, [])
        state, _ = transitions(state, {'day':'soldout'})
        _, opened = transitions(state, {'day':'available'})
        self.assertEqual(opened, ['day'])
    def test_closed_not_available(self):
        self.assertEqual(transitions({}, {'day':'closed'})[1], [])

if __name__ == '__main__': unittest.main()
