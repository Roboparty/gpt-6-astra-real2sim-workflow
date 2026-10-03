"""Package only this author's code and compact evidence; never models or raw datasets."""
from pathlib import Path
import json,hashlib,shutil,zipfile,datetime,collections
R=Path('/home/wqz/real2sim_agent_compare_20261003/OURS');stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
P=R/('handoff_small_'+stamp);P.mkdir()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(src,dest):
 src=Path(src);dst=P/dest;dst.parent.mkdir(parents=True,exist_ok=True)
 if src.stat().st_size>8_000_000:raise ValueError('Large input excluded: '+str(src))
 shutil.copyfile(src,dst)
def write(dest,obj):
 dst=P/dest;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(json.dumps(obj,indent=2))
V=R/'models/v3';selected=sha(V/'model.blend');assert selected=='4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85'
put(R/'replay_builder.py','replay_builder.py')
for f in ['build_scene_v3.py','prepare_native_assembly.py','v3_layout_corrections.json']:
 put(V/f,'source/'+f)
for f in ['bootstrap_native.py','final_technical_snapshot.py','verify_v3_intended_joint.py','inspect_tow_intersections.py','recover_v1_source.py','package_handoff.py']:
 put(R/f,'source/'+f)
put(R/'models/v1/build_scene_recovered.py','source/v1_build_scene_recovered.py');put(R/'models/v1/source_recovery.json','metadata/v1_source_recovery.json')
put(R/'models/v2/build_scene.py','source/v2_build_scene.py')
for f in ['scene.json','component_inventory.json','colliders.json','all36_cameras.json','frozen_label_check.json','native_structural_summary.json','intended_joint_diagnostic.json','contact_preparation_report.json']:
 put(V/f,'metadata/'+f)
for f in ['model_from_input.json','v3_layout_corrections.json','rgb_annotations.json','material_observations.json','measurement_raw.json','measurements_landmarks.json','measurement_summary.json','MEASUREMENT_HANDOFF.json']:
 put(R/f,'metadata/'+f)
put(R/'inputs/packet.json','metadata/input_packet.json');put(R/'camera_observations.json','metadata/camera_observations.json')
put(R/'native_case/runs/agent_observe/0001/furniture_observation.json','metadata/furniture_observation.json')
put(R/'native_case/runs/agent_observe/0001/observation.json','metadata/observation.json')
put(R/'inputs/depth_reference/manifest.json','metadata/input_depth_manifest.json');put(R/'inputs/depth_reference/REFERENCE_CONTRACT.md','metadata/REFERENCE_CONTRACT.md')
frozen=json.loads((R/'code/SOURCE_FROZEN.json').read_text());changed=['camera.py','media.py','blender_structure.py','structure.py','stage_worker.py']
for rel,expected in frozen['files'].items():
 p=R/'code'/rel;assert sha(p)==expected,rel
for p in (R/'code').rglob('*'):
 if p.is_file() and p.suffix in ['.py','.md','.toml','.json'] and '__pycache__' not in p.parts:
  put(p,'framework/code/'+str(p.relative_to(R/'code')))
for name in changed:put(R/'code/workflow/r2s'/name,'native_framework_delta/workflow/r2s/'+name)
put(R/'code/SOURCE_FROZEN.json','native_framework_delta/SOURCE_FROZEN.json')
write('native_framework_delta/delta_manifest.json',dict(base_revision='735be2f',scope='Coordinator final frozen support snapshot actually used; later coordinator fixes are not part of this execution',files={name:sha(R/'code/workflow/r2s'/name) for name in changed},author_changed_framework_guards=False))
for sub in ['root_v1','root_v2','root_v3']:
 folder=R/'independent_review'/sub
 if folder.exists():
  for name in ['review.json','review.md','camera_occlusion_audit.json']:
   if (folder/name).exists():put(folder/name,'independent_review/'+sub+'/'+name)
for label,rel in [('v1_paired','checks/v1_paired/report.json'),('v1_all_initial','checks/v1_all_initial/report.json'),('v2_paired','checks/v2_paired_retry1/report.json'),('v2_all_major_repair','checks/v2_all_major_repair/report.json'),('v3_paired','checks/v3_paired/report.json'),('v3_all_final','checks/v3_all_final/report.json')]:
 d=json.loads((R/rel).read_text());n=sum(x['domain_pixels'] for x in d['rows']);write('checks/'+label+'.json',{**{k:v for k,v in d.items() if k!='visible_inventory'},'original_report_sha256':sha(R/rel),'weighted_missing_penalty_mae_m':sum(x['missing_penalty_mae_m']*x['domain_pixels'] for x in d['rows'])/n})
state=json.loads((R/'native_case/runs/state.json').read_text());put(R/'native_case/case.json','native/case.json');write('native/state_snapshot.json',state)
for stage,entry in state['stages'].items():
 folder=Path(entry['directory'])
 if (folder/'response.json').exists():put(folder/'response.json','native/responses/'+stage+'.json')
for stage in ['agent_calibrate','agent_calibrate_room']:
 folder=Path(state['stages'][stage]['directory'])
 name='calibration.json' if stage=='agent_calibrate' else 'room_calibration.json';put(folder/name,'native/'+name)
costs=[]
for attempt in sorted((R/'native_case/runs/build_geometry').glob('*')):
 if not attempt.is_dir():continue
 images=[p.name for p in attempt.glob('*.png') if not p.name.startswith('furniture_original_crop')]
 row=dict(attempt=attempt.name,rendered_images=len(images),source_views=sum(n.startswith('source_view') for n in images),source_crops=sum(n.startswith('furniture_source_view') for n in images),isolated_and_combined=sum(n.startswith('structure_') for n in images),other_diagnostic=sum(not n.startswith(('source_view','furniture_source_view','structure_')) for n in images),images=images)
 if (attempt/'structural_audit.json').exists():
  a=json.loads((attempt/'structural_audit.json').read_text());row.update(structural_audit_sha256=sha(attempt/'structural_audit.json'),structural_status=a['status'],failure_counts=dict(collections.Counter(x['kind'] for x in a['failures'])),failures=a['failures'])
 costs.append(row)
write('native/native_cost_and_status_snapshot.json',dict(as_of=stamp,current_stage=state['stages']['build_geometry']['status'],attempts=costs,notes=['v2 executable timed out at1500s; partial artifacts preserved','v3 executable timeout2100s; native source resolution unchanged; diagnostic resolution384x384','The native worker may continue after this snapshot; no native acceptance is implied']))
for f in ['iteration_log.json','access.jsonl','visibility_compatibility.json']:
 if (R/'logs'/f).exists():put(R/'logs'/f,'logs/'+f)
put(R/'technical_export/appearance_and_lighting_candidate.json','technical/appearance_and_lighting_candidate.json');put(R/'technical_export/source_binding.json','technical/source_binding.json')
reload=json.loads((R/'technical_export/strict_reload_validation.json').read_text());write('technical/strict_reload_summary.json',dict(status=reload['status'],source_report_sha256=sha(R/'technical_export/strict_reload_validation.json'),sources_unchanged=reload.get('sources_unchanged'),records=[{k:r.get(k) for k in ['format','path','sha256','status','failures']} for r in reload['records']],interpretation='Blender roundtrip passed; GLB camera shift/FOV and USD stable part identity gates failed. No workaround or pass waiver applied.'))
geometry=json.loads((R/'technical_export/geometry_audit.json').read_text());write('technical/geometry_export_summary.json',dict(source_report_sha256=sha(R/'technical_export/geometry_audit.json'),enclosure_present=geometry['enclosure_present'],enclosure_hidden=geometry['enclosure_hidden'],units=geometry['units'],entities=len(geometry['entities']),warnings=geometry['warnings'],material_portability=geometry['material_portability'],scope='Technical export only; native export/validate stages remain blocked by geometry acceptance'))
report=f'''# OURS delivery-area reconstruction — LIMITED technical candidate

Selected immutable model SHA256: `{selected}`. The model remains remote at `models/v3/model.blend`; it is not included in this small archive. The selected editable scene contains801 visible mesh components,107 semantic entities,36 unchanged supplied cameras, and one recorded rigid model_from_input. No camera scale, per-frame pose correction, fused pointmap mesh, external stock mesh, heldout photo, laser geometry or GT depth was used by this author.

This is a scene-specific authored asset and an execution record, not a claim of a general automatic reconstruction algorithm. Custom construction includes full outer shell, internal partitions and columns, sliding-door components, pallet rack and sacks, wooden crates, two skips, two trailers, van and car, lumber cart, mesh cages, compactor, pipes and lighting. Unseen outer boundaries, backs and mechanical internals remain hypotheses.

## Native result at bundle time

The real Workflow.run/accept path completed ingest, preprocess, observation, identity, calibrated cameras, room calibration and model submission. build_geometry is `{state['stages']['build_geometry']['status']}` at {stamp}. Its actual v3 structural audit is FAILED: four unchanged source-endpoint gates and one undeclared intended tow/frame contact. The latter is retained as a contract failure; the diagnostic note is not a waiver. No native geometry-review pass has been asserted. Native material/light calibration, final visual acceptance, export/validate/report stages cannot be promoted past this gate. Assigned candidate PBR materials and lights are provisional, with their actual bindings and parameters included.

The exact remaining source endpoint failures are front skip median25.556/max41.010px; van median7.064/max33.556px; car median4.735/max27.566px; far cage median18.045/max30.598px. Frozen limits remain median9/max18px. Independent reviews selected v3 only for external MEASUREMENT as LIMITED; no independent physical accuracy result is available to this author.

## Checks and budget

Three authored full versions were created (maximum5). Fixed ten-view checks used30/50 budgeted pairs. One justified extra RGB pair reused the already-required native frame14 render to inspect windshield visibility (1/10 supplemental allowance). Exactly three full36-view input predicted-depth checks were run: initialv1, major-repairv2, finalv3. The final36-view domain has689349 pixels,99.9398% coverage and0.533454m missing-penalty MAE versus learned input depth; this is input consistency, not heldout/GT accuracy. All outcomes and input denominators are retained. A v2 checker attempt rejected fonts before rendering any views; identical text surfaces were realized and the retry was recorded.

CPU Blender4.5.3 with2 threads was used, with OMP/OPENBLAS set2 and R2S_CPU=1. Native-required diagnostic images are counted separately in native/native_cost_and_status_snapshot.json. v2 native build timed out after1500s with its failed audit,45 isolated/combined views,6 source crops and29 full-source renders retained. v3 uses384px diagnostic-only inspection views, unchanged full-source raster, and a2100s bounded executable timeout. This archive does not declare a running worker finished.

## Technical interchange boundary

Additional read-only technical export checks were run outside the blocked native acceptance path. Derived Blender reload PASSED. GLB strict reload FAILED camera FOV/shift preservation; USD strict reload FAILED32 stable-part identity checks. Those files are not certified interchange equivalents. The selected Blender model plus all36_cameras.json remain authoritative. Procedural Blender materials can flatten to simpler PBR approximations in GLB/USD. Mesh colliders and large model/export/audit files remain remote.

## Reproduction

Unpack this archive. With Blender4.5.3, run `blender -b --factory-startup --threads 2 --python replay_builder.py -- --root /new/empty/path`. The wrapper creates a NEW workspace, copies only camera/parameter/observation metadata and the exact native source snapshot, then executes the preserved final scene recipe and measured assembly declarations. It relocates the ROOT path only. It does not rerun source inference, use raw photos/depth, or grant native acceptance. Full protocol replay requires the original hash-pinned authorized inputs and actual agent stage reviews. The reconstructed .blend byte hash may differ due to embedded save paths/metadata; geometry identity must be checked separately if required.

The native framework is frozen atop coordinator base735be2f. Its exact SOURCE_FROZEN receipt and the five changed files camera.py,media.py,blender_structure.py,structure.py,stage_worker.py are included, along with the small full runtime source for portability. Later coordinator fixes were not used by this run.

The working v1 builder was overwritten before a separate source snapshot. Its source text was subsequently recovered by reversing this run's recorded edits and checking against the original creation record. No pre-run source hash exists, and a geometry replay proof was not completed; metadata/v1_source_recovery.json preserves this caveat. Original v1 model/GLB/check bytes were never overwritten. Final v3 source/parameters and selected model hashes are explicit.

No models, raw images/depth, inference weights,110MB structural audits, private chat or other-author material are included. Native state and cost records are timestamped snapshots; later completion/timeout belongs in a separately versioned final-state addendum.
'''
(P/'README.md').write_text(report)
entries=[]
for f in sorted(P.rglob('*')):
 if f.is_file():entries.append(dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=sha(f)))
write('MANIFEST.json',dict(schema='ours.small-handoff/1',as_of=stamp,selected_model_sha256=selected,files=entries,exclusions=['models','raw RGB/depth','weights','large raw audits','private chat','other-author files']))
archive=R/('OURS_small_bundle_'+stamp+'.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in sorted(P.rglob('*')):
  if f.is_file():z.write(f,str(f.relative_to(P)))
receipt=dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,manifest=str(P/'MANIFEST.json'),manifest_sha256=sha(P/'MANIFEST.json'),files=len(entries)+1,selected_model_sha256=selected,native_status_at_snapshot=state['stages']['build_geometry']['status'])
(R/'SMALL_BUNDLE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
