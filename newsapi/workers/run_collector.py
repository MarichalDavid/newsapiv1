import asyncio
import os
from app.core.db import get_session
from app.services.collector import run_collection_once
from sqlalchemy import text
from app.services.topics_bertopic import build_and_assign as build_topics
from app.services.sentiment_simple import label_text
from app.services.facts import extract_facts

# ✅ NOUVEAU: Configuration via variables d'environnement
# Utiliser votre variable existante en priorité, sinon fallback sur la nouvelle
COLLECTION_INTERVAL_MINUTES = int(os.getenv("COLLECTOR_DEFAULT_FREQUENCY_MIN", 
                                           os.getenv("COLLECTION_INTERVAL_MINUTES", "30")))
ENABLE_AUTO_COLLECTION = os.getenv("ENABLE_AUTO_COLLECTION", "true").lower() == "true"
ENABLE_TOPICS_REFRESH = os.getenv("ENABLE_TOPICS_REFRESH", "true").lower() == "true"
ENABLE_SENTIMENT_AGG = os.getenv("ENABLE_SENTIMENT_AGG", "true").lower() == "true"

print(f"🔧 Configuration Worker:")
print(f"   - Collecte auto: {'ON' if ENABLE_AUTO_COLLECTION else 'OFF'}")
print(f"   - Intervalle: {COLLECTION_INTERVAL_MINUTES} minutes")
print(f"   - Topics BERTopic: {'ON' if ENABLE_TOPICS_REFRESH else 'OFF'}")
print(f"   - Agrégation sentiment: {'ON' if ENABLE_SENTIMENT_AGG else 'OFF'}")

async def _aggregate_sentiment(session):
    """Agrégation des sentiments par source et date"""
    if not ENABLE_SENTIMENT_AGG:
        return
        
    try:
        await session.execute(text("""
            INSERT INTO source_sentiment_daily(d, domain, pos_count, neu_count, neg_count)
            SELECT current_date, domain,
                SUM((COALESCE(sentiment_label,'neu')='pos')::int),
                SUM((COALESCE(sentiment_label,'neu')='neu')::int),
                SUM((COALESCE(sentiment_label,'neu')='neg')::int)
            FROM articles
            WHERE published_at >= current_date
            GROUP BY domain
            ON CONFLICT (d, domain) DO UPDATE SET
                pos_count=EXCLUDED.pos_count, neu_count=EXCLUDED.neu_count, neg_count=EXCLUDED.neg_count
        """))
        await session.commit()
        print("✅ Agrégation sentiment terminée")
    except Exception as e:
        print(f"❌ Erreur agrégation sentiment: {e}")

async def _refresh_mv(session):
    """Rafraîchissement des vues matérialisées"""
    try:
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topics_daily"))
        await session.commit()
        print("✅ Vue matérialisée rafraîchie (CONCURRENTLY)")
    except Exception:
        try:
            await session.execute(text("REFRESH MATERIALIZED VIEW mv_topics_daily"))
            await session.commit()
            print("✅ Vue matérialisée rafraîchie")
        except Exception as e:
            print(f"❌ Erreur rafraîchissement vue: {e}")

async def main():
    """Boucle principale du worker avec configuration flexible"""
    
    if not ENABLE_AUTO_COLLECTION:
        print("❌ Collecte automatique désactivée (ENABLE_AUTO_COLLECTION=false)")
        print("   Le worker s'arrête. Utilisez l'endpoint /api/v1/admin/collect pour des collectes manuelles.")
        return
    
    print(f"🚀 Démarrage du worker de collecte (intervalle: {COLLECTION_INTERVAL_MINUTES}min)")
    
    # Compteurs pour les tâches périodiques
    topics_refresh_counter = 0
    mv_refresh_counter = 0
    agg_counter = 0
    
    # Calcul des intervalles basés sur votre configuration existante
    try:
        from app.core.config import settings
        base_freq = getattr(settings, 'DEFAULT_FREQ_MIN', COLLECTION_INTERVAL_MINUTES)
    except:
        base_freq = COLLECTION_INTERVAL_MINUTES  # Fallback
    
    # Intervalles pour les tâches (en cycles de collecte)
    topics_interval = max(1, (6*60) // base_freq)     # Topics toutes les 6h
    mv_interval = max(1, (30) // base_freq)           # MV toutes les 30min  
    agg_interval = max(1, (10) // base_freq)          # Sentiment toutes les 10min
    
    while True:
        cycle_start = asyncio.get_event_loop().time()
        
        # 1. Collecte principale (toujours)
        async for session in get_session():
            try:
                print(f"📥 Début cycle de collecte (intervalle: {COLLECTION_INTERVAL_MINUTES}min)")
                await run_collection_once(session)
                print("✅ Collecte terminée")
            except Exception as e:
                print(f"❌ Erreur collecte: {e}", flush=True)
            break
        
        # 2. Tâches périodiques
        topics_refresh_counter += 1
        mv_refresh_counter += 1  
        agg_counter += 1
        
        # Topics BERTopic (toutes les 6h par défaut)
        if ENABLE_TOPICS_REFRESH and topics_refresh_counter >= topics_interval:
            try:
                print("🧠 Mise à jour des topics BERTopic...")
                async for s in get_session():
                    await build_topics(s)
                    break
                print("✅ Topics BERTopic mis à jour")
            except Exception as e:
                print(f'❌ Erreur topics: {e}')
            topics_refresh_counter = 0
        
        # Vue matérialisée (toutes les 30min par défaut)
        if mv_refresh_counter >= mv_interval:
            try:
                async for s in get_session():
                    await _refresh_mv(s)
                    break
            except Exception as e:
                print(f'❌ Erreur MV refresh: {e}')
            mv_refresh_counter = 0
        
        # Agrégation sentiment (toutes les 10min par défaut)
        if agg_counter >= agg_interval:
            try:
                async for s in get_session():
                    await _aggregate_sentiment(s)
                    break
            except Exception as e:
                print(f'❌ Erreur agrégation: {e}')
            agg_counter = 0
        
        # 3. Attente jusqu'au prochain cycle
        cycle_duration = asyncio.get_event_loop().time() - cycle_start
        sleep_time = max(0, (COLLECTION_INTERVAL_MINUTES * 60) - cycle_duration)
        
        if sleep_time > 0:
            print(f"⏰ Prochain cycle dans {sleep_time/60:.1f} minutes")
            await asyncio.sleep(sleep_time)
        else:
            print("⚠️  Cycle plus long que l'intervalle configuré")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Worker arrêté par l'utilisateur")
    except Exception as e:
        print(f"💥 Erreur fatale worker: {e}")
        import traceback
        traceback.print_exc()