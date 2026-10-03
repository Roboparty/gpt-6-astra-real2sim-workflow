"""Validate agent-supplied web evidence locally; never fetch URLs or call models.

Dimensions are sourced priors, not measurements of the photographed instance.
This checks evidence integrity and declared provenance, not a publisher's truth
or whether a quoted product really matches the photograph.
"""
import copy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
from urllib.parse import urlsplit

SCHEMA = 'real2sim.web-research/1'
SOURCE_TYPES = {'manufacturer', 'official_product_page', 'official_manual', 'standards_body', 'research_paper'}
IDENTITIES = {'exact_product', 'family', 'category', 'unknown'}
AXES = ['width', 'depth', 'height']
UNIT_SCALE = {'mm': .001, 'cm': .01, 'm': 1.}


class WebResearchError(ValueError):
    pass


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise WebResearchError(label + ' must be a nonempty string')
    return value


def _rows(value, label):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise WebResearchError(label + ' must be a list of objects')
    return value


def _unique(rows, key, label):
    ids = [_text(row.get(key), label + '.' + key) for row in rows]
    if len(ids) != len(set(ids)):
        raise WebResearchError('Duplicate ' + label + ' identifiers')
    return set(ids)


def _snapshot_path(value, base):
    value = _text(value, 'snapshot_path')
    path = Path(value)
    if path.is_absolute() or PureWindowsPath(value).drive or '..' in value.replace('\\', '/').split('/') or '\\' in value:
        raise WebResearchError('Snapshot must use a contained relative path without traversal')
    base = Path(base).resolve(); resolved = (base/path).resolve()
    if not resolved.is_relative_to(base) or resolved == base:
        raise WebResearchError('Snapshot escapes artifact base')
    return resolved


def evidence_paths(bundle, base):
    """Return sorted absolute snapshot Paths for cache binding, including missing files.

    Reject escaping paths even for fingerprints. Call validate_bundle separately
    to verify content hashes. The caller also binds web_research.json itself.
    """
    if not isinstance(bundle, dict):
        raise WebResearchError('Bundle must be an object')
    return sorted({_snapshot_path(source.get('snapshot_path'), base)
                   for source in _rows(bundle.get('sources'), 'sources')}, key=str)


def _validate_bundle(bundle, base, *, max_queries=8, max_sources=12):
    """Return a JSON-serializable normalized report, or raise WebResearchError.

    Unknown identity/shipping values remain in objects[].priors as ineligible.
    Conflicting object dimensions remain available for review but none is selected
    into model_priors. No network, file mutations, or model installation occurs.
    """
    if not isinstance(bundle, dict) or bundle.get('schema') != SCHEMA:
        raise WebResearchError('Expected ' + SCHEMA)
    for label, limit in [('max_queries', max_queries), ('max_sources', max_sources)]:
        if type(limit) is not int or not 0 <= limit <= 100:
            raise WebResearchError(label + ' must be an integer in [0,100]')
    queries = _rows(bundle.get('queries'), 'queries'); sources = _rows(bundle.get('sources'), 'sources')
    objects = _rows(bundle.get('objects'), 'objects')
    if not objects:
        raise WebResearchError('At least one explicit object identity is required')
    if len(queries) > max_queries or len(sources) > max_sources:
        raise WebResearchError('Web query/source budget exceeded; retain all attempts')
    _unique(queries, 'id', 'queries'); source_ids = _unique(sources, 'id', 'sources')
    _unique(objects, 'object_id', 'objects')
    for query in queries:
        _text(query.get('query'), 'query')
    if sources and not queries:
        raise WebResearchError('Sources require an explicit query ledger')
    verified_sources = []
    for source in sources:
        url = _text(source.get('url'), 'source.url')
        parsed = urlsplit(url)
        parsed.port  # Validate malformed/non-numeric ports without any network access.
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in url):
            raise WebResearchError('Source URL must be an absolute HTTPS URL without credentials')
        for field in ['title', 'publisher']:
            _text(source.get(field), 'source.' + field)
        if source.get('type') not in SOURCE_TYPES:
            raise WebResearchError('Unsupported source type; expected declared primary source kind')
        try:
            timestamp = datetime.fromisoformat(_text(source.get('retrieved_at'), 'retrieved_at').replace('Z', '+00:00'))
        except ValueError as exc:
            raise WebResearchError('retrieved_at must be an ISO timestamp') from exc
        if timestamp.utcoffset() is None:
            raise WebResearchError('retrieved_at needs an explicit timezone')
        sha = source.get('snapshot_sha256')
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise WebResearchError('snapshot_sha256 must be a lowercase SHA256')
        path = _snapshot_path(source.get('snapshot_path'), base)
        if not path.is_file() or path.stat().st_size > 2*1024*1024:
            raise WebResearchError('Snapshot missing or exceeds 2 MiB text-evidence limit')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha:
            raise WebResearchError('Snapshot hash mismatch: ' + source['id'])
        try:
            text = payload.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise WebResearchError('Snapshot is not UTF-8 text') from exc
        if not text.strip() or '\x00' in text:
            raise WebResearchError('Snapshot is empty or binary-like')
        verified_sources.append(dict(source, snapshot_absolute_path=str(path), snapshot_bytes=len(payload),
                                     snapshot_verified=True, authority_status='declared_not_independently_verified'))
    normalized = []; model_priors = []; model_details = []; conflicts = []
    for obj in objects:
        identity = obj.get('identity_match')
        if identity not in IDENTITIES:
            raise WebResearchError('Unsupported identity_match')
        unresolved = obj.get('unresolved')
        if not isinstance(unresolved, list) or any(not isinstance(x, str) or not x.strip() for x in unresolved):
            raise WebResearchError('unresolved must be an explicit list of nonempty strings')
        if identity == 'unknown' and not unresolved:
            raise WebResearchError('Unknown identity requires an unresolved reason')
        records = []
        for prior in _rows(obj.get('priors'), 'priors'):
            if prior.get('parameter') != 'dimensions' or prior.get('status') != 'sourced_prior':
                raise WebResearchError('Only explicitly sourced_prior dimensions are supported')
            if prior.get('source_id') not in source_ids:
                raise WebResearchError('Prior references a missing source')
            _text(prior.get('claim_locator'), 'claim_locator')
            unit = prior.get('unit'); axes = prior.get('axis_order'); values = prior.get('value')
            if unit not in UNIT_SCALE:
                raise WebResearchError('Unsupported dimension unit')
            if not isinstance(axes, list) or len(axes) != 3 or any(not isinstance(x, str) for x in axes) or set(axes) != set(AXES):
                raise WebResearchError('axis_order must be a permutation of width, depth, height')
            if not isinstance(values, list) or len(values) != 3 or any(type(x) not in (float, int) or not math.isfinite(x) or x <= 0 for x in values):
                raise WebResearchError('Dimensions must contain three finite positive numbers')
            if 'uncertainty_fraction' not in prior:
                raise WebResearchError('uncertainty_fraction must be explicit, including when null')
            uncertainty = prior['uncertainty_fraction']
            if uncertainty is None:
                _text(prior.get('uncertainty_note'), 'Null uncertainty_fraction requires uncertainty_note')
            elif type(uncertainty) not in (float, int) or not math.isfinite(uncertainty) or uncertainty < 0:
                raise WebResearchError('uncertainty_fraction must be finite and nonnegative, or explicitly null with a note')
            if 'uncertainty_note' in prior:
                _text(prior['uncertainty_note'], 'uncertainty_note')
            kind = prior.get('dimension_kind')
            if kind not in {'object', 'shipping_package'}:
                raise WebResearchError('dimension_kind must distinguish object from shipping_package')
            # Forbid submitted derived fields that could contradict the gate.
            if any(k in prior for k in ['dimensions_m', 'value_m', 'model_eligible', 'instance_measurement', 'exact_dimensions']):
                raise WebResearchError('Derived dimension/eligibility claims must be produced by the validator')
            eligible = kind == 'object' and identity != 'unknown'
            value_m = [values[axes.index(axis)]*UNIT_SCALE[unit] for axis in AXES] if eligible else None
            if value_m is not None and not all(math.isfinite(v) and v > 0 for v in value_m):
                raise WebResearchError('Normalized dimensions overflow or underflow')
            record = dict(copy.deepcopy(prior), dimensions_m=value_m, normalized_axis_order=AXES[:],
                          uncertainty_status='unquantified' if uncertainty is None else 'declared_fraction',
                          source_status='prior_not_instance_measurement', model_eligible=eligible,
                          ineligible_reasons=(['shipping_package_not_object'] if kind == 'shipping_package' else []) +
                                             (['unknown_identity_not_transferable'] if identity == 'unknown' else []))
            records.append(record)
        candidates = [r for r in records if r['model_eligible']]
        different = candidates and any(any(not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
                        for a, b in zip(candidates[0]['dimensions_m'], r['dimensions_m'])) for r in candidates[1:])
        if different:
            conflicts.append(dict(object_id=obj['object_id'], parameter='dimensions',
                source_ids=[r['source_id'] for r in candidates], values_m=[r['dimensions_m'] for r in candidates],
                resolution='unresolved_no_automatic_selection', rule='Distinct values retained even if uncertainty ranges overlap'))
            for record in candidates:
                record['model_eligible'] = False; record['ineligible_reasons'].append('unresolved_source_conflict')
        details = []
        for detail in _rows(obj.get('details', []), 'details'):
            for field in ['parameter', 'value', 'claim_locator', 'uncertainty_note']:
                _text(detail.get(field), 'detail.'+field)
            if detail['parameter'].strip().casefold() == 'dimensions':
                raise WebResearchError('dimensions is reserved for numeric priors, not text details')
            if detail.get('status') != 'sourced_prior':
                raise WebResearchError('Details require explicit sourced_prior status')
            if detail.get('source_id') not in source_ids:
                raise WebResearchError('Detail references a missing source')
            if any(k in detail for k in ['model_eligible', 'instance_measurement', 'dimensions_m', 'value_m']):
                raise WebResearchError('Details cannot provide derived numeric dimensions or eligibility claims')
            details.append(dict(copy.deepcopy(detail), model_eligible=identity != 'unknown',
                                source_status='prior_not_instance_measurement',
                                ineligible_reasons=['unknown_identity_not_transferable'] if identity == 'unknown' else []))
        normalized.append(dict(object_id=obj['object_id'], identity_match=identity, priors=records,
                               details=details, unresolved=unresolved[:]))
        model_priors.extend(dict(record, object_id=obj['object_id'], identity_match=identity)
                            for record in records if record['model_eligible'])
        model_details.extend(dict(detail, object_id=obj['object_id'], identity_match=identity)
                             for detail in details if detail['model_eligible'])
    return dict(schema='real2sim.web-research-report/1', status='validated', source_status='prior_not_instance_measurement',
                queries=copy.deepcopy(queries), sources=verified_sources, objects=normalized,
                model_priors=model_priors, model_details=model_details,
                conflicts=conflicts, budget=dict(queries_used=len(queries), sources_used=len(sources),
                    max_queries=max_queries, max_sources=max_sources),
                factual_claim_validation='not_performed; snapshot integrity does not verify identity or claim interpretation',
                detail_conflict_policy='All eligible text claims retained without ranking; semantic compatibility is not inferred')


def validate_bundle(bundle, base, *, max_queries=8, max_sources=12):
    """Validate/normalize local evidence; all invalid bundles raise WebResearchError."""
    try:
        return _validate_bundle(bundle, base, max_queries=max_queries, max_sources=max_sources)
    except WebResearchError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise WebResearchError('Malformed web evidence: '+str(exc)) from exc


def main(packet_path):
    """Executable validate_web_research stage; invalid evidence becomes needs_input."""
    packet = json.loads(Path(packet_path).read_text(encoding='utf-8-sig'))
    out = Path(packet['output_directory']); out.mkdir(parents=True, exist_ok=True)
    try:
        accepted_artifacts = packet.get('input_artifacts', {}).get('agent_identify', [])
        artifacts = [a for a in accepted_artifacts
                     if Path(a['path']).name == 'web_research.json']
        if len(artifacts) != 1:
            raise WebResearchError('Exactly one agent_identify/web_research.json artifact is required')
        artifact = artifacts[0]; path = Path(artifact['path']); raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if not isinstance(artifact.get('sha256'), str) or artifact['sha256'] != sha:
            raise WebResearchError('web_research.json differs from its accepted artifact hash')
        bundle = json.loads(raw.decode('utf-8-sig')); params = packet.get('parameters', {})
        report = validate_bundle(bundle, path.parent, max_queries=params.get('max_queries', 8), max_sources=params.get('max_sources', 12))
        for snapshot in evidence_paths(bundle, path.parent):
            delivered = [a for a in accepted_artifacts if Path(a['path']).resolve() == snapshot]
            if len(delivered) != 1 or delivered[0].get('sha256') != hashlib.sha256(snapshot.read_bytes()).hexdigest():
                raise WebResearchError('Snapshot must be declared exactly once with its accepted hash in agent_identify outputs: '+snapshot.name)
        report['bundle_sha256'] = sha; status = 'complete'
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report = dict(schema='real2sim.web-research-report/1', status='needs_input', error=str(exc),
                      source_status='unverified', model_priors=[], model_details=[], conflicts=[])
        status = 'needs_input'
    (out/'web_research_report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    response = dict(status=status, artifacts=['web_research_report.json'],
                    evidence=['Local snapshot/hash/provenance validation only; no network or model call'],
                    reasoning_summary='Sourced priors retain identity uncertainty, shipping distinctions and unresolved conflicts.')
    (out/'response.json').write_text(json.dumps(response, indent=2), encoding='utf-8')
    return response


if __name__ == '__main__':
    main(sys.argv[1])
