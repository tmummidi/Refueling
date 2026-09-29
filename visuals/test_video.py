import unittest
import numpy as np
from continuity.simulation import Incident, generate, evaluate
from make_video import trace, totals, state, stamp


class ReplayTests(unittest.TestCase):
    def test_replay_agrees_with_core_for_zero_and_multiple_crews(self):
        for seed in (2,17,99):
            jobs=generate(seed,4)
            for allocation in ([0,0,0,0],[1,2,3,4],[4,2,1,0]):
                actual=totals(trace(jobs,allocation),72)
                expected=evaluate(jobs,allocation,72,6)
                self.assertAlmostEqual(actual['loss'],expected['weighted_unresolved_hours'])
                self.assertEqual(actual['done'],expected['completed'])
                self.assertEqual(actual['waiting']+actual['active'],expected['unfinished'])

    def test_exact_horizon_completion_and_fifo(self):
        rows=trace([[Incident(0,2),Incident(0,3)]],[1],5)[0]
        self.assertEqual([r['start'] for r in rows],[0,2])
        self.assertEqual([r['end'] for r in rows],[2,5])
        self.assertEqual(state(rows,5)['done'],2)
        self.assertEqual(state(rows,1)['waiting'],1)
        self.assertEqual(state(rows,5)['loss'],7)

    def test_unfinished_service_and_conservation(self):
        rows=trace([[Incident(0,100),Incident(1,2),Incident(60,1)]],[1])[0]
        self.assertIsNone(rows[0]['end'])
        for t in np.linspace(0,72,33):
            s=state(rows,t)
            self.assertEqual(s['arrived'],s['waiting']+s['active']+s['done'])
        self.assertEqual(state(rows,72)['loss'],72+71+12)

    def test_future_incidents_do_not_appear(self):
        rows=trace([[Incident(10,2)]],[1])[0]
        self.assertEqual(state(rows,9)['arrived'],0)
        self.assertEqual(state(rows,9)['loss'],0)

    def test_subtitle_timestamps(self):
        self.assertEqual(stamp(61.125),'00:01:01,125')


if __name__=='__main__':unittest.main()
