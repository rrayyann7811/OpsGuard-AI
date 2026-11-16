"""Strict agent output, then application attribution validation. No generated patches."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.agent_evidence import sanitize


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Finding(StrictModel):
    classification: Literal['verified_fact','hypothesis','uncertain','recommendation']
    statement: str = Field(min_length=3, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class Location(StrictModel):
    path: str = Field(min_length=1, max_length=256)
    start_line: int = Field(ge=1, strict=True)
    end_line: int = Field(ge=1, strict=True)
    evidence_id: str


class CommitReference(StrictModel):
    commit_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    evidence_id: str
    explanation: str = Field(min_length=3, max_length=1500)


class HistoricalReference(StrictModel):
    historical_id: str
    evidence_id: str


class AgentAnalysis(StrictModel):
    error_summary: str = Field(min_length=3, max_length=3000)
    suspected_root_cause: Finding
    verified_facts: list[Finding] = Field(max_length=12)
    explanation: list[Finding] = Field(max_length=12)
    affected_files: list[Location] = Field(max_length=12)
    suspected_commits: list[CommitReference] = Field(max_length=6)
    historical_references: list[HistoricalReference] = Field(max_length=6)
    recommended_remediation: list[Finding] = Field(max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=12)


def validate_analysis(raw, evidence, limitations):
    analysis = AgentAnalysis.model_validate(raw)
    def redact_values(value):
        if isinstance(value,str): return sanitize(value)
        if isinstance(value,list): return [redact_values(item) for item in value]
        if isinstance(value,dict): return {key:redact_values(item) for key,item in value.items()}
        return value
    analysis = AgentAnalysis.model_validate(redact_values(analysis.model_dump()))
    by_id = {item['id']:item for item in evidence}
    findings = [analysis.suspected_root_cause, *analysis.verified_facts, *analysis.explanation, *analysis.recommended_remediation]
    if analysis.suspected_root_cause.classification not in ('hypothesis','uncertain'):
        raise ValueError('Root cause must be a hypothesis, not a verified causal conclusion')
    if any(item.classification != 'verified_fact' for item in analysis.verified_facts):
        raise ValueError('Verified fact classification mismatch')
    if any(item.classification != 'recommendation' for item in analysis.recommended_remediation):
        raise ValueError('Remediation must be a conceptual recommendation')
    for finding in findings:
        if any(id not in by_id for id in finding.evidence_ids):
            raise ValueError('Unknown evidence citation')
    for location in analysis.affected_files:
        item = by_id.get(location.evidence_id, {})
        if item.get('kind') != 'source' or location.path != item.get('path') or not item['start_line'] <= location.start_line <= location.end_line <= item['end_line']:
            raise ValueError('Unverified code location')
    for commit in analysis.suspected_commits:
        item = by_id.get(commit.evidence_id, {})
        if item.get('kind') != 'git' or commit.commit_sha != item.get('commit_sha'):
            raise ValueError('Unverified Git commit')
    for history in analysis.historical_references:
        item = by_id.get(history.evidence_id, {})
        if item.get('kind') != 'historical' or history.historical_id != item.get('historical_id'):
            raise ValueError('Unverified historical source')
    # Prevent uncited inline paths, hashes, or alleged code line numbers in prose.
    allowed_paths = {item['path'] for item in evidence if item['kind']=='source'}
    allowed_basenames = {path.rsplit('/',1)[-1] for path in allowed_paths}
    allowed_hashes = {item.get('commit_sha') for item in evidence if item['kind']=='git'}
    prose = '\n'.join([finding.statement for finding in findings] + [analysis.error_summary] + analysis.limitations + [item.explanation for item in analysis.suspected_commits])
    if re.search(r'diff --git|\*\*\* Begin Patch|```', prose):
        raise ValueError('Generated patch/code blocks are not allowed')
    for path in re.findall(r'(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:js|ts|mjs|cjs|py)\b', prose):
        if path not in allowed_paths and path not in allowed_basenames and path not in ('Node.js','node.js'):
            raise ValueError('Unknown inline file reference')
    for sha in re.findall(r'\b[0-9a-f]{40}\b', prose):
        if sha not in allowed_hashes: raise ValueError('Unknown inline commit reference')
    # Numerical code references must be in validated affected_files, not unchecked prose.
    if re.search(r'\bline[s]?\s+\d+|\.(?:js|ts|mjs|py):\d+', prose, re.I):
        raise ValueError('Use structured code locations for line references')
    cited = {by_id[id]['kind'] for id in analysis.suspected_root_cause.evidence_ids}
    if 'source' not in cited:
        confidence, reason = 'INSUFFICIENT_EVIDENCE', 'The root-cause hypothesis lacks a collected source-code citation.'
    elif 'log' in cited:
        confidence, reason = 'MEDIUM', 'The hypothesis cites both observed failure and collected source. Causality has not been reproduced.'
    else:
        confidence, reason = 'LOW', 'Source context is available but the hypothesis does not cite observed failure evidence.'
    # HIGH is reserved for independent controlled causal reproduction, absent in read-only Phase 5.
    result = analysis.model_dump()
    result['limitations'] = list(dict.fromkeys([*limitations, *result['limitations'], 'Citation validation checks provenance and locations, not semantic entailment. No causal reproduction or hotfix was executed.']))
    result['confidence'] = {'category':confidence, 'reason':reason}
    result['historical_references'] = [{**item, 'similarity_score':by_id[item['evidence_id']]['similarity_score'], 'source_ref':by_id[item['evidence_id']]['source_ref']} for item in result['historical_references']]
    return result
