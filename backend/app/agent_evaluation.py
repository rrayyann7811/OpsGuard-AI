"""Offline scorer for explicitly captured reports. Does not execute paid agents."""
import argparse
import json
from pathlib import Path
from statistics import mean
from app.agent_reports import validate_analysis

ROOT=Path(__file__).resolve().parents[2]


def score(records,cases):
    if not records:
        return {'live_execution_performed':False,'status':'PENDING_LIVE_CODEX','case_count':len(cases),
            'root_cause_accuracy':None,'affected_file_accuracy':None,'evidence_attribution_correctness':None,
            'mean_duration_ms':None,'failure_rate':None,'incorrect_confidence_rate':None,
            'message':'No real Codex reports supplied. Deterministic application tests are not AI benchmarks.'}
    known={case['id']:case for case in cases}
    methods={}
    for variant in ('logs_only','logs_git','logs_git_rag'):
        rows=[row for row in records if row['variant']==variant]
        if not rows: continue
        if any(row.get('execution_mode')!='live-codex' for row in rows):
            raise ValueError('Test-double output cannot be scored as a real AI benchmark')
        complete=[row for row in rows if row['status']=='COMPLETED']
        checked=[]
        for row in complete:
            case=known[row['case_id']]
            try:
                validate_analysis(row['analysis'],row['evidence'],[])
                attributed=True
            except ValueError: attributed=False
            file_correct=case['expected_file'] in {item['path'] for item in row['analysis']['affected_files']}
            # Keyword proxy is diagnostic only. Independent reviewed labels determine root accuracy.
            proxy=all(term in row['analysis']['suspected_root_cause']['statement'].lower() for term in case['expected_terms'])
            checked.append({'file':file_correct,'attributed':attributed,'proxy':proxy,'reviewed':row.get('reviewed_root_cause_correct'),
                'confident':row.get('confidence_category') in ('HIGH','MEDIUM')})
        reviewed=[row for row in checked if isinstance(row['reviewed'],bool)]
        methods[variant]={'attempts':len(rows),'completed':len(complete),
            'root_cause_accuracy':mean(row['reviewed'] for row in reviewed) if reviewed else None,
            'root_cause_keyword_proxy':mean(row['proxy'] for row in checked) if checked else None,
            'affected_file_accuracy':mean(row['file'] for row in checked) if checked else None,
            'evidence_attribution_correctness':mean(row['attributed'] for row in checked) if checked else None,
            'mean_duration_ms':mean(row['duration_ms'] for row in complete) if complete else None,
            'failure_rate':1-len(complete)/len(rows),
            'incorrect_confidence_rate':mean(not row['reviewed'] and row['confident'] for row in reviewed) if reviewed else None,
            'reviewed_reports':len(reviewed)}
    return {'live_execution_performed':True,'methods':methods,'case_count':len(cases),
        'limitations':['Reviewed correctness is required for root-cause accuracy. Keyword coverage is not semantic correctness.',
            'Attribution checks provenance, not whether evidence entails a conclusion.','Small controlled synthetic fixture corpus; no generalization claim.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'evaluation/agent_results.json')
    args=parser.parse_args()
    cases=json.loads((ROOT/'evaluation/investigation_cases.json').read_text())
    records=json.loads(args.reports.read_text()) if args.reports else []
    result=score(records,cases)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
