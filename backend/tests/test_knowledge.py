"""Deterministic interface tests use labelled test vectors, never quality measurements."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
pytest.importorskip("qdrant_client", reason="Install optional requirements-rag.lock.txt for knowledge tests")
from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models import Incident, now
from app.knowledge_api import get_store
from app.knowledge_documents import HistoricalIncident, load_dataset, prepare, point_id, document_hash
from app.knowledge_embeddings import LocalEmbedder, KnowledgeUnavailable
from app.knowledge_store import KnowledgeStore

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = load_dataset(ROOT / "knowledge/data/incidents.json")


class TestEmbedder:
    __test__ = False
    # Explicit deterministic interface double. Not a semantic embedding model.
    model_key = "unit-test-double-v1"
    model = None
    calls = 0
    def split(self, text): return [text]
    def encode(self, texts):
        self.calls += 1
        return [[1.0, float('payment' in text.lower()), float('user' in text.lower()), 0.1] for text in texts]


@pytest.fixture
def store():
    settings = Settings(embedding_dimension=4)
    result = KnowledgeStore(settings, client=QdrantClient(":memory:"), embedder=TestEmbedder())
    yield result
    result.close()


def test_dataset_validation_preparation_and_identifiers(tmp_path):
    assert len(DOCUMENTS) == 24
    assert {doc.service_name for doc in DOCUMENTS} == {'user-service','order-service','payment-service'}
    document = DOCUMENTS[0]
    text = prepare(document)
    assert document.error_message in text and document.resolution in text
    assert document.id == 'SYN-USR-001' and document.synthetic is True
    assert point_id(document.id, 0) == point_id(document.id, 0)
    assert point_id(document.id, 0) != point_id(document.id, 1)
    assert document_hash(document, 'model-a') != document_hash(document, 'model-b')
    for updates in [{'synthetic':False},{'service_name':'unknown'},{'runbook':[]},{'id':'bad'}]:
        with pytest.raises(ValidationError): HistoricalIncident.model_validate({**document.model_dump(), **updates})
    path = tmp_path/'duplicates.json'
    path.write_text(json.dumps([document.model_dump(mode='json')]*2))
    with pytest.raises(ValueError, match='Duplicate'): load_dataset(path)


def test_documents_redact_credentials():
    doc = DOCUMENTS[0].model_copy(update={'error_message':'token=secret-value password=hidden-value'})
    assert 'secret-value' not in prepare(doc) and 'hidden-value' not in prepare(doc)


def test_collection_initialization_and_idempotent_indexing(store):
    assert store.status()['status'] == 'empty'
    first = store.index(DOCUMENTS[:2])
    assert first['indexed'] == 2 and first['indexed_incidents'] == 2
    calls = store.embedder.calls
    repeated = store.index(DOCUMENTS[:2])
    assert repeated['indexed'] == 0 and repeated['unchanged'] == 2
    assert store.embedder.calls == calls
    assert store.status()['source_count'] == 1
    assert store.status()['last_indexed_at']


def test_collection_mismatch_is_not_destroyed(store):
    store.client.create_collection(store.settings.qdrant_collection,
        vectors_config=models.VectorParams(size=2, distance=models.Distance.DOT))
    with pytest.raises(KnowledgeUnavailable): store.index(DOCUMENTS[:1])
    assert store.client.get_collection(store.settings.qdrant_collection).config.params.vectors.size == 2


def test_real_local_qdrant_filtering_and_result_format(store):
    store.index(DOCUMENTS)
    results = store.search('payment amount', service='payment-service', top_k=3, min_score=-1)
    assert len(results) == 3
    assert all(result['incident']['service_name']=='payment-service' for result in results)
    assert all(isinstance(result['similarity_score'], float) and result['source_ref'] for result in results)
    assert store.search('anything', severity='low') == []
    assert len(store.documents(service='user-service')) == 8
    assert store.search('PaymentFailure HTTP 502 payment-service', ranking='hybrid', min_score=-1)[0]['rank_score'] >= 0


def test_reindex_replaces_only_own_document_and_deactivates_stale_chunks(store):
    class Chunker(TestEmbedder):
        long = True
        def split(self, text): return [text, 'extra chunk'] if self.long else [text]
    store.embedder = Chunker()
    store.index(DOCUMENTS[:1])
    assert store.status()['indexed_chunks'] == 2
    store.embedder.long = False
    updated = DOCUMENTS[0].model_copy(update={'resolution':'Updated safe resolution with explicit input validation.'})
    store.index([updated])
    assert store.status()['indexed_chunks'] == 1
    assert store.client.count(store.settings.qdrant_collection).count == 2 # retained, not deleted
    assert store.documents()[0]['resolution'] == updated.resolution


def test_embedding_failure_preserves_prior_searchable_record(store):
    store.index(DOCUMENTS[:1])
    changed = DOCUMENTS[0].model_copy(update={'title':'Changed title for failure test'})
    with patch.object(store.embedder, 'encode', side_effect=KnowledgeUnavailable('offline')):
        with pytest.raises(KnowledgeUnavailable): store.index([changed])
    assert store.documents()[0]['title'] == DOCUMENTS[0].title


def test_partial_upsert_not_exposed_and_retry_recovers(store):
    store.index(DOCUMENTS[:1])
    changed = DOCUMENTS[0].model_copy(update={'title':'Changed historical title'})
    with patch.object(store.client, 'upsert', side_effect=RuntimeError('write failed')):
        with pytest.raises(RuntimeError): store.index([changed])
    assert store.documents() == []
    assert store.index([changed])['indexed'] == 1
    assert store.documents()[0]['title'] == changed.title


@pytest.fixture
def client(store):
    store.index(DOCUMENTS)
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def session():
        with factory() as db: yield db
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_db] = session
    yield TestClient(app), store, factory
    app.dependency_overrides.clear()
    engine.dispose()


def test_knowledge_api_pagination_metadata_and_detail(client):
    api, _, _ = client
    page = api.get('/api/knowledge/incidents?page_size=3&service=payment-service').json()
    assert page['total'] == 8 and len(page['items']) == 3
    assert api.get('/api/knowledge/incidents/SYN-PAY-001').json()['incident']['synthetic']
    assert api.get('/api/knowledge/incidents/missing').status_code == 404
    assert api.get('/api/knowledge/status').json()['indexed_incidents'] == 24
    assert api.get('/api/knowledge/incidents?page=0').status_code == 422


@pytest.mark.parametrize('body',[{'query':' '},{'query':'ab'},{'query':'x'*6001},{'query':'payment','top_k':11},{'query':'payment','service':'unknown'},{'query':'payment','extra':True}])
def test_search_validation(client, body):
    assert client[0].post('/api/knowledge/search',json=body).status_code == 422


def test_search_no_match_and_qdrant_unavailable(client):
    api, store, _ = client
    result = api.post('/api/knowledge/search',json={'query':'payment','service':'payment-service'}).json()
    assert result['total'] == 3 and result['items'][0]['source_ref']
    assert api.post('/api/knowledge/search',json={'query':'payment','severity':'low'}).json()['items'] == []
    with patch.object(store.client, 'collection_exists', side_effect=RuntimeError('secret-address')):
        assert api.get('/api/knowledge/status').json()['status']=='unavailable'
        response = api.post('/api/knowledge/search',json={'query':'payment'})
        assert response.status_code == 503 and 'secret-address' not in response.text
    assert api.post('/api/knowledge/reindex').status_code in (404,405)


def test_similar_incident_uses_sqlite_evidence_without_modifying_status(client):
    api, store, factory = client
    with factory() as db:
        row = Incident(id=str(uuid4()),service_name='payment-service', title='Payment failure', severity='high',status='OPEN',
            error_signature='test',error_type='PaymentFailure',error_message='Processor rejected payment',stack_trace=None,
            endpoint='/payments',http_status=502,first_seen=now(),last_seen=now(),occurrence_count=1)
        db.add(row);db.commit();id=row.id
    with patch.object(store,'search',wraps=store.search) as search:
        result = api.post('/api/knowledge/similar/'+id,json={'top_k':3})
        assert result.status_code == 200
        assert 'Processor rejected payment' in search.call_args.args[0]
    with factory() as db: assert db.get(Incident,id).status == 'OPEN'
    assert api.post('/api/knowledge/similar/'+str(uuid4()),json={}).status_code == 404


def test_embedding_interface_handles_missing_model_and_dimension():
    settings=Settings(embedding_model='nonexistent/offline-model')
    # No external download: constructor is mocked and configured offline.
    with patch('sentence_transformers.SentenceTransformer', side_effect=OSError('not cached')):
        with pytest.raises(KnowledgeUnavailable): LocalEmbedder(settings).encode(['text'])
    with patch('sentence_transformers.SentenceTransformer') as constructor:
        constructor.return_value.get_embedding_dimension.return_value = 2
        with pytest.raises(KnowledgeUnavailable): LocalEmbedder(Settings()).load()


@pytest.mark.skipif(os.getenv('OPSGUARD_RAG_INTEGRATION') != '1', reason='Opt-in real cached-model integration; never downloads in routine tests')
def test_real_embeddings_persistent_qdrant_and_semantic_search(tmp_path):
    settings=Settings(qdrant_path=str(tmp_path/'real-qdrant'))
    store=KnowledgeStore(settings)
    try:
        indexed=store.index(DOCUMENTS)
        assert indexed['indexed_incidents']==24
        assert store.index(DOCUMENTS)['unchanged']==24
        hits=store.search('Processing fee subtracted instead of added to the payment amount',service='payment-service')
        assert 'SYN-PAY-004' in [hit['incident']['id'] for hit in hits]
        model=store.embedder
    finally: store.close()
    reopened=KnowledgeStore(settings, embedder=model)
    try:
        assert reopened.status()['indexed_incidents']==24
        assert reopened.search('Payment total violated fee invariant',service='payment-service')[0]['incident']['id']=='SYN-PAY-004'
    finally: reopened.close()


def test_index_refuses_foreign_point_overwrite(store):
    store.collection(create=True)
    id = point_id(DOCUMENTS[0].id, 0)
    store.client.upsert(store.settings.qdrant_collection, points=[models.PointStruct(id=id, vector=[1.,0.,0.,0.], payload={"owner":"someone-else"})])
    with pytest.raises(KnowledgeUnavailable): store.index(DOCUMENTS[:1])
    assert store.client.retrieve(store.settings.qdrant_collection, ids=[id])[0].payload['owner']=='someone-else'


def test_long_query_embeds_all_chunks(store):
    store.index(DOCUMENTS[:1])
    with patch.object(store.embedder, 'split', return_value=['first error', 'later stack frame']), patch.object(store.embedder,'encode', wraps=store.embedder.encode) as encode:
        store.search('long input', min_score=-1)
        assert encode.call_args.args[0] == ['first error','later stack frame']


def test_evaluation_metric_denominators_and_no_match():
    from app.knowledge_cli import evaluate
    class MetricStore:
        embedder = TestEmbedder()
        def search(self, query, **kwargs):
            return [] if query == 'unrelated' else [{'incident':{'id':'wrong'}}, {'incident':{'id':'B'}}]
    result = evaluate(MetricStore(), [
        {'id':'relevant','query':'failure','service':None,'relevant_ids':['A','B']},
        {'id':'unrelated','query':'unrelated','service':None,'relevant_ids':[]},
    ])
    for method in result['methods'].values():
        assert method['precision_at_3'] == pytest.approx(1/3)
        assert method['recall_at_3'] == .5
        assert method['mrr'] == .5
        assert method['no_match_accuracy'] == 1
