"""Content-addressed attempts, explicit Agent gates, retry and dependency-aware resume."""
import json,os,time,shutil,subprocess,traceback,signal
from pathlib import Path
from datetime import datetime,timezone
from .contracts import ContractError,digest,scene_check
from .media import file_hash,ingest,preprocess

from .profiles import LEGACY, stages_for, physics_options
from .quality import check_quality_stage
from .refinement import REVIEW_STAGES, limits, check_response
STAGES=LEGACY
STAGE_MAP={n:(deps,agent) for n,deps,agent in STAGES}

def now():return datetime.now(timezone.utc).isoformat()
def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)
def safe_path(base,relative):
    p=(Path(base)/relative).resolve()
    if not p.is_relative_to(Path(base).resolve()):raise ContractError('Artifact path escapes attempt directory')
    return p

def run_command(argv,cwd,env,timeout):
    """Own a process group so a timed-out worker cannot leave Blender running."""
    options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
    proc=subprocess.Popen(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,shell=False,**options)
    try:stdout,stderr=proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
            if proc.poll() is None:proc.kill()
        else:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        stdout,stderr=proc.communicate()
        Path(cwd,'stdout.log').write_text(stdout);Path(cwd,'stderr.log').write_text(stderr)
        raise
    return subprocess.CompletedProcess(argv,proc.returncode,stdout,stderr)

class Workflow:
    def __init__(self,case):
        self.case=Path(case).resolve();self.config=json.loads((self.case/'case.json').read_text());self.root=self.case/'runs';self.root.mkdir(exist_ok=True)
        self.stages=stages_for(self.config);self.stage_map={n:(deps,agent) for n,deps,agent in self.stages}
        self.state_path=self.root/'state.json';self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'case_id':self.config['id'],'stages':{},'created':now()}
        self.refining='refinement' in self.config
        if self.refining:
            limits(self.config)
            if self.config.get('workflow_profile')!='quality_v2':raise ContractError('Refinement requires quality_v2')
    def save(self):atomic_json(self.state_path,self.state)
    def event(self,data):
        with (self.root/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'time':now(),**data},ensure_ascii=False)+'\n')
    def fingerprint(self,name):
        deps,_=self.stage_map[name];up={d:self.state['stages'][d]['outputs'] for d in deps};config=self.config.get('stages',{}).get(name,{})
        if name=='ingest':config={k:self.config.get(k) for k in ['mode','inputs','provenance','formal_test']};config['actual_input_hashes']=[file_hash(x['path']) for x in self.config['inputs']]
        source_root=Path(__file__).parent
        source_hash=digest({str(p.relative_to(source_root)):file_hash(p) for p in source_root.rglob('*') if p.is_file() and p.suffix in {'.py','.md'}})
        return digest({'stage':name,'upstream':up,'config':config,'implementation':source_hash,'branch':self.config.get('branch','A'),'workflow_profile':self.config.get('workflow_profile','legacy_v1'),'physics_options':physics_options(self.config),'refinement_enabled':self.refining,'surface_contract_version':limits(self.config)['surface_contract_version'] if self.refining else 0,'revision_epoch':self.state.get('revision_epochs',{}).get(name,0)})
    def valid(self,name):
        item=self.state['stages'].get(name)
        if not item or item['status']!='succeeded':return False
        if any(not self.valid(d) for d in self.stage_map[name][0]):return False
        if item.get('fingerprint')!=self.fingerprint(name):return False
        return all(Path(o['path']).is_file() and file_hash(o['path'])==o['sha256'] for o in item['outputs'])
    def upstream(self,name):
        return {d:self.state['stages'][d]['outputs'] for d in self.stage_map[name][0]}
    def packet(self,name,attempt):
        deps,_=self.stage_map[name]
        return {'schema':'real2sim.agent-packet/1.0','case_id':self.config['id'],'stage':name,'branch':self.config.get('branch','A'),'mode':self.config['mode'],'workflow_profile':self.config.get('workflow_profile','legacy_v1'),'physics_options':physics_options(self.config),'input_artifacts':self.upstream(name),'original_input_allowlist':[e['path'] for e in self.config['inputs']],'parameters':self.config.get('stages',{}).get(name,{}).get('parameters',{}),'output_directory':str(attempt),'instruction_file':str(Path(__file__).parent/'prompts'/(name+'.md')),'constraints':{'no_previous_project_artifacts':True,'formal_real_photography_only':True,'four_walls_floor_ceiling_luminaires_required':True,'external_geometry_allowed':self.config.get('branch','A')=='B','exact_assets_only':True,'unknown_identity_fallback':'A','validation_truth_access':False,'observed_layout_immutable_to_generative_repair':True},'response_contract':{'status':'complete | changes_requested | needs_input','evidence':'nonempty list of evidence records','reasoning_summary':'concise auditable rationale, not private chain of thought','parameters':'estimation and construction parameters','artifacts':'list of paths relative to output_directory','issues':'unresolved issues; never hide failure'}}
    def _finish(self,name,attempt,response):
        if any(not self.valid(dep) for dep in self.stage_map[name][0]):raise ContractError('Upstream artifacts changed while the stage was running')
        if response.get('status') not in {'complete','changes_requested','needs_input'}:raise ContractError('Unknown response status')
        candidate=check_response(self,name,attempt,response) if self.refining else None
        artifacts=response.get('artifacts',[])
        outputs=[]
        for rel in artifacts:
            p=safe_path(attempt,rel)
            if not p.is_file():raise ContractError('Missing artifact: '+str(p))
            outputs.append({'path':str(p),'sha256':file_hash(p),'bytes':p.stat().st_size})
        if response.get('status')!='complete':
            if candidate:self.record_candidate(name,attempt,response,outputs,*candidate)
            item=self.state['stages'][name];item.update(status=response['status'],response=response,outputs=outputs,finished=now());atomic_json(attempt/'record.json',item);self.save();self.event({'stage':name,'status':item['status']});return False
        if self.stage_map[name][1] and (not response.get('evidence') or not response.get('reasoning_summary')):raise ContractError('Agent output lacks explicit evidence or rationale')
        if name=='agent_review' and any(i.get('blocking') for i in response.get('issues',[]) if isinstance(i,dict)):raise ContractError('Blocking visual issues cannot be marked complete')
        check_quality_stage(name,attempt,response,self.config.get('workflow_profile','legacy_v1'))
        if not artifacts:raise ContractError('Stage cannot complete without artifacts')
        for rel in artifacts:
            p=safe_path(attempt,rel)
            if p.name.startswith('scene') and p.suffix=='.json':scene_check(json.loads(p.read_text()))
        if candidate:self.record_candidate(name,attempt,response,outputs,*candidate)
        item=self.state['stages'][name];item.update(status='succeeded',outputs=outputs,response=response,finished=now());atomic_json(attempt/'record.json',item);self.save();self.event({'stage':name,'status':'succeeded','attempt':item['attempt']});return True
    def accept(self,name,response_file):
        item=self.state['stages'].get(name)
        allowed={'awaiting_agent','needs_input'} if self.refining else {'awaiting_agent','changes_requested','needs_input'}
        if not item or item['status'] not in allowed:raise ContractError('No pending Agent stage; reviewed attempts are immutable')
        if item['fingerprint']!=self.fingerprint(name):raise ContractError('Inputs changed while Agent worked; stage must be reissued')
        return self._finish(name,Path(item['directory']),json.loads(Path(response_file).read_text()))
    def execute(self,name,retry=False):
        if self.valid(name):return 'cached'
        for d in self.stage_map[name][0]:
            if not self.valid(d):raise ContractError('Upstream stage not valid: '+d)
        old=self.state['stages'].get(name,{})
        if old.get('status') in {'awaiting_agent','needs_input','changes_requested'} and old.get('fingerprint')==self.fingerprint(name) and not retry:return old['status']
        number=old.get('attempt',0)+1;attempt=self.root/name/f'{number:04d}';attempt.mkdir(parents=True,exist_ok=False)
        item={'stage':name,'attempt':number,'directory':str(attempt),'status':'running','started':now(),'fingerprint':self.fingerprint(name),'inputs':self.upstream(name),'parameters':self.config.get('stages',{}).get(name,{}).get('parameters',{}),'outputs':[]};self.state['stages'][name]=item;self.save();self.event({'stage':name,'status':'running','attempt':number})
        try:
            cfg=self.config.get('stages',{}).get(name,{})
            if name=='ingest':
                ingested=ingest(self.config,attempt);return 'succeeded' if self._finish(name,attempt,{'status':'complete','artifacts':['ingest.json']+[Path(r['path']).name for r in ingested['files']],'evidence':['original byte hashes, decode verification']}) else 'failed'
            if name=='preprocess':
                inp=json.loads(Path(self.state['stages']['ingest']['outputs'][0]['path']).read_text());processed=preprocess(inp,attempt,cfg.get('parameters'));return 'succeeded' if self._finish(name,attempt,{'status':'complete','artifacts':['preprocess.json']+[Path(r['path']).name for r in processed['accepted']],'evidence':['original frame sampling and feature correspondences']}) else 'failed'
            packet=self.packet(name,attempt);packet['revision_request']=self.state.get('revision_requests',{}).get(name)
            if self.refining:
                targets=[]
                sources=[{'path':x['path'],'sha256':file_hash(x['path'])} for x in self.config['inputs']] if self.config['mode']!='video' else []
                for a in self.state['stages'].get('preprocess',{}).get('outputs',[]):
                    if Path(a['path']).name=='preprocess.json':sources+=json.loads(Path(a['path']).read_text())['accepted']
                primary=sources[0] if sources and self.config['mode']!='video' else None
                for a in self.state['stages'].get('agent_observe',{}).get('outputs',[]):
                    if Path(a['path']).name=='observation.json':
                        observed=json.loads(Path(a['path']).read_text());targets=observed.get('appearance_targets',[]);primary=observed.get('appearance_source',primary)
                packet.update(appearance_targets=targets,appearance_source=primary,comparison_inputs=sources,refinement={'limits':limits(self.config),'history':self.state.get('refinement',{}),'instruction_file':str(Path(__file__).parent/'prompts/refinement.md')})
            atomic_json(attempt/'packet.json',packet)
            if self.stage_map[name][1]:
                command=self.config.get('agent_command')
                if not command:item['status']='awaiting_agent';self.save();return item['status']
                # Fail closed when secret validation truth exists unless an isolation wrapper is configured.
                if self.config.get('sealed_validation') and not self.config.get('agent_isolation_command'):raise ContractError('Sealed validation requires an explicit filesystem isolation wrapper for external agents')
            else:command=cfg.get('command')
            if not command:raise ContractError('Executable stage command is not configured: '+name)
            if not isinstance(command,list):raise ContractError('Commands must be argv arrays, never shell strings')
            argv=[v.replace('{packet}',str(attempt/'packet.json')).replace('{output}',str(attempt)).replace('{case}',str(self.case)) for v in command]
            if self.stage_map[name][1] and self.config.get('agent_isolation_command'):argv=self.config['agent_isolation_command']+argv
            # Stage cwd differs from the caller. A relative PYTHONPATH could resolve
            # to an unrelated installed workflow; bind children to this exact snapshot.
            env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parent.parent)
            timeout=cfg.get('timeout_seconds',3600)
            if self.refining:timeout=min(timeout,max(1,limits(self.config)['max_seconds']-self.state.get('refinement',{}).get('elapsed_seconds',0)))
            proc=run_command(argv,attempt,env,timeout)
            (attempt/'stdout.log').write_text(proc.stdout);(attempt/'stderr.log').write_text(proc.stderr)
            if proc.returncode:raise RuntimeError(f'Stage command exited {proc.returncode}; see attempt logs')
            response_path=attempt/'response.json'
            if not response_path.exists():raise ContractError('Process exited without a response artifact; zero exit code is not sufficient')
            return 'succeeded' if self._finish(name,attempt,json.loads(response_path.read_text())) else self.state['stages'][name]['status']
        except Exception as exc:
            item.update(status='failed',finished=now(),error=str(exc));(attempt/'error.log').write_text(traceback.format_exc());atomic_json(attempt/'record.json',item);self.save();self.event({'stage':name,'status':'failed','error':str(exc)});raise
    def run(self,until=None,retry_failed=False):
        if until is not None and until not in self.stage_map:raise ContractError('Unknown stop stage')
        lock=self.root/'run.lock'
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise ContractError('Another run holds the case lock; inspect run.lock before explicit recovery')
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        try:
            while True:
                for name,_,_ in self.stages:
                    if self.refining and not self.valid(name) and self.state.get('refinement',{}).get('elapsed_seconds',0)>=limits(self.config)['max_seconds']:return self.stop_refinement(name,'time_budget')
                    started=time.monotonic();timeout_error=None
                    try:result=self.execute(name,retry=retry_failed)
                    except subprocess.TimeoutExpired as exc:timeout_error=exc
                    finally:
                        if self.refining:
                            history=self.state.setdefault('refinement',{});history['elapsed_seconds']=history.get('elapsed_seconds',0)+time.monotonic()-started;self.save()
                    if timeout_error:
                        if self.refining and self.state['refinement']['elapsed_seconds']>=limits(self.config)['max_seconds']:return self.stop_refinement(name,'time_budget')
                        raise timeout_error
                    if result=='changes_requested' and self.refining:
                        stopped=self.route_revision(name)
                        if stopped:return stopped
                        break
                    if result not in {'cached','succeeded'}:return {'status':result,'stage':name,'directory':self.state['stages'][name]['directory']}
                    if name==until:return {'status':'completed_until','stage':name}
                else:return {'status':'succeeded'}
        finally:lock.unlink()
    def freeze(self):
        if not {'validate','report'}<=set(self.stage_map):raise ContractError('A partial workflow cannot be frozen as a full delivery')
        missing=[n for n,_,_ in self.stages if not self.valid(n)]
        if missing:raise ContractError('Cannot freeze with incomplete or stale required stages: '+', '.join(missing))
        record={'case_id':self.config['id'],'frozen_at':now(),'outputs':{n:v['outputs'] for n,v in self.state['stages'].items() if self.valid(n)}};record['sha256']=digest(record);atomic_json(self.root/'freeze.json',record);return record
    def revise(self,name,reason):
        if name not in self.stage_map:raise ContractError('Unknown stage')
        if self.refining and name in {'agent_observe','agent_calibrate','agent_calibrate_room'}:
            for review_stage in REVIEW_STAGES:
                h=self.state.get('refinement',{}).get(review_stage,{})
                if h.get('best'):h.setdefault('archived_best',[]).append(h.pop('best'))
                h['stagnant']=0
        self.state.setdefault('revision_epochs',{})[name]=self.state.get('revision_epochs',{}).get(name,0)+1
        self.state.setdefault('revision_requests',{})[name]={'reason':reason,'time':now()}
        affected={name}
        for n,deps,_ in self.stages:
            if any(d in affected for d in deps):affected.add(n)
        for n in affected:
            if n in self.state['stages']:self.state['stages'][n]['status']='stale'
        self.save();self.event({'action':'revision_requested','stage':name,'affected':sorted(affected),'reason':reason});return sorted(affected)

    def record_candidate(self,name,attempt,response,outputs,data,binding):
        history=self.state.setdefault('refinement',{}).setdefault(name,{'stagnant':0})
        candidate={'directory':str(attempt),'review_sha256':file_hash(attempt/'appearance_review.json'),'protocol_sha256':binding['protocol_sha256'],'image_hashes':list(binding['images'].values()),'artifacts':outputs,'status':response['status'],'source_stages':{n:dict(v) for n,v in self.state['stages'].items() if self.valid(n)}}
        # References to immutable attempts preserve large models without duplicating them.
        atomic_json(attempt/'candidate.json',candidate)
        if data['comparison']['relation'] in {'baseline','better'}:
            history['best']=candidate;history['stagnant']=0
        else:history['stagnant']+=1
        history['latest']=str(attempt/'candidate.json')

    def stop_refinement(self,name,reason):
        item=self.state['stages'].get(name,{})
        result={'status':'needs_revision','stage':name,'reason':reason,'directory':item.get('directory'),'issues':item.get('response',{}).get('issues',[]),'best_candidates':{n:h['best']['directory'] for n,h in self.state.get('refinement',{}).items() if isinstance(h,dict) and 'best' in h}}
        self.state.setdefault('refinement',{})['stop']=result;self.save();self.event(result);return result

    def route_revision(self,name):
        history=self.state.setdefault('refinement',{});policy=limits(self.config)
        if history.get('revisions',0)>=policy['max_revisions']:return self.stop_refinement(name,'revision_budget')
        if history.get(name,{}).get('stagnant',0)>=policy['max_stagnant']:return self.stop_refinement(name,'no_visual_improvement')
        request=self.state['stages'][name]['response']['revision'];history['revisions']=history.get('revisions',0)+1;history.pop('stop',None)
        self.revise(request['stage'],request['reason'])
        self.state['revision_requests'][request['stage']].update(request,review_stage=name,review_directory=self.state['stages'][name]['directory'],change_method_required=history.get(name,{}).get('stagnant',0)>=2)
        self.save()
