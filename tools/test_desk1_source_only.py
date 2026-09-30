"""Synthetic geometry regression: internet-prior availability cannot change B's fit."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from fit_desk1_cuboids import project,vertices

class SourceOnlyTests(unittest.TestCase):
    def test_empty_or_absent_priors_do_not_change_source_only_solution(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC_desk1_sourceonly_') as td:
            root=Path(td);source=root/'synthetic_source_bytes.txt';source.write_text('SYNTHETIC-only source binding; no retrieved photograph.')
            digest=hashlib.sha256(source.read_bytes()).hexdigest();camera=[np.log(2000/1.5),30,.8,.43]
            boxes=[]
            for key,pose,dims,heldout in [('domino_sugar_box',[-.24,-.12,35],[.089,.038,.175],3),
                ('chocolate_jello_box',[.02,-.15,-20],[.11,.089,.035],2),('red_jello_box',[.18,-.01,20],[.085,.028,.073],3)]:
                pixels=project(vertices(*pose,dims),camera)
                boxes.append({'id':key,'height_assumed_m':dims[2],'top_front_order':pixels[4:].tolist(),
                    'bottom_pixels':{str(i):pixels[i].tolist() for i in [0,1,heldout]}})
            annotation=root/'annotation.json';annotation.write_text(json.dumps({'source_image':str(source),'source_sha256':digest,
                'camera':{'focal_px':2000,'position':[0,-.65,.43],'down_pitch_deg':30,'roll_deg':.8},'boxes':boxes}))
            phase=root/'phase.json';phase.write_text(json.dumps({'source_sha256':digest,'fit_protocol':{'maximum_solver_evaluations_per_start':2000}}))
            report=root/'empty_web_report.json';report.write_text(json.dumps({'status':'validated','model_priors':[]}))
            solutions=[]
            for label,web in [('without_report',None),('empty_priors',report)]:
                out=root/label;argv=[sys.executable,str(Path(__file__).with_name('fit_desk1_cuboids.py')),
                    '--annotation',str(annotation),'--phase',str(phase),'--arm','B_image_cuboids','--output',str(out)]
                if web:argv+=['--web-report',str(web)]
                proc=subprocess.run(argv,capture_output=True,text=True,timeout=20);self.assertEqual(proc.returncode,0,proc.stderr)
                fit=json.loads((out/'fit.json').read_text());self.assertEqual(fit['web_consumption'],[])
                for b in fit['boxes']:
                    self.assertIsNone(b['nominal_web_local_dimensions_m']);self.assertIsNone(b['relative_web_prior_deviation'])
                solutions.append(fit)
            self.assertEqual(solutions[0]['camera'],solutions[1]['camera'])
            self.assertEqual(solutions[0]['metrics'],solutions[1]['metrics'])
            self.assertEqual(solutions[0]['boxes'],solutions[1]['boxes'])
            # A soft/fixed web arm still fails closed when no eligible numerical prior exists.
            proc=subprocess.run([sys.executable,str(Path(__file__).with_name('fit_desk1_cuboids.py')),
                '--annotation',str(annotation),'--phase',str(phase),'--web-report',str(report),
                '--arm','C_web_soft_cuboids','--output',str(root/'missing_web_for_C')],capture_output=True,text=True,timeout=20)
            self.assertNotEqual(proc.returncode,0);self.assertIn('Required dimension prior unavailable',proc.stderr)

if __name__=='__main__':unittest.main()
