# Guide de Redémarrage Complet - NewsIA

## 🔄 Redémarrage Local (PC actuel)

### 1. Arrêt complet du système
```bash
# Arrêter tous les conteneurs et supprimer les volumes
docker-compose down -v

# Nettoyer le système Docker (optionnel)
docker system prune -f

# Supprimer les images Docker pour rebuild complet (optionnel)
docker rmi $(docker images -q)
```

### 2. Redémarrage propre
```bash
# Rebuild et redémarrer
docker-compose up --build -d

# Vérifier l'état
docker-compose ps
docker-compose logs api
```

### 3. Test avec collecte automatique
```bash
# Test complet avec collecte automatique
python test_newsapi.py --base-url http://localhost:8000 --verbose

# Test rapide (santé + articles)
python test_newsapi.py --base-url http://localhost:8000 --only health,articles

# Test sans collecte automatique
python test_newsapi.py --base-url http://localhost:8000 --skip-collection
```

## 📦 Migration vers un autre PC

### 1. Fichiers à copier
Copiez le dossier complet `newsia (1)` avec tous les fichiers :

**Fichiers essentiels :**
- `docker-compose.yml` ✅
- `Dockerfile.api` ✅
- `requirements.txt` ✅
- `db/init.sql` ✅
- `config/rss_feeds_global.json` ✅
- `.env` ✅
- `newsapi/` (dossier complet) ✅
- `workers/` (dossier complet) ✅
- `test_newsapi.py` ✅ (avec collecte automatique)

**Fichiers générés à NE PAS copier :**
- `logs/` (sera recréé)
- Tous les fichiers `*.pyc` et `__pycache__/`
- Les fichiers temporaires de test

### 2. Prérequis sur le nouveau PC
```bash
# Installer Docker Desktop
# Télécharger depuis https://docker.com

# Vérifier l'installation
docker --version
docker-compose --version

# Installer Python 3.8+ (pour les tests)
python --version
pip install aiohttp asyncio
```

### 3. Première installation sur nouveau PC
```bash
# Aller dans le dossier du projet
cd /chemin/vers/newsia

# Construire et démarrer (première fois)
docker-compose up --build -d

# Attendre que tous les services soient healthy
docker-compose ps

# Vérifier les logs en cas de problème
docker-compose logs api
docker-compose logs db
```

### 4. Test de validation complète
```bash
# Test complet avec collecte automatique (recommandé)
python test_newsapi.py --base-url http://localhost:8000 --verbose

# Le script va automatiquement :
# 1. Déclencher la collecte d'articles
# 2. Attendre la fin de collecte
# 3. Lancer l'enrichissement (topics, sentiment)
# 4. Tester tous les endpoints
```

## 🚨 Problèmes courants et solutions

### Problème 1: Base de données vide
```bash
# Solution : Forcer la recollecte
docker-compose exec api python -c "
import asyncio
from newsapi.app.services.collector import CollectorService
asyncio.run(CollectorService().run_full_collection())
"
```

### Problème 2: Permissions Docker (Linux/Mac)
```bash
# Ajouter l'utilisateur au groupe docker
sudo usermod -aG docker $USER
# Redémarrer la session
```

### Problème 3: Ports occupés
```bash
# Vérifier les ports
netstat -tulpn | grep :8000
netstat -tulpn | grep :5432

# Modifier docker-compose.yml si nécessaire
# Changer "8000:8000" vers "8001:8000" par exemple
```

### Problème 4: Ollama non disponible
```bash
# Désactiver Ollama dans docker-compose.yml
# Commenter la section ollama si non nécessaire
```

## ✅ Validation finale

Le système est prêt quand :

1. **Containers healthy :** `docker-compose ps` montre tous les services "healthy"
2. **API accessible :** `curl http://localhost:8000/health` retourne `{"status": "ok"}`
3. **Base de données connectée :** `/health/detailed` montre `"database": "connected"`
4. **Tests passent :** `python test_newsapi.py --base-url http://localhost:8000 --only health` réussit

## 🎯 Commandes rapides de débogage

```bash
# Voir les logs en temps réel
docker-compose logs -f api

# Redémarrer un service spécifique
docker-compose restart api

# Vérifier l'état des bases de données
docker-compose exec db psql -U news -d news -c "SELECT COUNT(*) FROM articles;"

# Forcer une collecte manuelle
curl -X POST http://localhost:8000/api/v1/admin/collect

# Diagnostic complet
curl http://localhost:8000/api/v1/admin/diagnose
```

## 📝 Notes importantes

- **Premier démarrage :** Attendre 2-3 minutes pour l'initialisation complète
- **Collecte automatique :** Le script de test déclenche automatiquement la collecte
- **Performance :** Prévoir 1-2 GB d'espace disque pour les données
- **Réseau :** S'assurer que les ports 8000, 5432, 6379 sont libres