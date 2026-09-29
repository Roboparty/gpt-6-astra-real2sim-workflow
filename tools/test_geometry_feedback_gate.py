"""Reject rendering success with failed or modified geometric feedback."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import ContractError
from r2s.quality import check_geometry_feedback
from r2s.core import Workflow

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);report=root/'geometry_feedback'/'report.json'
    report.parent.mkdir()
    packet=root/'packet.json'
    packet.write_text(json.dumps({'input_artifacts':{}}))
    check_geometry_feedback(root)
    for status in ['passed','failed']:
        report.write_text(json.dumps({'status':status}))
        packet.write_text(json.dumps({'input_artifacts':{'build_geometry':[{
            'path':str(report),'sha256':hashlib.sha256(report.read_bytes()).hexdigest()}]}}))
        if status=='passed':check_geometry_feedback(root)
        else:
            try:check_geometry_feedback(root)
            except ContractError:pass
            else:raise AssertionError('Failed geometry escaped gate')
    report.write_text(json.dumps({'status':'passed'}))
    try:check_geometry_feedback(root)
    except ContractError:pass
    else:raise AssertionError('Modified feedback escaped gate')
    source=root/'source.png';source.write_bytes(b'original source')
    mask=root/'mask.png';mask.write_bytes(b'original mask')
    protocol=root/'protocol.json'
    protocol.write_text(json.dumps({'views':[{'source':{'path':'source.png'},'objects':[{'mask':{'path':'mask.png'}}]}]}))
    workflow=Workflow.__new__(Workflow)
    workflow.config={'stages':{'build_geometry':{'parameters':{'geometry_feedback_protocol':str(protocol)}}}}
    workflow.state={'stages':{}};workflow.stage_map={'build_geometry':([],False)};workflow.refining=False
    before=workflow.fingerprint('build_geometry')
    mask.write_bytes(b'changed mask')
    changed=workflow.fingerprint('build_geometry');assert changed!=before
    mask.unlink();assert workflow.fingerprint('build_geometry')!=changed
    protocol.unlink();assert workflow.fingerprint('build_geometry')!=before
print('GEOMETRY_FEEDBACK_REVIEW_GATE_OK')
