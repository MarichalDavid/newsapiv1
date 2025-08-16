#!/usr/bin/env python3
"""
Script de test complet pour l'API NewsAI avec validation du contenu
Tests TOUS les endpoints + validation de la structure et du contenu des réponses

Usage:
    python test_newsapi_complete.py --base-url http://localhost:8000
    python test_newsapi_complete.py --base-url https://your-api.com --verbose
    python test_newsapi_complete.py --only health,articles --timeout 30
"""

import asyncio
import aiohttp
import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import traceback
import time
import re

class TestStatus(Enum):
    PASS = "[PASS] PASS"
    FAIL = "[FAIL] FAIL"
    SKIP = "[SKIP] SKIP"
    WARN = "[WARN] WARN"
    CONTENT_FAIL = "[CONTENT_FAIL] CONTENT FAIL"
    EMPTY_RESPONSE = "[EMPTY_RESPONSE] EMPTY RESPONSE"  # Nouvelle catégorie pour les réponses vides

@dataclass
class TestResult:
    endpoint: str
    method: str
    status_code: int
    response_time: float
    status: TestStatus
    message: str
    response_data: Optional[Any] = None  # Utiliser Any pour stocker n'importe quel type de réponse
    content_checks: List[str] = None

class ContentValidator:
    """Classe pour valider le contenu des réponses API"""
    
    @staticmethod
    def validate_article(article: Dict) -> List[str]:
        """Valide la structure d'un article"""
        errors = []
        required_fields = ['id', 'title', 'url', 'domain']
        
        for field in required_fields:
            if field not in article:
                errors.append(f"Champ manquant: {field}")
            elif not article[field]:
                errors.append(f"Champ vide: {field}")
        
        # Validation des types
        if 'id' in article and not isinstance(article['id'], int):
            errors.append("ID doit être un entier")
        
        if 'title' in article and len(str(article['title'])) < 3:
            errors.append("Titre trop court")
        
        if 'url' in article and not str(article['url']).startswith(('http://', 'https://')):
            errors.append("URL invalide")
        
        return errors

    @staticmethod
    def validate_source(source: Dict) -> List[str]:
        """Valide la structure d'une source"""
        errors = []
        required_fields = ['id', 'name', 'feed_url', 'site_domain', 'active']
        
        for field in required_fields:
            if field not in source:
                errors.append(f"Champ manquant: {field}")
        
        if 'active' in source and not isinstance(source['active'], bool):
            errors.append("'active' doit être un booléen")
        
        if 'feed_url' in source and not str(source['feed_url']).startswith(('http://', 'https://')):
            errors.append("feed_url invalide")
        
        return errors

    @staticmethod
    def validate_stats(stats: Dict) -> List[str]:
        """Valide les statistiques générales"""
        errors = []
        required_fields = ['total_articles', 'unique_domains']
        numeric_fields = ['total_articles', 'unique_domains', 'articles_24h']
        
        for field in required_fields:
            if field not in stats:
                errors.append(f"Champ statistique manquant: {field}")
        
        for field in numeric_fields:
            if field in stats and not isinstance(stats[field], (int, float)):
                errors.append(f"{field} doit être numérique")
            elif field in stats and stats[field] < 0:
                errors.append(f"{field} ne peut pas être négatif")
        
        return errors

    @staticmethod
    def validate_health(health: Dict) -> List[str]:
        """Valide la réponse health"""
        errors = []
        
        if 'status' not in health:
            errors.append("Champ 'status' manquant")
        elif health['status'] not in ['ok', 'healthy', 'running']:
            errors.append(f"Status invalide: {health['status']}")
        
        return errors

    @staticmethod
    def validate_cluster(cluster: Dict) -> List[str]:
        """Valide la structure d'un cluster"""
        errors = []
        
        if 'cluster_id' not in cluster:
            errors.append("cluster_id manquant")
        
        if 'n' in cluster and not isinstance(cluster['n'], int):
            errors.append("'n' doit être un entier")
        
        return errors

class NewsAIAPITester:
    def __init__(self, base_url: str, timeout: int = 30, verbose: bool = False, show_response: bool = True, response_max_chars: int = 2000, skip_collection: bool = False):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.show_response = show_response
        self.response_max_chars = response_max_chars
        self.skip_collection = skip_collection
        self.validator = ContentValidator()
        
        # IDs de test récupérés dynamiquement
        self.test_data = {
            'article_id': None,
            'source_id': None,
            'cluster_id': None,
            'topic_name': None,
            'domain': None,
            'test_date': datetime.now().strftime('%Y-%m-%d')
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def make_request(self, method: str, endpoint: str, expected_content: Optional[Dict] = None, **kwargs) -> TestResult:
        """Fait une requête HTTP et valide le contenu de la réponse"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        content_checks = []
        response_data = None
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                
                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    response_data = await response.text()
                except json.JSONDecodeError:
                    response_data = await response.text()
                except Exception:
                    response_data = None
                
                # Déterminer le statut de base
                if response.status < 400:
                    status = TestStatus.PASS
                    message = f"Success - {response.status}"
                elif response.status == 404:
                    status = TestStatus.WARN
                    message = f"Not found - {response.status}"
                else:
                    status = TestStatus.FAIL
                    message = f"HTTP Error - {response.status}"

                # Vérification de la réponse vide/nulle
                if response_data is None or response_data == [] or response_data == {} or response_data == "":
                    status = TestStatus.EMPTY_RESPONSE
                    message = "Réponse nulle ou vide"

                # Validation du contenu si la requête a réussi
                if status in [TestStatus.PASS, TestStatus.CONTENT_FAIL] and expected_content:
                    if isinstance(response_data, dict):
                        content_errors = self.validate_response_content(response_data, expected_content)
                        if content_errors:
                            status = TestStatus.CONTENT_FAIL
                            message = f"Content validation failed: {'; '.join(content_errors[:3])}"
                            content_checks = content_errors
                        else:
                            content_checks = ["[OK] Structure valide"]
                    elif isinstance(response_data, list):
                        content_errors = self.validate_list_content(response_data, expected_content)
                        if content_errors:
                            status = TestStatus.CONTENT_FAIL
                            message = f"Content validation failed: {'; '.join(content_errors[:3])}"
                            content_checks = content_errors
                        else:
                            content_checks = [f"[OK] Liste valide ({len(response_data)} éléments)"]
                
                return TestResult(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status,
                    response_time=response_time,
                    status=status,
                    message=message,
                    response_data=response_data,
                    content_checks=content_checks
                )
                
        except asyncio.TimeoutError:
            return TestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=time.time() - start_time,
                status=TestStatus.FAIL,
                message="Timeout"
            )
        except Exception as e:
            return TestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=time.time() - start_time,
                status=TestStatus.FAIL,
                message=f"Exception: {str(e)}"
            )

    def validate_response_content(self, data: Dict, expected: Dict) -> List[str]:
        """Valide le contenu d'une réponse selon les attentes"""
        errors = []
        
        # Validation du type de réponse
        if expected.get('type') == 'list' and not isinstance(data, list):
            errors.append("Réponse devrait être une liste")
            return errors
        
        if expected.get('type') == 'object' and not isinstance(data, dict):
            errors.append("Réponse devrait être un objet")
            return errors
        
        # Validation des stats
        if expected.get('contains') == 'stats':
            stats_errors = self.validator.validate_stats(data)
            errors.extend(stats_errors)
        
        # Validation health
        elif expected.get('contains') == 'health':
            health_errors = self.validator.validate_health(data)
            errors.extend(health_errors)
        
        # Validation des champs requis
        if expected.get('required_fields'):
            for field in expected['required_fields']:
                if field not in data:
                    errors.append(f"Champ requis manquant: {field}")
        
        return errors

    def validate_list_content(self, data: List, expected: Dict) -> List[str]:
        """Valide le contenu d'une liste selon les attentes"""
        errors = []
        
        # Validation des contraintes de taille
        if expected.get('min_items') and len(data) < expected['min_items']:
            errors.append(f"Nombre d'éléments insuffisant: {len(data)} < {expected['min_items']}")
        
        # Validation des articles
        if expected.get('contains') == 'articles' and len(data) > 0:
            for i, article in enumerate(data[:3]):  # Vérifier les 3 premiers
                if isinstance(article, dict):
                    article_errors = self.validator.validate_article(article)
                    for error in article_errors:
                        errors.append(f"Article {i}: {error}")
        
        # Validation des sources
        elif expected.get('contains') == 'sources' and len(data) > 0:
            for i, source in enumerate(data[:3]):
                if isinstance(source, dict):
                    source_errors = self.validator.validate_source(source)
                    for error in source_errors:
                        errors.append(f"Source {i}: {error}")
        
        # Validation des clusters
        elif expected.get('contains') == 'clusters' and len(data) > 0:
            for i, cluster in enumerate(data[:3]):
                if isinstance(cluster, dict):
                    cluster_errors = self.validator.validate_cluster(cluster)
                    for error in cluster_errors:
                        errors.append(f"Cluster {i}: {error}")
        
        return errors

    def _format_response_preview(self, data) -> str:
        try:
            if isinstance(data, (dict, list)):
                text = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                text = str(data)
        except Exception:
            text = str(data)
        if len(text) > self.response_max_chars:
            extra = len(text) - self.response_max_chars
            text = text[:self.response_max_chars] + f"... (+{extra} chars)"
        return text

    def log_result(self, result: TestResult):
        """Log le résultat d'un test avec détails du contenu"""
        self.results.append(result)
        
        if self.verbose or result.status in [TestStatus.FAIL, TestStatus.WARN, TestStatus.CONTENT_FAIL, TestStatus.EMPTY_RESPONSE]:
            print(f"{result.status.value} {result.method} {result.endpoint}")
            print(f"    Status: {result.status_code} | Time: {result.response_time:.2f}s | {result.message}")
            
            if result.content_checks and self.verbose:
                for check in result.content_checks[:5]:  # Limiter à 5 messages
                    print(f"    [CHECK] {check}")
            
            if result.status == TestStatus.FAIL and self.verbose:
                print(f"    [RESPONSE] Response: {str(result.response_data)[:200]}...")
            
            if self.show_response and result.response_data is not None:
                preview = self._format_response_preview(result.response_data)
                print(f"    [RESPONSE] Réponse API (aperçu):\n{preview}")
            print()

    async def populate_test_data(self):
        """Récupère des IDs de test valides depuis l'API"""
        print("[INFO] Récupération des données de test...")
        
        # Récupérer un article ID
        result = await self.make_request("GET", "/api/v1/articles?limit=1", 
                                       expected_content={'contains': 'articles'})
        if result.status == TestStatus.PASS and result.response_data:
            articles = result.response_data
            if isinstance(articles, list) and len(articles) > 0:
                self.test_data['article_id'] = articles[0].get('id')
                self.test_data['domain'] = articles[0].get('domain')
        
        # Récupérer un source ID
        result = await self.make_request("GET", "/api/v1/sources",
                                       expected_content={'contains': 'sources'})
        if result.status == TestStatus.PASS and result.response_data:
            sources = result.response_data
            if isinstance(sources, list) and len(sources) > 0:
                self.test_data['source_id'] = sources[0].get('id')
        
        # Récupérer un cluster ID
        result = await self.make_request("GET", "/api/v1/clusters?limit_clusters=1")
        if result.status == TestStatus.PASS and result.response_data:
            clusters = result.response_data
            if isinstance(clusters, list) and len(clusters) > 0:
                self.test_data['cluster_id'] = clusters[0].get('cluster_id')
        
        # Récupérer un topic name
        result = await self.make_request("GET", "/api/v1/topics")
        if result.status == TestStatus.PASS and result.response_data:
            topics = result.response_data
            if isinstance(topics, list) and len(topics) > 0:
                topic_data = topics[0]
                if isinstance(topic_data, dict):
                    self.test_data['topic_name'] = topic_data.get('topic')
                elif isinstance(topic_data, str):
                    self.test_data['topic_name'] = topic_data
        
        if self.verbose:
            print(f"[DATA] Données de test: {self.test_data}")
            print()

    async def test_health_endpoints(self):
        """Test des endpoints de santé"""
        print("[INFO] Test des endpoints Health & Monitoring...")
        
        tests = [
            ("/health", {'type': 'object', 'contains': 'health'}),
            ("/health/detailed", {'type': 'object', 'contains': 'health'}),
            ("/", {'type': 'object'}),
            ("/api/v1/system/status", {'type': 'object'}),
        ]
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_articles_endpoints(self):
        """Test des endpoints d'articles"""
        print("[INFO] Test des endpoints Articles...")
        
        tests = [
            ("/api/v1/articles", {'contains': 'articles'}),
            ("/api/v1/articles?limit=5&lang=fr", {'contains': 'articles'}),
            ("/api/v1/articles?q=test&has_full_text=true", {'contains': 'articles'}),
            ("/api/v1/articles?topic=tech&order=asc", {'contains': 'articles'}),
        ]
        
        # Test avec ID spécifique si disponible
        if self.test_data['article_id']:
            tests.append((f"/api/v1/articles/{self.test_data['article_id']}", 
                          {'type': 'object', 'contains': 'articles'}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_search_endpoints(self):
        """Test des endpoints de recherche"""
        print("[INFO] Test des endpoints Search...")
        
        tests = [
            ("/api/v1/search?q=test", {'contains': 'articles'}),
            ("/api/v1/search?q=macron&lang=fr&limit=5", {'contains': 'articles'}),
            ("/api/v1/search/semantic?q=intelligence&k=5", {'contains': 'articles'}),
            ("/api/v1/search/entities?entity_type=PERSON&since_days=7", {}),
            ("/api/v1/search/entities?entity_type=ORG&entity_name=OpenAI", {}),
        ]
        
        # Test articles similaires si ID disponible
        if self.test_data['article_id']:
            tests.append((f"/api/v1/search/similar/{self.test_data['article_id']}", 
                          {'contains': 'articles'}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_sources_endpoints(self):
        """Test des endpoints de sources"""
        print("[INFO] Test des endpoints Sources...")
        
        tests = [
            ("/api/v1/sources", {'contains': 'sources', 'min_items': 1}),
        ]
        
        # Test source spécifique si ID disponible
        if self.test_data['source_id']:
            tests.append((f"/api/v1/sources/{self.test_data['source_id']}", 
                          {'type': 'object', 'contains': 'sources'}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)
        
        # Test POST refresh
        result = await self.make_request("POST", "/api/v1/sources/refresh")
        self.log_result(result)

    async def test_summaries_endpoints(self):
        """Test des endpoints de résumés"""
        print("[INFO] Test des endpoints Summaries...")
        
        tests = [
            ("/api/v1/summaries?limit=3", {}),
            ("/api/v1/summaries?since_hours=48&lang=fr", {}),
            ("/api/v1/summaries/general?target_sentences=5", {}),
            ("/api/v1/summaries/trending?since_hours=24", {}),
        ]
        
        # Test avec topic et domain si disponibles
        if self.test_data['topic_name']:
            tests.append((f"/api/v1/summaries/topic/{self.test_data['topic_name']}", {}))
        
        if self.test_data['domain']:
            tests.append((f"/api/v1/summaries/source/{self.test_data['domain']}", {}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_synthesis_endpoints(self):
        """Test des endpoints de synthèse"""
        print("[INFO] Test des endpoints Synthesis...")
        
        tests = [
            ("/api/v1/synthesis?since_hours=24&limit_docs=5", {}),
            ("/api/v1/synthesis?q=test&lang=fr", {}),
        ]
        
        # Test avec source et topic si disponibles
        if self.test_data['source_id']:
            tests.append((f"/api/v1/synthesis?source_id={self.test_data['source_id']}", {}))
        
        if self.test_data['topic_name']:
            tests.append((f"/api/v1/synthesis?topic={self.test_data['topic_name']}", {}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_topics_endpoints(self):
        """Test des endpoints de topics"""
        print("[INFO] Test des endpoints Topics...")
        
        tests = [
            ("/api/v1/topics", {}),
        ]
        
        # Test avec topic spécifique si disponible
        if self.test_data['topic_name']:
            tests.extend([
                (f"/api/v1/topics/{self.test_data['topic_name']}", {}),
                (f"/api/v1/topics/{self.test_data['topic_name']}/articles?limit=5", {'contains': 'articles'}),
            ])
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_clusters_endpoints(self):
        """Test des endpoints de clusters"""
        print("[INFO] Test des endpoints Clusters...")
        
        tests = [
            ("/api/v1/clusters?limit_clusters=5", {'contains': 'clusters'}),
            ("/api/v1/clusters?since_hours=24", {'contains': 'clusters'}),
        ]
        
        # Test avec cluster spécifique si disponible
        if self.test_data['cluster_id']:
            tests.extend([
                (f"/api/v1/clusters/{self.test_data['cluster_id']}", {}),
                (f"/api/v1/clusters/{self.test_data['cluster_id']}/articles?limit=5", {'contains': 'articles'}),
            ])
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_sentiment_endpoints(self):
        """Test des endpoints de sentiment"""
        print("[INFO] Test des endpoints Sentiment...")
        
        tests = [
            ("/api/v1/sentiment/global?days=7", {}),
            ("/api/v1/sentiment/global?days=30&granularity=weekly", {}),
            ("/api/v1/sentiment/topic/1?days=7", {}),
        ]
        
        # Test avec domain si disponible
        if self.test_data['domain']:
            tests.append((f"/api/v1/sentiment/source/{self.test_data['domain']}?days=7", {}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_stats_endpoints(self):
        """Test des endpoints de statistiques"""
        print("[INFO] Test des endpoints Stats...")
        
        tests = [
            ("/api/v1/stats/general", {
                'type': 'object', 
                'contains': 'stats',
                'required_fields': ['total_articles', 'unique_domains']
            }),
            ("/api/v1/stats/sources", {'type': 'object'}),
            ("/api/v1/stats/topics", {'type': 'object'}),
            ("/api/v1/stats/timeline?days=30", {}),
        ]
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_relations_endpoints(self):
        """Test des endpoints de relations"""
        print("[INFO] Test des endpoints Relations...")
        
        tests = [
            (f"/api/v1/relations/sources?date={self.test_data['test_date']}&limit=5", {}),
            (f"/api/v1/relations/sources?date={self.test_data['test_date']}&min_weight=2.0", {}),
        ]
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_graph_endpoints(self):
        """Test des endpoints de graph"""
        print("[INFO] Test des endpoints Graph...")
        
        tests = []
        
        # Test avec cluster si disponible
        if self.test_data['cluster_id']:
            tests.append((f"/api/v1/graph/cluster/{self.test_data['cluster_id']}", {}))
        else:
            # Test avec cluster fictif pour vérifier la réponse
            tests.append(("/api/v1/graph/cluster/test123", {}))
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)

    async def test_exports_endpoints(self):
        """Test des endpoints d'export"""
        print("[INFO] Test des endpoints Exports...")
        
        endpoints = [
            "/api/v1/exports/articles.csv?limit=5",
            "/api/v1/exports/articles.csv?lang=fr&limit=3",
            "/api/v1/exports/sentiment.csv?days=7",
            "/api/v1/exports/topics.json",
            "/api/v1/exports/stats.json",
        ]
        
        for endpoint in endpoints:
            result = await self.make_request("GET", endpoint)
            
            # Validation spéciale pour les exports
            if result.status == TestStatus.PASS and result.response_data:
                if endpoint.endswith('.csv') and isinstance(result.response_data, str):
                    if not result.response_data.strip():
                        result.status = TestStatus.EMPTY_RESPONSE
                        result.message = "Fichier CSV vide"
                    elif ',' not in result.response_data:
                        result.status = TestStatus.CONTENT_FAIL
                        result.message = "Format CSV invalide"
                    else:
                        result.content_checks = ["[OK] Format CSV valide"]
            
            self.log_result(result)

    async def test_admin_endpoints(self):
        """Test des endpoints d'administration"""
        print("[INFO] Test des endpoints Admin...")
        
        tests = [
            ("/api/v1/admin/diagnose", {
                'type': 'object',
                'required_fields': ['status', 'sources', 'articles']
            }),
            ("/api/v1/admin/collection-status", {
                'type': 'object',
                'required_fields': ['collection_enabled', 'health']
            }),
        ]
        
        for endpoint, expected in tests:
            result = await self.make_request("GET", endpoint, expected_content=expected)
            self.log_result(result)
        
        # Test POST admin
        result = await self.make_request("POST", "/api/v1/admin/fix-sources")
        self.log_result(result)
    
    def print_per_endpoint_results(self):
        """Affiche un tableau compact avec le résultat de CHAQUE endpoint testé."""
        # Construire des lignes : [status, method, endpoint, code, time, note]
        rows = []
        for r in self.results:
            note = r.message
            # Raccourcir les messages trop longs
            if note and len(note) > 80:
                note = note[:77] + "..."
            rows.append([r.status.value.split()[0], r.method, r.endpoint, str(r.status_code), f"{r.response_time:.2f}s", note or ""])  # status icon only
        
        # Largeurs de colonne
        widths = [0,0,0,0,0,0]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        
        headers = ["Statut", "Méthode", "Endpoint", "Code", "Temps", "Détail"]
        for i, h in enumerate(headers):
            widths[i] = max(widths[i], len(h))
        
        sep = "-" * (sum(widths) + len(widths)*3 + 1)
        print("\n[DETAIL] DÉTAIL PAR ENDPOINT\n" + sep)
        # Header
        line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
        print(line)
        print(sep)
        # Rows
        for row in rows:
            line = "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) + " |"
            print(line)
        print(sep + "\n")

    def print_summary(self):
        """Affiche un résumé détaillé des tests"""
        print("=" * 70)
        print("[SUMMARY] RÉSUMÉ COMPLET DES TESTS")
        print("=" * 70)
        
        total = len(self.results)
        passed = len([r for r in self.results if r.status == TestStatus.PASS])
        failed = len([r for r in self.results if r.status == TestStatus.FAIL])
        warned = len([r for r in self.results if r.status == TestStatus.WARN])
        content_failed = len([r for r in self.results if r.status == TestStatus.CONTENT_FAIL])
        empty_responses = len([r for r in self.results if r.status == TestStatus.EMPTY_RESPONSE])
        
        print(f"Total tests: {total}")
        print(f"[SUCCESS] Succès complets: {passed}")
        print(f"[FAILED] Échecs techniques: {failed}")
        print(f"[CONTENT_FAIL] Échecs de contenu: {content_failed}")
        print(f"[WARNED] Avertissements (e.g., 404): {warned}")
        print(f"[EMPTY] Réponses vides/nulles: {empty_responses}")
        
        success_rate = ((passed) / total) * 100 if total > 0 else 0
        quality_rate = ((passed) / (total - warned)) * 100 if (total - warned) > 0 else 0
        
        print(f"[STATS] Taux de succès global: {success_rate:.1f}%")
        print(f"[QUALITY] Taux de qualité (hors 404): {quality_rate:.1f}%")
        
        # Temps de réponse moyen
        avg_time = sum(r.response_time for r in self.results) / total if total > 0 else 0
        print(f"[TIME] Temps moyen: {avg_time:.2f}s")
        
        # Endpoints les plus lents
        slowest = sorted(self.results, key=lambda x: x.response_time, reverse=True)[:3]
        print(f"\n[SLOW_ENDPOINTS] Endpoints les plus lents:")
        for result in slowest:
            print(f"    {result.endpoint}: {result.response_time:.2f}s")
        
        # Détails des problèmes de contenu
        content_issues = [r for r in self.results if r.status == TestStatus.CONTENT_FAIL]
        if content_issues:
            print(f"\n[CONTENT_ISSUES] Problèmes de contenu détectés:")
            for result in content_issues:
                print(f"    {result.endpoint}: {result.message}")
                if result.content_checks:
                    for check in result.content_checks[:2]:
                        print(f"      - {check}")
        
        # Détails des réponses vides/nulles
        empty_issues = [r for r in self.results if r.status == TestStatus.EMPTY_RESPONSE]
        if empty_issues:
            print(f"\n[EMPTY_ENDPOINTS] Endpoints avec réponses vides ou nulles:")
            for result in empty_issues:
                print(f"    {result.endpoint}: {result.message}")
        
        # Échecs techniques
        technical_failures = [r for r in self.results if r.status == TestStatus.FAIL]
        if technical_failures:
            print(f"\n[FAILED] Échecs techniques:")
            for result in technical_failures:
                print(f"    {result.endpoint}: {result.message}")
        
        print("\n" + "=" * 70)
        
        return passed, failed, warned, content_failed, empty_responses

    async def wait_for_collection_completion(self, max_wait_minutes: int = 10) -> bool:
        """Attend que la collecte se termine"""
        print(f"[INFO] Attente de la fin de collecte (max {max_wait_minutes} minutes)...")
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        
        while time.time() - start_time < max_wait_seconds:
            try:
                # Vérifier le statut de la collecte
                result = await self.make_request("GET", "/api/v1/admin/collection-status")
                if result.status == TestStatus.PASS:
                    # Vérifier le nombre d'articles
                    articles_result = await self.make_request("GET", "/api/v1/articles?limit=1")
                    if articles_result.status == TestStatus.PASS and articles_result.response_data:
                        articles_count = len(articles_result.response_data) if isinstance(articles_result.response_data, list) else 0
                        if articles_count > 0:
                            print(f"[INFO] OK Collecte terminee avec des articles disponibles")
                            return True
                
                print(".", end="", flush=True)
                await asyncio.sleep(10)  # Attendre 10 secondes
                
            except Exception as e:
                print(f"[WARN] Erreur lors de la vérification: {e}")
                await asyncio.sleep(5)
        
        print(f"\n[WARN] Timeout après {max_wait_minutes} minutes")
        return False

    async def trigger_collection_and_enrichment(self) -> bool:
        """Déclenche la collecte et l'enrichissement automatiques"""
        print("\n" + "="*80)
        print(">> DEMARRAGE AUTOMATIQUE DE LA COLLECTE ET ENRICHISSEMENT")
        print("="*80)
        
        # 1. Déclencher la collecte manuelle
        print("\n[INFO] (1) Declenchement de la collecte manuelle...")
        collect_result = await self.make_request("POST", "/api/v1/admin/collect")
        
        if collect_result.status != TestStatus.PASS:
            print(f"[ERROR] Echec de la collecte: {collect_result.message}")
            return False
        
        print(f"[INFO] Collecte lancee: {collect_result.message}")
        
        # 2. Attendre que la collecte se termine
        print("\n[INFO] (2) Attente de la fin de collecte...")
        if not await self.wait_for_collection_completion():
            print("[WARN] Collecte peut ne pas etre terminee")
        
        # 3. Vérifier le nombre d'articles collectés
        articles_result = await self.make_request("GET", "/api/v1/admin/diagnose")
        if articles_result.status == TestStatus.PASS and articles_result.response_data:
            articles_count = articles_result.response_data.get('articles', {}).get('total', 0)
            print(f"[INFO] Articles collectes: {articles_count}")
        
        # 4. Lancer l'extraction de topics et clustering
        print("\n[INFO] (3) Extraction de topics et clustering...")
        topics_result = await self.make_request(
            "POST", 
            "/api/v1/admin/process-topics?limit=100&since_hours=24&fallback=true"
        )
        
        if topics_result.status == TestStatus.PASS:
            print(f"[INFO] Topics extraits: {topics_result.message}")
        else:
            print(f"[WARN] Extraction topics echouee: {topics_result.message}")
        
        # 5. Lancer l'analyse de sentiment
        print("\n[INFO] (4) Analyse de sentiment...")
        sentiment_result = await self.make_request(
            "POST",
            "/api/v1/admin/process-sentiment?limit=100&since_hours=24&use_llm=false&fallback=true"
        )
        
        if sentiment_result.status == TestStatus.PASS:
            print(f"[INFO] Sentiment analyse: {sentiment_result.message}")
        else:
            print(f"[WARN] Analyse sentiment echouee: {sentiment_result.message}")
        
        # 6. Vérification finale
        print("\n[INFO] (5) Verification finale...")
        final_check = await self.make_request("GET", "/api/v1/admin/diagnose")
        if final_check.status == TestStatus.PASS and final_check.response_data:
            data = final_check.response_data
            articles_count = data.get('articles', {}).get('total', 0)
            sources_count = data.get('sources', {}).get('active', 0)
            
            print(f"[INFO] Etat final:")
            print(f"  - Articles: {articles_count}")
            print(f"  - Sources actives: {sources_count}")
            
            # Test rapide des endpoints enrichis
            topics_test = await self.make_request("GET", "/api/v1/topics")
            clusters_test = await self.make_request("GET", "/api/v1/clusters?limit_clusters=5")
            
            topics_available = topics_test.status == TestStatus.PASS and topics_test.response_data
            clusters_available = clusters_test.status == TestStatus.PASS and clusters_test.response_data
            
            print(f"  - Topics disponibles: {'OK' if topics_available else 'NOK'}")
            print(f"  - Clusters disponibles: {'OK' if clusters_available else 'NOK'}")
        
        print("\n" + "="*80)
        print(">> COLLECTE ET ENRICHISSEMENT TERMINES")
        print("="*80)
        
        return True

    async def run_all_tests(self, categories: Optional[List[str]] = None):
        """Lance tous les tests ou seulement les catégories spécifiées"""
        
        all_categories = {
            'health': self.test_health_endpoints,
            'articles': self.test_articles_endpoints,
            'search': self.test_search_endpoints,
            'sources': self.test_sources_endpoints,
            'summaries': self.test_summaries_endpoints,
            'synthesis': self.test_synthesis_endpoints,
            'topics': self.test_topics_endpoints,
            'clusters': self.test_clusters_endpoints,
            'sentiment': self.test_sentiment_endpoints,
            'stats': self.test_stats_endpoints,
            'relations': self.test_relations_endpoints,
            'graph': self.test_graph_endpoints,
            'exports': self.test_exports_endpoints,
            'admin': self.test_admin_endpoints,
        }
        
        # Filtrer les catégories si spécifiées
        if categories:
            test_categories = {k: v for k, v in all_categories.items() if k in categories}
            if not test_categories:
                print(f"[ERROR] Catégories invalides: {categories}")
                print(f"Catégories disponibles: {list(all_categories.keys())}")
                return
        else:
            test_categories = all_categories

        # >> NOUVELLE FONCTIONNALITE: Collecte et enrichissement automatiques
        print("\n" + "="*80)
        print(">> NEWSAI API - TESTS AUTOMATISES AVEC COLLECTE")
        print("="*80)
        
        # Déclencher la collecte et l'enrichissement avant les tests (si pas désactivé)
        if not self.skip_collection:
            collection_success = await self.trigger_collection_and_enrichment()
            
            if not collection_success:
                print("\n[WARN] ! La collecte automatique a echoue, mais les tests continuent...")
        else:
            print("\n[INFO] -> Collecte automatique desactivee, passage direct aux tests")
        
        await self.populate_test_data()

        print("\n" + "="*80)
        print(">> DEMARRAGE DES TESTS D'ENDPOINTS")
        print("="*80)

        for category, test_method in test_categories.items():
            await test_method()

## Fonction principale et exécution du script

async def main():
    parser = argparse.ArgumentParser(description="Script de test complet pour l'API NewsAI.")
    parser.add_argument("--base-url", type=str, required=True, help="URL de base de l'API (ex: http://localhost:8000)")
    parser.add_argument("--timeout", type=int, default=30, help="Delai d'attente maximum pour chaque requete en secondes")
    parser.add_argument("--verbose", action="store_true", help="Afficher les details de chaque test")
    parser.add_argument("--no-response-preview", action="store_false", dest="show_response", help="Ne pas afficher l'apercu de la reponse API pour les tests individuels")
    parser.add_argument("--response-max-chars", type=int, default=2000, help="Nombre maximal de caracteres a afficher pour l'apercu de la reponse API")
    parser.add_argument("--only", type=str, help="Executer seulement certaines categories de tests (ex: health,articles)")
    parser.add_argument("--skip-collection", action="store_true", help="Ignorer la collecte automatique et passer directement aux tests")
    
    args = parser.parse_args()

    # Convertir les categories en liste si specifiees
    only_categories = [cat.strip() for cat in args.only.split(',')] if args.only else None

    print(f"[START] Demarrage des tests de l'API NewsAI a l'adresse: {args.base_url}")
    print(f"[TIMEOUT] Timeout par requete: {args.timeout}s")
    if only_categories:
        print(f"[CATEGORIES] Categories de tests selectionnees: {', '.join(only_categories)}")
    print("-" * 70)

    tester = None
    try:
        async with NewsAIAPITester(
            base_url=args.base_url, 
            timeout=args.timeout, 
            verbose=args.verbose, 
            show_response=args.show_response,
            response_max_chars=args.response_max_chars,
            skip_collection=args.skip_collection
        ) as tester:
            await tester.run_all_tests(categories=only_categories)
    except aiohttp.ClientConnectorError as e:
        print(f"\n[CRITICAL ERROR] Impossible de se connecter a l'API a l'adresse {args.base_url}.")
        print(f"Verifiez que l'API est en cours d'execution et accessible. Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] lors de l'execution des tests: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        if tester:
            tester.print_per_endpoint_results()
            passed, failed, warned, content_failed, empty_responses = tester.print_summary()
            
            if failed > 0 or content_failed > 0 or empty_responses > 0:
                print("\n[ALERT] DES TESTS ONT ECHOUE OU PRESENTENT DES PROBLEMES DE CONTENU.")
                sys.exit(1)
            elif warned > 0:
                print("\n[WARNING] TOUS LES TESTS TECHNIQUES ONT REUSSI, MAIS DES AVERTISSEMENTS ONT ETE EMIS (e.g., 404).")
                sys.exit(0) # Sortie reussie car ce sont des avertissements
            else:
                print("\n[SUCCESS] TOUS LES TESTS ONT REUSSI AVEC SUCCES !")
                sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())