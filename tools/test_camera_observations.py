"""Input-to-render camera checks; synthetic fixtures are not reconstruction scores."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
import cv2
import numpy as np
from r2s.camera import check_scene_cameras,load_observations,resize_camera,workflow_constraints
from r2s.core import Workflow
from r2s.geometry_feedback import _project


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.image=self.root/'source.png';cv2.imwrite(str(self.image),np.random.default_rng(7).integers(0,255,(60,80,3),dtype=np.uint8))
        self.sha=hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.entry=dict(input_index=0,frame_id='view0',source_sha256=self.sha,role='reconstruction',image_size=[80,60],
            K=[[70,0,31.5],[0,55,26.5],[0,0,1]],T_world_camera=[[0,-1,0,1],[1,0,0,2],[0,0,1,3],[0,0,0,1]],
            distortion_model='none',pose_source='measured',evidence=['synthetic fixture'])
        self.manifest=dict(schema='real2sim.camera-observations/1',units='m',up_axis='Z',camera_frame='opencv',pixel_coordinates='integer_centers',frames=[self.entry])
        self.config=dict(id='synthetic-camera',mode='single',inputs=[dict(path=str(self.image))],formal_test=False,
            workflow_profile='quality_v2',provenance=dict(kind='synthetic_fixture'),stages={'preprocess':{'parameters':{'max_edge':40}}})
        self.write()

    def write(self):
        path=self.root/'cameras.json';path.write_text(json.dumps(self.manifest))
        self.config['camera_observations']=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        (self.root/'case.json').write_text(json.dumps(self.config))

    def load(self):
        return load_observations(self.config,[dict(sha256=self.sha,image_size=[80,60])])

    def test_projection_pose_and_resize(self):
        camera=self.load()['cameras'][0]
        self.assertTrue(np.allclose(_project([1,3,5],camera),[66.5,26.5]))
        resized=resize_camera(camera,[40,30])
        self.assertTrue(np.allclose(_project([1,3,5],resized),([66.5,26.5]+np.array([.5,.5]))*.5-.5))
        self.assertEqual(resized['focal_y_px'],27.5)

    def test_workflow_packet_cache_and_scene_lock(self):
        workflow=Workflow(self.root);self.assertEqual(workflow.run(until='preprocess')['status'],'completed_until')
        locked=workflow_constraints(workflow);self.assertEqual(locked['cameras'][0]['image_size'],[40,30])
        self.assertEqual(workflow.execute('agent_observe'),'awaiting_agent')
        packet=json.loads((Path(workflow.state['stages']['agent_observe']['directory'])/'packet.json').read_text())
        self.assertEqual(packet['camera_constraints'],locked)
        scene=dict(camera=copy.deepcopy(locked['cameras'][0]),cameras=copy.deepcopy(locked['cameras']))
        check_scene_cameras(scene,locked);scene['camera']['position'][0]+=.01
        with self.assertRaises(ValueError):check_scene_cameras(scene,locked)
        self.entry['K'][0][0]+=1;self.write()
        self.assertFalse(Workflow(self.root).valid('ingest'))

    def test_reject_wrong_bindings_and_camera_conventions(self):
        for key,value in [('source_sha256','bad'),('role','holdout'),('image_size',[81,60]),
                          ('distortion_model','radtan'),('pose_source','ground_truth'),('input_index',4)]:
            with self.subTest(key=key):
                old=self.entry[key];self.entry[key]=value;self.write()
                with self.assertRaises(ValueError):self.load()
                self.entry[key]=old
        self.write();self.manifest['frames'].append(copy.deepcopy(self.entry));self.write()
        with self.assertRaises(ValueError):self.load()

    def test_reject_nonfinite_reflection_skew_and_hash(self):
        original=copy.deepcopy(self.entry)
        for key,i,j,value in [('K',0,0,float('nan')),('K',0,1,2),('T_world_camera',3,3,2),('T_world_camera',2,2,-1)]:
            self.entry.update(copy.deepcopy(original));self.entry[key][i][j]=value;self.write()
            with self.assertRaises(ValueError):self.load()
        self.entry.update(original);self.write();self.config['camera_observations']['sha256']='wrong'
        with self.assertRaises(ValueError):self.load()

    def test_explicit_gt_and_legacy(self):
        self.entry['pose_source']='ground_truth';self.write();self.config['camera_observations']['allow_ground_truth_pose']=True
        self.assertEqual(self.load()['scope'],'GT-pose diagnostic')
        self.config.pop('camera_observations');self.assertIsNone(self.load())

    def test_calibrated_video_preserves_exact_frame_order(self):
        video=self.root/'source.avi';writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10.,(80,60))
        self.assertTrue(writer.isOpened())
        for value in [40,90,140]:writer.write(np.full((60,80,3),value,np.uint8))
        writer.release();self.config.update(mode='video',inputs=[dict(path=str(video))])
        video_sha=hashlib.sha256(video.read_bytes()).hexdigest()
        self.manifest['frames']=[dict(copy.deepcopy(self.entry),source_sha256=video_sha,source_frame=i,frame_id='video'+str(i)) for i in [2,0]]
        self.write();workflow=Workflow(self.root);workflow.run(until='preprocess')
        frames=workflow_constraints(workflow)['cameras'];self.assertEqual([f['source_frame'] for f in frames],[2,0])
        self.assertEqual([f['frame_id'] for f in frames],['video2','video0'])

    def test_mujoco_asymmetric_projection(self):
        import mujoco
        for fx,fy in [(710.,530.),(490.,830.)]:
            xml=f'<mujoco><worldbody><camera name="source" resolution="640 480" sensorsize=".036 .027" focalpixel="{fx} {fy}" principalpixel="32.7 -11.2" ipd="0"/></worldbody></mujoco>'
            model=mujoco.MjModel.from_xml_string(xml);data=mujoco.MjData(model);mujoco.mj_forward(model,data)
            camera=mujoco.MjvCamera();camera.type=mujoco.mjtCamera.mjCAMERA_FIXED;camera.fixedcamid=0
            view=mujoco.MjvScene(model,maxgeom=10)
            mujoco.mjv_updateScene(model,data,mujoco.MjvOption(),None,camera,mujoco.mjtCatBit.mjCAT_ALL,view)
            frustum=view.camera[0]
            recovered=[frustum.frustum_near*640/(2*frustum.frustum_width),frustum.frustum_near*480/(frustum.frustum_top-frustum.frustum_bottom),320-frustum.frustum_center*640/(2*frustum.frustum_width),480*frustum.frustum_top/(frustum.frustum_top-frustum.frustum_bottom)]
            self.assertLess(float(np.max(np.abs(np.array(recovered)-[fx,fy,287.3,251.2]))),.002)


if __name__=='__main__':unittest.main()
