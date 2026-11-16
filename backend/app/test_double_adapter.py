"""Explicit deterministic wiring check. Never selected as a live failure fallback."""


def deterministic_analysis(bundle):
    refs = [bundle['evidence'][0]['id']]
    return {'error_summary': 'TEST DOUBLE: deterministic evidence wiring check.',
            'suspected_root_cause': {'classification': 'uncertain',
                'statement': 'TEST DOUBLE: no AI root cause was inferred.', 'evidence_ids': refs},
            'verified_facts': [], 'explanation': [], 'affected_files': [], 'suspected_commits': [],
            'historical_references': [], 'recommended_remediation': [],
            'limitations': ['TEST DOUBLE: no model request, causal verification or genuine AI analysis.']}


class DeterministicAdapter:
    mode = 'test-double'
    backend = 'test-double'

    def __init__(self, settings):
        self.settings = settings

    def status(self):
        return {'available': bool(self.settings.agent_execution_enabled and self.settings.agent_auth_token),
                'mode': self.mode, 'backend': self.backend, 'paid_run_performed': False,
                'message': 'Explicit TEST DOUBLE; no genuine AI analysis or model request.'}

    async def run(self, bundle):
        if not self.status()['available']:
            raise RuntimeError('Test double is disabled')
        return {'analysis': deterministic_analysis(bundle),
                'metadata': {'provider': 'deterministic-test-double', 'mode': self.mode, 'backend': self.backend}}
