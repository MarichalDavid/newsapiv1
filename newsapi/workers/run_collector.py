# newsapi/workers/run_collector.py - Worker principal corrigé

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime
from pathlib import Path

# ✅ CORRECTION: Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# ✅ CORRECTION: Import avec gestion d'erreur améliorée
try:
    from app.services.collector import run_collection_once, get_collection_health
    from app.core.db import SessionLocal
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Current working directory:", os.getcwd())
    print("Python path:", sys.path)
    print("Make sure you're running from the correct directory")
    sys.exit(1)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/collector.log') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

class CollectorWorker:
    """Worker principal pour la collecte d'articles"""
    
    def __init__(self):
        self.running = False
        self.collection_interval = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "30")) * 60
        self.enable_auto_collection = os.getenv("ENABLE_AUTO_COLLECTION", "true").lower() == "true"
        self.max_retries = int(os.getenv("WORKER_RETRY_ATTEMPTS", "3"))
        
    async def setup_signal_handlers(self):
        """Configure les gestionnaires de signaux pour arrêt propre"""
        def signal_handler(signum, frame):
            logger.info(f"Signal {signum} reçu, arrêt du worker...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_collection_cycle(self):
        """Exécute un cycle de collecte avec gestion d'erreur robuste"""
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                logger.info(f"🔄 Début du cycle de collecte (tentative {retry_count + 1}/{self.max_retries})")
                
                # ✅ CORRECTION: Gérer la session de base de données proprement
                async with SessionLocal() as session:
                    result = await run_collection_once(session)
                    
                    if result.get("articles", 0) > 0:
                        logger.info(f"✅ Collecte réussie: {result['articles']} articles")
                    else:
                        logger.warning("⚠️ Aucun article collecté")
                
                logger.info("✅ Cycle de collecte terminé avec succès")
                return True
                
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Erreur lors de la collecte (tentative {retry_count}/{self.max_retries}): {e}")
                
                if retry_count < self.max_retries:
                    wait_time = min(60 * retry_count, 300)
                    logger.info(f"⏳ Attente de {wait_time}s avant nouvelle tentative...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("❌ Échec de toutes les tentatives de collecte")
                    return False
        
        return False
    
    async def health_check(self):
        """Vérification de santé du système"""
        try:
            health = await get_collection_health()
            logger.info(f"📊 Santé système: {health['status']} - {health.get('total_articles', 0)} articles")
            return health
        except Exception as e:
            logger.error(f"❌ Erreur health check: {e}")
            return {"status": "error", "error": str(e)}
    
    async def diagnose_sources(self):
        """Diagnostic des sources disponibles"""
        try:
            async with SessionLocal() as session:
                from sqlalchemy import text
                
                # Compter les sources
                result = await session.execute(text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE active = true) as active,
                        COUNT(*) FILTER (WHERE active = false) as inactive
                    FROM sources
                """))
                stats = result.fetchone()
                
                logger.info(f"📊 Sources: {stats[1]} actives / {stats[0]} total")
                
                if stats[1] == 0:
                    logger.warning("⚠️ AUCUNE SOURCE ACTIVE!")
                    
                    # Lister quelques sources pour diagnostic
                    result = await session.execute(text("""
                        SELECT id, name, feed_url, active 
                        FROM sources 
                        ORDER BY id 
                        LIMIT 5
                    """))
                    sample_sources = result.fetchall()
                    
                    logger.info("📋 Échantillon de sources:")
                    for source in sample_sources:
                        status = "✅" if source[3] else "❌"
                        logger.info(f"  {status} [{source[0]}] {source[1]} -> {source[2]}")
                
                return {
                    "total": stats[0],
                    "active": stats[1],
                    "inactive": stats[2]
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur diagnostic sources: {e}")
            return {"error": str(e)}
    
    async def start(self):
        """Démarre le worker principal"""
        logger.info("🚀 Démarrage du CollectorWorker")
        logger.info(f"📅 Intervalle de collecte: {self.collection_interval/60:.1f} minutes")
        logger.info(f"🔄 Collecte automatique: {'activée' if self.enable_auto_collection else 'désactivée'}")
        
        await self.setup_signal_handlers()
        self.running = True
        
        # Diagnostic initial
        await self.diagnose_sources()
        
        # Health check initial
        await self.health_check()
        
        # Première collecte immédiate si activée
        if self.enable_auto_collection:
            logger.info("🎯 Exécution de la collecte initiale...")
            await self.run_collection_cycle()
        
        # Boucle principale
        last_collection = datetime.now()
        
        while self.running:
            try:
                await asyncio.sleep(10)
                
                if not self.running:
                    break
                
                now = datetime.now()
                time_since_last = (now - last_collection).total_seconds()
                
                # Collecte automatique
                if self.enable_auto_collection and time_since_last >= self.collection_interval:
                    logger.info("⏰ Heure de collecte automatique")
                    success = await self.run_collection_cycle()
                    
                    if success:
                        last_collection = now
                    else:
                        # Attendre un peu plus en cas d'échec
                        await asyncio.sleep(300)
                
                # Health check périodique (toutes les heures)
                if time_since_last % 3600 < 10:
                    await self.health_check()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Worker annulé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle principale: {e}")
                await asyncio.sleep(30)
        
        logger.info("🏁 CollectorWorker arrêté")

async def main():
    """Point d'entrée principal du worker"""
    try:
        # Vérifier l'environnement
        logger.info("🔍 Vérification de l'environnement...")
        
        # Vérifier la connexion à la base de données
        try:
            async with SessionLocal() as session:
                from sqlalchemy import text
                result = await session.execute(text("SELECT 1"))
                logger.info("✅ Connexion base de données OK")
        except Exception as e:
            logger.error(f"❌ Erreur connexion base de données: {e}")
            sys.exit(1)
        
        # Démarrer le worker
        worker = CollectorWorker()
        await worker.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 Interruption clavier reçue")
    except Exception as e:
        logger.error(f"❌ Erreur fatale du worker: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Arrêt du worker")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)