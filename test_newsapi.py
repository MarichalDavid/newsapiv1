#!/usr/bin/env python3
"""
Script de Test Complet pour MarichalDavid/newsapi
Teste tous les endpoints principaux et secondaires avec rapport détaillé
"""

import requests
import json
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from urllib.parse import quote
import csv
import io
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30
RETRY_COUNT = 2
RETRY_DELAY = 2

@dataclass
class TestResult:
    """Résultat d'un test d'endpoint"""
    endpoint: str
    method: str
    status_code: Optional[int]
    success: bool
    response_time: float
    error_message: Optional[str]
    response_data: Optional[Any]
    headers: Optional[Dict]
    test_description: str

class NewsAPITester:
    """Testeur complet pour l'API NewsAPI"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.results: List[TestResult] = []
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        
    def test_endpoint(self, endpoint: str, method: str = "GET", 
                     data: Optional[Dict] = None, 
                     params: Optional[Dict] = None,
                     description: str = "") -> TestResult:
        """Test un endpoint spécifique avec retry"""
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        for attempt in range(RETRY_COUNT + 1):
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, params=params)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=data, params=params)
                elif method.upper() == "PUT":
                    response = self.session.put(url, json=data, params=params)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, params=params)
                else:
                    raise ValueError(f"Méthode HTTP non supportée: {method}")
                
                response_time = time.time() - start_time
                
                # Essayer de parser la réponse JSON
                try:
                    response_data = response.json()
                except:
                    response_data = response.text if response.text else None
                
                result = TestResult(
                    endpoint=endpoint,
                    method=method.upper(),
                    status_code=response.status_code,
                    success=200 <= response.status_code < 300,
                    response_time=response_time,
                    error_message=None if 200 <= response.status_code < 300 else f"HTTP {response.status_code}: {response.reason}",
                    response_data=response_data,
                    headers=dict(response.headers),
                    test_description=description
                )
                break
                
            except requests.exceptions.RequestException as e:
                response_time = time.time() - start_time
                if attempt < RETRY_COUNT:
                    print(f"  ⚠️  Tentative {attempt + 1} échouée pour {endpoint}, retry dans {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    start_time = time.time()  # Reset timer for retry
                    continue
                
                result = TestResult(
                    endpoint=endpoint,
                    method=method.upper(),
                    status_code=None,
                    success=False,
                    response_time=response_time,
                    error_message=f"Erreur de connexion: {str(e)}",
                    response_data=None,
                    headers=None,
                    test_description=description
                )
                break
        
        self.results.append(result)
        return result
    
    def run_system_tests(self):
        """Tests des endpoints système"""
        print("🏥 Tests des Endpoints Système...")
        
        # Health check
        self.test_endpoint("/health", description="Health check de l'API")
        
        # Documentation
        self.test_endpoint("/docs", description="Documentation Swagger")
        self.test_endpoint("/redoc", description="Documentation ReDoc")
        self.test_endpoint("/openapi.json", description="Schéma OpenAPI")
    
    def run_articles_tests(self):
        """Tests des endpoints articles"""
        print("📰 Tests des Endpoints Articles...")
        
        # Articles de base
        self.test_endpoint("/api/v1/articles", description="Tous les articles")
        self.test_endpoint("/api/v1/articles", params={"limit": 5}, description="Articles avec limite")
        self.test_endpoint("/api/v1/articles", params={"limit": 10, "lang": "fr"}, description="Articles français")
        
        # Test avec pagination
        self.test_endpoint("/api/v1/articles", params={"limit": 5, "offset": 10}, description="Articles avec pagination")
        
        # Test avec filtres
        self.test_endpoint("/api/v1/articles", params={
            "limit": 5,
            "date_from": (datetime.now() - timedelta(days=7)).isoformat()
        }, description="Articles de la semaine dernière")
        
        # Test recherche (si disponible)
        self.test_endpoint("/api/v1/articles/search", params={"q": "test"}, description="Recherche d'articles")
        
        # Test article individuel (ID générique)
        self.test_endpoint("/api/v1/articles/1", description="Article spécifique (ID 1)")
        self.test_endpoint("/api/v1/articles/999999", description="Article inexistant")
    
    def run_sources_tests(self):
        """Tests des endpoints sources"""
        print("🔄 Tests des Endpoints Sources...")
        
        # Gestion des sources
        self.test_endpoint("/api/v1/sources", description="Liste des sources")
        self.test_endpoint("/api/v1/sources/refresh", method="POST", description="Refresh des sources")
        self.test_endpoint("/api/v1/sources/1", description="Source spécifique")
        
        # Test d'ajout de source (peut échouer si pas d'auth)
        self.test_endpoint("/api/v1/sources", method="POST", data={
            "url": "https://example.com/rss.xml",
            "domain": "example.com",
            "active": True
        }, description="Ajouter une source")
    
    def run_topics_tests(self):
        """Tests des endpoints topics"""
        print("🏷️ Tests des Endpoints Topics...")
        
        # Topics de base
        self.test_endpoint("/api/v1/topics", description="Tous les topics")
        self.test_endpoint("/api/v1/topics", params={"lang": "fr"}, description="Topics français")
        self.test_endpoint("/api/v1/topics", params={"min_count": 5}, description="Topics avec minimum d'articles")
        
        # Topic spécifique
        self.test_endpoint("/api/v1/topics/1", description="Topic spécifique (ID 1)")
        self.test_endpoint("/api/v1/topics/1/articles", description="Articles du topic 1")
        
        # Topic inexistant
        self.test_endpoint("/api/v1/topics/999999", description="Topic inexistant")
    
    def run_clusters_tests(self):
        """Tests des endpoints clusters"""
        print("🔗 Tests des Endpoints Clusters...")
        
        # Clusters de base
        self.test_endpoint("/api/v1/clusters", description="Tous les clusters")
        self.test_endpoint("/api/v1/clusters", params={"limit": 10}, description="Clusters avec limite")
        self.test_endpoint("/api/v1/clusters", params={"min_size": 3}, description="Clusters avec taille minimum")
        
        # Cluster spécifique
        self.test_endpoint("/api/v1/clusters/1", description="Cluster spécifique")
        self.test_endpoint("/api/v1/clusters/1/articles", description="Articles du cluster 1")
    
    def run_sentiment_tests(self):
        """Tests des endpoints sentiment"""
        print("📈 Tests des Endpoints Sentiment...")
        
        # Sentiment par topic
        for topic_id in [1, 2, 5]:
            self.test_endpoint(f"/api/v1/sentiment/topic/{topic_id}", 
                             params={"days": 7}, 
                             description=f"Sentiment topic {topic_id} (7 jours)")
            
            self.test_endpoint(f"/api/v1/sentiment/topic/{topic_id}", 
                             params={"days": 30}, 
                             description=f"Sentiment topic {topic_id} (30 jours)")
        
        # Sentiment par source
        test_sources = [
            "www.bbc.com",
            "www.lemonde.fr", 
            "www.cnn.com",
            "techcrunch.com",
            "www.reuters.com"
        ]
        
        for source in test_sources:
            self.test_endpoint(f"/api/v1/sentiment/source/{source}", 
                             params={"days": 7}, 
                             description=f"Sentiment {source} (7 jours)")
        
        # Tests avec paramètres avancés
        self.test_endpoint("/api/v1/sentiment/source/www.bbc.com", 
                         params={"days": 14, "granularity": "daily"}, 
                         description="Sentiment BBC granularité quotidienne")
        
        # Sentiment global (si disponible)
        self.test_endpoint("/api/v1/sentiment/global", description="Sentiment global")
        
        # Test cas d'erreur
        self.test_endpoint("/api/v1/sentiment/source/inexistant.com", 
                         params={"days": 7}, 
                         description="Sentiment source inexistante")
        
        self.test_endpoint("/api/v1/sentiment/topic/999999", 
                         params={"days": 7}, 
                         description="Sentiment topic inexistant")
    
    def run_summaries_tests(self):
        """Tests des endpoints synthèses"""
        print("📊 Tests des Endpoints Synthèses...")
        
        # Synthèses générales
        self.test_endpoint("/api/v1/summaries/general", description="Synthèse générale par défaut")
        
        self.test_endpoint("/api/v1/summaries/general", 
                         params={"since_hours": 24, "target_sentences": 10}, 
                         description="Synthèse 24h, 10 phrases")
        
        self.test_endpoint("/api/v1/summaries/general", 
                         params={"since_hours": 48, "target_sentences": 20, "lang": "fr"}, 
                         description="Synthèse 48h, 20 phrases, français")
        
        # Synthèses par topic
        self.test_endpoint("/api/v1/summaries/topic/1", description="Synthèse topic 1")
        
        # Synthèses par source
        self.test_endpoint("/api/v1/summaries/source/www.bbc.com", description="Synthèse BBC")
        
        # Trending topics
        self.test_endpoint("/api/v1/summaries/trending", description="Topics en tendance")
    
    def run_stats_tests(self):
        """Tests des endpoints statistiques"""
        print("📊 Tests des Endpoints Statistiques...")
        
        # Stats générales
        self.test_endpoint("/api/v1/stats/general", description="Statistiques générales")
        self.test_endpoint("/api/v1/stats/sources", description="Statistiques par source")
        self.test_endpoint("/api/v1/stats/topics", description="Statistiques par topic")
        self.test_endpoint("/api/v1/stats/timeline", description="Timeline des statistiques")
        
        # Stats avec paramètres
        self.test_endpoint("/api/v1/stats/timeline", 
                         params={"granularity": "daily", "days": 30}, 
                         description="Timeline quotidienne 30 jours")
    
    def run_export_tests(self):
        """Tests des endpoints export"""
        print("📥 Tests des Endpoints Export...")
        
        # Export articles CSV
        self.test_endpoint("/api/v1/exports/articles.csv", description="Export articles CSV de base")
        
        self.test_endpoint("/api/v1/exports/articles.csv", 
                         params={"limit": 10}, 
                         description="Export articles CSV limité")
        
        self.test_endpoint("/api/v1/exports/articles.csv", 
                         params={"lang": "fr", "limit": 5}, 
                         description="Export articles français CSV")
        
        self.test_endpoint("/api/v1/exports/articles.csv", 
                         params={
                             "lang": "fr", 
                             "topic": "tech",
                             "date_from": (datetime.now() - timedelta(days=7)).isoformat(),
                             "limit": 20
                         }, 
                         description="Export articles tech français 7 jours")
        
        # Autres exports
        self.test_endpoint("/api/v1/exports/sentiment.csv", description="Export sentiment CSV")
        self.test_endpoint("/api/v1/exports/stats.json", description="Export stats JSON")
        self.test_endpoint("/api/v1/exports/topics.json", description="Export topics JSON")
    
    def run_search_tests(self):
        """Tests des endpoints recherche"""
        print("🔍 Tests des Endpoints Recherche...")
        
        # Recherche globale
        search_queries = ["intelligence artificielle", "climate change", "tech", "politics"]
        
        for query in search_queries:
            self.test_endpoint("/api/v1/search", 
                             params={"q": query}, 
                             description=f"Recherche globale: {query}")
        
        # Recherche avancée
        self.test_endpoint("/api/v1/search", 
                         params={
                             "q": "AI", 
                             "lang": "en", 
                             "sentiment": "positive",
                             "date_range": "last_week"
                         }, 
                         description="Recherche avancée AI positive")
        
        # Recherche par entités
        self.test_endpoint("/api/v1/search/entities", 
                         params={"entity_type": "PERSON"}, 
                         description="Recherche entités personnes")
        
        # Recherche similarité
        self.test_endpoint("/api/v1/search/similar/1", description="Articles similaires à l'article 1")
    
    def run_admin_tests(self):
        """Tests des endpoints admin (peuvent nécessiter auth)"""
        print("🛠️ Tests des Endpoints Administration...")
        
        # Configuration
        self.test_endpoint("/api/v1/admin/config", description="Configuration système")
        
        # Monitoring
        self.test_endpoint("/api/v1/admin/monitoring", description="Monitoring système")
        
        # Jobs
        self.test_endpoint("/api/v1/admin/jobs", description="Liste des jobs")
        
        # DB stats
        self.test_endpoint("/api/v1/admin/db/stats", description="Statistiques base de données")
    
    def run_auth_tests(self):
        """Tests des endpoints authentification"""
        print("🔐 Tests des Endpoints Authentification...")
        
        # Test login (peut échouer si pas configuré)
        self.test_endpoint("/api/v1/auth/login", 
                         method="POST", 
                         data={"username": "test", "password": "test"}, 
                         description="Test login")
        
        # Test profil
        self.test_endpoint("/api/v1/auth/me", description="Profil utilisateur")
    
    def run_edge_case_tests(self):
        """Tests des cas limites et d'erreur"""
        print("⚠️ Tests des Cas Limites...")
        
        # Paramètres invalides
        self.test_endpoint("/api/v1/articles", 
                         params={"limit": -1}, 
                         description="Limite négative")
        
        self.test_endpoint("/api/v1/articles", 
                         params={"limit": 999999}, 
                         description="Limite très élevée")
        
        self.test_endpoint("/api/v1/sentiment/topic/abc", 
                         description="Topic ID non numérique")
        
        self.test_endpoint("/api/v1/sentiment/source/", 
                         description="Source vide")
        
        # Dates invalides
        self.test_endpoint("/api/v1/articles", 
                         params={"date_from": "invalid-date"}, 
                         description="Date invalide")
        
        # Endpoints inexistants
        self.test_endpoint("/api/v1/nonexistent", description="Endpoint inexistant")
        self.test_endpoint("/api/v2/articles", description="Version API inexistante")
    
    def run_all_tests(self):
        """Exécute tous les tests"""
        print("🚀 Début des tests complets de l'API NewsAPI")
        print("=" * 60)
        
        start_time = time.time()
        
        # Tests par catégorie
        self.run_system_tests()
        self.run_articles_tests()
        self.run_sources_tests()
        self.run_topics_tests()
        self.run_clusters_tests()
        self.run_sentiment_tests()
        self.run_summaries_tests()
        self.run_stats_tests()
        self.run_export_tests()
        self.run_search_tests()
        self.run_admin_tests()
        self.run_auth_tests()
        self.run_edge_case_tests()
        
        total_time = time.time() - start_time
        
        print(f"\n✅ Tests terminés en {total_time:.2f} secondes")
        print("=" * 60)
    
    def generate_report(self) -> str:
        """Génère un rapport détaillé des tests"""
        if not self.results:
            return "Aucun test exécuté"
        
        # Statistiques
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests) * 100
        avg_response_time = sum(r.response_time for r in self.results) / total_tests
        
        # Grouper par catégorie
        categories = {}
        for result in self.results:
            category = self.get_category(result.endpoint)
            if category not in categories:
                categories[category] = []
            categories[category].append(result)
        
        # Générer le rapport
        report = []
        report.append("📊 RAPPORT DE TEST COMPLET - NewsAPI")
        report.append("=" * 80)
        report.append(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"🎯 URL de base: {self.base_url}")
        report.append("")
        
        # Résumé exécutif
        report.append("📈 RÉSUMÉ EXÉCUTIF")
        report.append("-" * 40)
        report.append(f"Total des tests: {total_tests}")
        report.append(f"✅ Succès: {successful_tests}")
        report.append(f"❌ Échecs: {failed_tests}")
        report.append(f"📊 Taux de succès: {success_rate:.1f}%")
        report.append(f"⏱️ Temps de réponse moyen: {avg_response_time:.3f}s")
        report.append("")
        
        # Résumé par catégorie
        report.append("📋 RÉSUMÉ PAR CATÉGORIE")
        report.append("-" * 40)
        for category, tests in categories.items():
            cat_success = sum(1 for t in tests if t.success)
            cat_total = len(tests)
            cat_rate = (cat_success / cat_total * 100) if cat_total > 0 else 0
            status = "✅" if cat_rate == 100 else "⚠️" if cat_rate >= 50 else "❌"
            report.append(f"{status} {category}: {cat_success}/{cat_total} ({cat_rate:.1f}%)")
        report.append("")
        
        # Tests échoués (priorité)
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            report.append("❌ TESTS ÉCHOUÉS (DÉTAILS)")
            report.append("-" * 40)
            for result in failed_results:
                report.append(f"🔴 {result.method} {result.endpoint}")
                report.append(f"   Description: {result.test_description}")
                report.append(f"   Erreur: {result.error_message}")
                if result.status_code:
                    report.append(f"   Code HTTP: {result.status_code}")
                report.append(f"   Temps: {result.response_time:.3f}s")
                report.append("")
        
        # Détails par catégorie
        report.append("📊 DÉTAILS PAR CATÉGORIE")
        report.append("-" * 40)
        
        for category, tests in categories.items():
            report.append(f"\n🔹 {category.upper()}")
            report.append("-" * 20)
            
            for result in tests:
                status = "✅" if result.success else "❌"
                report.append(f"{status} {result.method} {result.endpoint}")
                report.append(f"   📝 {result.test_description}")
                
                if result.success:
                    report.append(f"   ✅ HTTP {result.status_code} - {result.response_time:.3f}s")
                    if result.response_data:
                        # Informations sur la réponse
                        if isinstance(result.response_data, dict):
                            if 'count' in result.response_data:
                                report.append(f"   📊 Éléments retournés: {result.response_data.get('count', 'N/A')}")
                            elif isinstance(result.response_data, list):
                                report.append(f"   📊 Éléments retournés: {len(result.response_data)}")
                        elif isinstance(result.response_data, list):
                            report.append(f"   📊 Éléments retournés: {len(result.response_data)}")
                else:
                    report.append(f"   ❌ {result.error_message}")
                    if result.status_code:
                        report.append(f"   🔢 HTTP {result.status_code}")
                
                report.append("")
        
        # Recommandations
        report.append("💡 RECOMMANDATIONS")
        report.append("-" * 40)
        
        if failed_tests == 0:
            report.append("🎉 Excellent! Tous les tests sont passés.")
        elif success_rate >= 80:
            report.append("👍 Bon score global. Corriger les quelques endpoints défaillants.")
        elif success_rate >= 50:
            report.append("⚠️ Score moyen. Révision nécessaire des endpoints échoués.")
        else:
            report.append("🚨 Score faible. Révision complète recommandée.")
        
        # Actions recommandées
        if any(r.error_message and "connexion" in r.error_message.lower() for r in self.results):
            report.append("🔧 Vérifier que l'API est démarrée: docker compose up -d")
        
        if any(r.status_code == 500 for r in self.results):
            report.append("🔧 Erreurs 500 détectées: vérifier les logs serveur")
        
        if any(r.status_code == 404 for r in self.results):
            report.append("🔧 Endpoints 404: vérifier la documentation /docs")
        
        report.append("")
        report.append("📚 Pour plus d'infos: http://localhost:8000/docs")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def get_category(self, endpoint: str) -> str:
        """Détermine la catégorie d'un endpoint"""
        if endpoint in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return "Système"
        elif "/articles" in endpoint:
            return "Articles"
        elif "/sources" in endpoint:
            return "Sources"
        elif "/topics" in endpoint:
            return "Topics"
        elif "/clusters" in endpoint:
            return "Clusters"
        elif "/sentiment" in endpoint:
            return "Sentiment"
        elif "/summaries" in endpoint:
            return "Synthèses"
        elif "/stats" in endpoint:
            return "Statistiques"
        elif "/exports" in endpoint:
            return "Export"
        elif "/search" in endpoint:
            return "Recherche"
        elif "/admin" in endpoint:
            return "Administration"
        elif "/auth" in endpoint:
            return "Authentification"
        else:
            return "Autres"
    
    def save_report(self, filename: str = None):
        """Sauvegarde le rapport dans un fichier"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"newsapi_test_report_{timestamp}.txt"
        
        report = self.generate_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 Rapport sauvegardé: {filename}")
        return filename
    
    def save_csv_report(self, filename: str = None):
        """Sauvegarde un rapport CSV détaillé"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"newsapi_test_results_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Endpoint', 'Method', 'Status_Code', 'Success', 
                'Response_Time', 'Error_Message', 'Description', 'Category'
            ])
            
            for result in self.results:
                writer.writerow([
                    result.endpoint,
                    result.method,
                    result.status_code or '',
                    result.success,
                    f"{result.response_time:.3f}",
                    result.error_message or '',
                    result.test_description,
                    self.get_category(result.endpoint)
                ])
        
        print(f"📊 Rapport CSV sauvegardé: {filename}")
        return filename

def main():
    """Fonction principale"""
    print("🧪 Script de Test Complet - NewsAPI")
    print("Assurez-vous que l'API est démarrée: docker compose up -d")
    
    # Demander confirmation
    try:
        response = input("\nCommencer les tests? (y/N): ").strip().lower()
        if response != 'y':
            print("Tests annulés.")
            return
    except KeyboardInterrupt:
        print("\nTests annulés.")
        return
    
    # Initialiser le testeur
    tester = NewsAPITester()
    
    try:
        # Exécuter tous les tests
        tester.run_all_tests()
        
        # Générer et afficher le rapport
        print("\n" + tester.generate_report())
        
        # Sauvegarder les rapports
        txt_file = tester.save_report()
        csv_file = tester.save_csv_report()
        
        print(f"\n📁 Fichiers générés:")
        print(f"   📄 {txt_file}")
        print(f"   📊 {csv_file}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrompus par l'utilisateur")
        if tester.results:
            print("Génération du rapport partiel...")
            print(tester.generate_report())
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        if tester.results:
            print("Génération du rapport partiel...")
            print(tester.generate_report())

if __name__ == "__main__":
    main()