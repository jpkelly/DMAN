"""Display state tests using actual captured HID reports, with a controlled clock."""
import unittest
from pathlib import Path
from dsan_display.model import Source

FIXTURES = Path(__file__).parent / 'fixtures' / 'dongle'


def feed(source, fixture, now):
    raw = (FIXTURES / fixture).read_bytes()
    for i in range(0,len(raw),8):
        source.receive(raw[i:i+8],now=now)


class DisplayTests(unittest.TestCase):
    def source(self, name='a'):
        source=Source(name,name,'replay','fixture',warmup=1)
        source.connected(now=0)
        return source

    def test_stale_never_advances_last_value(self):
        source=self.source()
        feed(source,'pi-p1-paused-0052.bin',2)
        self.assertTrue(source.snapshot(2)['fresh'])
        self.assertFalse(source.snapshot(5)['fresh'])
        self.assertEqual(source.snapshot(100)['programs'][0]['seconds'],52)
        source.end('disconnected','test unplug')
        self.assertFalse(source.snapshot(2)['fresh'])
        self.assertEqual(source.snapshot(2)['programs'][0]['seconds'],52)

    def test_confirmed_stop_at_zero_preserves_raw_overtime(self):
        source=self.source()
        feed(source,'pi-p1-running-through-zero.bin',2)
        program=source.snapshot(2)['programs'][0]
        self.assertEqual(program['seconds'],0)
        self.assertEqual(program['raw_seconds'],-11)
        self.assertTrue(program['running'])

    def test_source_and_program_isolation(self):
        a,b=self.source('a'),self.source('b')
        feed(a,'pi-p1-paused-0052.bin',2)
        feed(b,'pi-program-switch.bin',2)
        a.end('disconnected')
        self.assertTrue(b.snapshot(2)['fresh'])
        self.assertEqual(b.snapshot(2)['selected'],1)
        self.assertEqual(b.snapshot(2)['programs'][1]['seconds'],1920)
        self.assertEqual(a.snapshot(2)['programs'][0]['seconds'],52)

    def test_initial_buffer_is_not_presented_as_fresh(self):
        source=self.source()
        feed(source,'pi-p1-stopped-0100.bin',0.2)
        self.assertTrue(source.snapshot(0.2)['warming'])
        self.assertFalse(source.snapshot(0.2)['fresh'])
        self.assertTrue(source.snapshot(1.1)['fresh'])

    def test_replay_end_marks_last_value_stale(self):
        source=self.source()
        feed(source,'pi-p1-paused-0052.bin',2)
        source.end('ended')
        self.assertFalse(source.snapshot(2)['fresh'])
        self.assertEqual(source.snapshot(2)['programs'][0]['seconds'],52)
