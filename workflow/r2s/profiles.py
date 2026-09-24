"""Versioned workflows: technical v1 and fidelity-first v2."""
LEGACY=[('ingest',[],False),('preprocess',['ingest'],False),('agent_observe',['preprocess'],True),('agent_identify',['agent_observe'],True),('agent_calibrate',['agent_observe','agent_identify'],True),('agent_model',['agent_calibrate','agent_identify'],True),('build_render',['agent_model'],False),('agent_review',['build_render','agent_observe'],True),('export',['agent_review','build_render','agent_model'],False),('validate',['export','agent_calibrate'],False),('report',['validate','agent_review'],False)]

def physics_options(config):
    value=config.get('physics',{})
    result={k:value.get(k,False) for k in ['hinges','cloth','soft_bodies']}
    if any(type(v) is not bool for v in result.values()):raise ValueError('Physics switches must be booleans')
    return result

def stages_for(config):
    profile=config.get('workflow_profile','legacy_v1')
    if profile=='legacy_v1':return list(LEGACY)
    if profile!='quality_v2':raise ValueError('Unknown workflow_profile')
    stages=[('ingest',[],False),('preprocess',['ingest'],False),
      ('agent_observe',['preprocess'],True),('agent_identify',['agent_observe'],True),
      ('agent_calibrate',['agent_observe','agent_identify'],True),
      ('agent_calibrate_room',['agent_calibrate','agent_observe'],True),
      ('agent_model',['agent_calibrate_room','agent_calibrate','agent_identify','agent_observe'],True),
      ('build_geometry',['agent_model'],False),
      ('agent_review_geometry',['build_geometry','agent_observe','agent_calibrate_room'],True),
      ('agent_materials',['agent_review_geometry','agent_model','agent_observe'],True),
      ('agent_calibrate_lighting',['agent_materials','agent_review_geometry','agent_calibrate_room','agent_observe'],True),
      ('build_render',['agent_calibrate_lighting','agent_materials','agent_model'],False),
      ('agent_review',['build_render','agent_review_geometry','agent_calibrate_lighting','agent_materials','agent_observe'],True)]
    physical=any(physics_options(config).values())
    if physical:stages.append(('agent_physics',['agent_review','agent_calibrate_lighting','agent_materials','agent_model'],True))
    stages.append(('export',(['agent_physics'] if physical else [])+['agent_review','build_render','agent_calibrate_lighting','agent_materials','agent_model'],False))
    stages.append(('validate',['export','agent_calibrate'],False))
    if physical:stages.append(('agent_review_physics',['validate','agent_physics','agent_review'],True))
    stages.append(('report',['validate','agent_review']+(['agent_review_physics'] if physical else []),False))
    return stages
