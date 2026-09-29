"""Bad cohort identity must preserve failure slots without calling the SfM engine."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

script=Path(__file__).with_name('initialize_video_cameras.py')
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);protocol=root/'protocol.json'
    protocol.write_text(json.dumps({'cohort':'fixed','expected_scene_count':3,'expected_frames_per_scene':6}))
    for name,ids,status,cohort in [('missing',['a','b'],'frozen','fixed'),
                                  ('duplicate',['a','a','b'],'frozen','fixed'),
                                  ('global_failure',['a','b','c'],'failed','fixed'),
                                  ('wrong_cohort',['a','b','c'],'frozen','other')]:
        frames=root/(name+'.json');frames.write_text(json.dumps({'cohort_id':cohort,'status':status,
            'sources':[{'id':i,'status':'frozen','selected_frames':[]} for i in ids]}))
        out=root/name
        result=subprocess.run([sys.executable,str(script),'--frames',str(frames),'--protocol',str(protocol),'--output',str(out)],capture_output=True,text=True)
        assert result.returncode==1,result.stderr
        receipt=json.loads((out/'receipt.json').read_text())
        assert receipt['expected_scene_count']==3 and len(receipt['sources'])==3
        assert receipt['initialized_scene_count']==0 and all(s['status']=='failed' for s in receipt['sources'])
        assert receipt['original_inputs_unchanged']
        for filename,expected in receipt['snapshots'].items():
            assert hashlib.sha256((out/filename).read_bytes()).hexdigest()==expected
print('SFM_INPUT_IDENTITY_FAILURE_DENOMINATOR_AND_SNAPSHOTS_OK')
