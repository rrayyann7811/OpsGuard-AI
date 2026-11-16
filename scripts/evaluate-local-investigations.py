"""Score saved genuine local reports only. Never runs a model, service or collector.

Input: [{case_id, investigation: <GET /api/investigations/{id} response body field>,
         review: {root_cause_correct: bool, reviewer: str}}]. Manual review is optional.
Use a NEW output path. Test-double reports are rejected, not scored as AI accuracy.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.agent_reports import validate_analysis


def evaluate(rows, cases):
    by_id = {x['id']: x for x in cases}
    seen, durations, term_matches, file_matches, valid, reviewed = set(), [], [], [], [], []
    failed = model_failed = 0
    models = set()
    for entry in rows:
        case_id = entry['case_id']
        if case_id in seen or case_id not in by_id: raise ValueError('Unknown or duplicate case ID')
        seen.add(case_id)
        job = entry['investigation']; meta = job['execution_metadata']
        if meta.get('mode') != 'local-ollama' or meta.get('backend') != 'local-ollama':
            raise ValueError('Only explicitly genuine local-ollama provenance may be evaluated')
        models.add(meta.get('model', 'unknown'))
        if job.get('duration_ms') is not None: durations.append(job['duration_ms'])
        if job['status'] != 'COMPLETED':
            if job['status'] not in ('FAILED', 'CANCELLED'): raise ValueError('Unfinished investigation')
            failed += 1
            if str(job.get('error_code', '')).startswith('OLLAMA_') or job.get('error_code') == 'TIMEOUT': model_failed += 1
            continue
        if meta.get('provider') != 'ollama': raise ValueError('Completed report lacks actual Ollama provider provenance')
        report = job['report']; evidence = job['evidence']
        fields = ('error_summary','suspected_root_cause','verified_facts','explanation','affected_files',
                  'suspected_commits','historical_references','recommended_remediation','limitations')
        raw = {key: report[key] for key in fields}
        raw['historical_references'] = [{key:x[key] for key in ('historical_id','evidence_id')} for x in raw['historical_references']]
        try:
            validate_analysis(raw, evidence, [])
            valid.append(True)
        except ValueError: valid.append(False)
        expected = by_id[case_id]
        statement = report['suspected_root_cause']['statement'].lower()
        term_matches.append(all(term in statement for term in expected['expected_terms']))
        file_matches.append(expected['expected_file'] in {x['path'] for x in report['affected_files']})
        review = entry.get('review', {})
        if 'root_cause_correct' in review:
            if type(review['root_cause_correct']) is not bool or not review.get('reviewer'):
                raise ValueError('Manual accuracy requires a named reviewer and boolean judgment')
            reviewed.append(review['root_cause_correct'])
    mean = lambda values: sum(values)/len(values) if values else None
    return {'execution':'saved genuine local reports; no inference performed by scorer',
            'evaluated_cases':len(seen), 'expected_cases':len(cases), 'models':sorted(models),
            'completed':len(valid), 'failed_or_cancelled':failed,
            'root_cause_accuracy':mean(reviewed), 'manually_reviewed_count':len(reviewed),
            'root_cause_term_match_rate_heuristic_only':mean(term_matches),
            'affected_file_identification_accuracy_completed':mean(file_matches),
            'report_citation_validation_pass_rate':mean(valid),
            'mean_investigation_duration_ms':mean(durations),
            'operational_failure_rate':failed/len(seen) if seen else None,
            'model_or_timeout_error_rate':model_failed/len(seen) if seen else None,
            'limits':['Manual root-cause review compares against known controlled ground truth.',
                      'Term matching is a heuristic, not causal accuracy.',
                      'Citation validation checks report provenance, not semantic entailment.',
                      'Model errors include preflight, validation and timeout; they are not pure inference-engine failures.',
                      'Saved provenance must be independently audited; this tool cannot authenticate arbitrary JSON.',
                      'Historical references may reveal similar causes; this is an assisted task, not a blind benchmark.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=evaluate(json.loads(args.input.read_text()),json.loads((ROOT/'evaluation/investigation_cases.json').read_text()))
    with args.output.open('x') as target: json.dump(result,target,indent=2);target.write('\n')


if __name__=='__main__': main()
