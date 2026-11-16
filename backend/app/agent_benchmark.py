"""Opt-in paid runner. Never runs implicitly in tests or on backend startup."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from app.config import get_settings
from app.codex_adapter import CodexAdapter
from app.agent_evidence import RepositoryReader
from app.agent_reports import validate_analysis
from app.knowledge_store import KnowledgeStore

ROOT=Path(__file__).resolve().parents[2]


async def benchmark(args):
    settings=get_settings();adapter=CodexAdapter(settings)
    if not args.authorize_paid_execution:
        raise SystemExit('Refusing paid execution without --authorize-paid-execution. No model call made.')
    if not adapter.status().get('available'):
        raise SystemExit('Actual Codex configuration or containment unavailable. No test double is substituted; no model call made.')
    sys.path.insert(0,str(ROOT/'backend/tests'))
    from agent_support import git_fixture
    cases=json.loads((ROOT/'evaluation/investigation_cases.json').read_text())
    if args.case: cases=[case for case in cases if case['id']==args.case]
    records=[]
    knowledge=KnowledgeStore(settings)
    try:
        with tempfile.TemporaryDirectory(prefix='opsguard-agent-benchmark-') as directory:
            fixture,_=git_fixture(Path(directory)/'fixture',ROOT)
            reader=RepositoryReader(fixture)
            for case in cases:
                # Curated synthetic input is labelled, never represented as a newly observed service log.
                evidence=[{'id':'E001','kind':'log','content':json.dumps({'synthetic_evaluation_input':True,'case_id':case['id'],
                    'error_type':case['error_type'],'error_message':case['error_message']})}]
                sources=reader.collect(case['service_name'],{**case,'stack_trace':None})
                git,limitations=reader.collect_git(sources)
                for item in [*sources,*git]: evidence.append({**item,'id':f'E{len(evidence)+1:03}'})
                try:
                    matches=knowledge.search(case['error_type']+' '+case['error_message'],service=case['service_name'])
                    for hit in matches: evidence.append({'id':f'E{len(evidence)+1:03}','kind':'historical','historical_id':hit['incident']['id'],
                        'similarity_score':hit['similarity_score'],'source_ref':hit['source_ref'],'content':json.dumps(hit['incident'])})
                except Exception: limitations.append('Historical context unavailable for this evaluation run.')
                for variant in args.variants:
                    allowed={'log'} if variant=='logs_only' else {'log','source','git'} if variant=='logs_git' else {'log','source','git','historical'}
                    selected=[item for item in evidence if item['kind'] in allowed]
                    started=perf_counter()
                    record={'case_id':case['id'],'variant':variant,'execution_mode':'live-codex','reviewed_root_cause_correct':None,
                        'synthetic_evaluation_input':True,'evidence':selected}
                    try:
                        async with asyncio.timeout(settings.agent_timeout_seconds):
                            output=await adapter.run({'investigation_id':'evaluation-'+case['id'],'incident_id':'synthetic-evaluation',
                                'service_name':case['service_name'],'evidence':selected,'limitations':limitations,'read_only':True})
                        report=validate_analysis(output['analysis'],selected,limitations)
                        record.update(status='COMPLETED',analysis=output['analysis'],confidence_category=report['confidence']['category'],metadata=output.get('metadata',{}))
                    except Exception:
                        record.update(status='FAILED',error='Agent execution, timeout or report validation failure')
                    record['duration_ms']=round((perf_counter()-started)*1000,2)
                    records.append(record)
                    args.output.write_text(json.dumps(records,indent=2)+'\n')
    finally: knowledge.close()
    print('Saved real execution records. Add independent reviewed_root_cause_correct labels before claiming root-cause accuracy.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-paid-execution',action='store_true')
    parser.add_argument('--case',choices=[f'INV-EVAL-{index:02}' for index in range(1,11)])
    parser.add_argument('--variants',nargs='+',choices=['logs_only','logs_git','logs_git_rag'],default=['logs_git_rag'])
    parser.add_argument('--output',type=Path,default=ROOT/'evaluation/agent_live_reports.json')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a new output path; existing benchmark results are never overwritten by this runner')
    asyncio.run(benchmark(args))


if __name__=='__main__': main()
