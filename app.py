from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
from functools import wraps
import requests
import json

# Création de l'application Flask
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '32015@1a')

# Correction pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialisation de la base de données
db = SQLAlchemy(app)

# --- CONFIGURATION API DU SITE PRINCIPAL ---
SITE_URL = os.environ.get('SITE_URL', 'https://labmathscsmaubmar.org')
API_KEY = os.environ.get('API_KEY', 'labmath_api_secret_2024')

print(f"🌐 Site principal configuré: {SITE_URL}")
print(f"🔑 Clé API configurée: {'Oui' if API_KEY else 'Non'}")

# --- DÉCORATEUR SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODÈLES ---
class Activite(db.Model):
    __tablename__ = 'activites'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    contenu = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    auteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_publie = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Annonce(db.Model):
    __tablename__ = 'annonces'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Offre(db.Model):
    __tablename__ = 'offres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

# --- FONCTIONS DE SYNCHRONISATION ---
def get_api_headers():
    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
    }

def check_site_connection():
    if not API_KEY:
        return False, "Clé API non configurée"
    try:
        response = requests.get(f"{SITE_URL}/api/health", timeout=5)
        return response.status_code == 200, "Connecté" if response.status_code == 200 else f"Erreur {response.status_code}"
    except:
        return False, "Site inaccessible"

def sync_activite_to_site(activite):
    if not API_KEY or not activite.est_publie:
        return False, "Non synchronisé"
    try:
        data = {
            'id': str(activite.id),
            'titre': activite.titre,
            'description': activite.description or '',
            'contenu': activite.contenu or '',
            'image_url': activite.image_url or '',
            'auteur': activite.auteur or 'Admin',
            'est_publie': activite.est_publie,
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else datetime.utcnow().isoformat()
        }
        response = requests.post(f"{SITE_URL}/api/activites/{activite.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            activite.last_sync = datetime.utcnow()
            activite.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        activite.sync_status = 'failed'
        activite.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_realisation_to_site(realisation):
    if not API_KEY:
        return False, "Clé API non configurée"
    try:
        data = {
            'id': str(realisation.id),
            'titre': realisation.titre,
            'description': realisation.description or '',
            'image_url': realisation.image_url or '',
            'categorie': realisation.categorie or '',
            'date_realisation': realisation.date_realisation.isoformat() if realisation.date_realisation else None,
            'date_creation': realisation.date_creation.isoformat() if realisation.date_creation else datetime.utcnow().isoformat()
        }
        response = requests.post(f"{SITE_URL}/api/realisations/{realisation.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            realisation.last_sync = datetime.utcnow()
            realisation.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        realisation.sync_status = 'failed'
        realisation.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_annonce_to_site(annonce):
    if not API_KEY or not annonce.est_active:
        return False, "Non synchronisé"
    try:
        data = {
            'id': str(annonce.id),
            'titre': annonce.titre,
            'contenu': annonce.contenu or '',
            'type_annonce': annonce.type_annonce or 'info',
            'date_debut': annonce.date_debut.isoformat() if annonce.date_debut else None,
            'date_fin': annonce.date_fin.isoformat() if annonce.date_fin else None,
            'date_creation': annonce.date_creation.isoformat() if annonce.date_creation else datetime.utcnow().isoformat(),
            'est_active': annonce.est_active
        }
        response = requests.post(f"{SITE_URL}/api/annonces/{annonce.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            annonce.last_sync = datetime.utcnow()
            annonce.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        annonce.sync_status = 'failed'
        annonce.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_offre_to_site(offre):
    if not API_KEY or not offre.est_active:
        return False, "Non synchronisé"
    try:
        data = {
            'id': str(offre.id),
            'titre': offre.titre,
            'description': offre.description or '',
            'type_offre': offre.type_offre or 'autre',
            'lieu': offre.lieu or '',
            'date_limite': offre.date_limite.isoformat() if offre.date_limite else None,
            'date_creation': offre.date_creation.isoformat() if offre.date_creation else datetime.utcnow().isoformat(),
            'est_active': offre.est_active
        }
        response = requests.post(f"{SITE_URL}/api/offres/{offre.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            offre.last_sync = datetime.utcnow()
            offre.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        offre.sync_status = 'failed'
        offre.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def delete_from_site(model_type, item_id):
    if not API_KEY:
        return False, "Clé API non configurée"
    try:
        url = f"{SITE_URL}/api/{model_type}s/{item_id}"
        response = requests.delete(url, headers=get_api_headers(), timeout=10)
        return response.status_code in [200, 204], "Supprimé" if response.status_code in [200, 204] else f"Erreur {response.status_code}"
    except Exception as e:
        return False, str(e)[:50]

# --- ROUTES AUTHENTIFICATION ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['user_id'] = 1
            session['username'] = username
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('login'))

# --- ROUTE UNIQUE POUR L'ADMIN ---
@app.route('/dashboard')
@app.route('/admin')
@login_required
def admin_panel():
    """Interface admin unique avec toutes les sections"""
    try:
        # Statistiques pour le dashboard
        stats = {
            'activities_count': Activite.query.count(),
            'realisations_count': Realisation.query.count(),
            'annonces_count': Annonce.query.count(),
            'offres_count': Offre.query.count(),
            'activities_published': Activite.query.filter_by(est_publie=True).count(),
            'annonces_active': Annonce.query.filter_by(est_active=True).count(),
            'offres_active': Offre.query.filter_by(est_active=True).count(),
            'sync_failed': Activite.query.filter_by(sync_status='failed').count() +
                          Realisation.query.filter_by(sync_status='failed').count() +
                          Annonce.query.filter_by(sync_status='failed').count() +
                          Offre.query.filter_by(sync_status='failed').count()
        }
        
        # Vérification connexion site principal
        site_connected, site_message = check_site_connection()
        stats['site_connected'] = site_connected
        stats['site_message'] = site_message
        stats['api_key_configured'] = bool(API_KEY)
        
        # Récupérer toutes les données pour l'admin
        activites = Activite.query.order_by(Activite.date_creation.desc()).all()
        realisations = Realisation.query.order_by(Realisation.date_creation.desc()).all()
        annonces = Annonce.query.order_by(Annonce.date_creation.desc()).all()
        offres = Offre.query.order_by(Offre.date_creation.desc()).all()
        
        # 5 derniers éléments
        recent_activities = activites[:5]
        recent_annonces = annonces[:5]
        
        return render_template('admin.html',
                              stats=stats,
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              activites=activites,
                              realisations=realisations,
                              annonces=annonces,
                              offres=offres,
                              recent_activities=recent_activities,
                              recent_annonces=recent_annonces,
                              session=session)
                              
    except Exception as e:
        flash(f'Erreur: {str(e)}', 'danger')
        return render_template('admin.html', 
                              error=str(e),
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              stats={})

# --- ROUTES API POUR LE FORMULAIRE UNIQUE ---

@app.route('/api/<type>/nouveau', methods=['POST'])
@login_required
def api_nouveau(type):
    """API pour créer un nouvel élément via le formulaire unique"""
    try:
        data = request.json
        
        if type == 'activite':
            item = Activite(
                titre=data.get('titre'),
                description=data.get('description'),
                contenu=data.get('contenu'),
                image_url=data.get('image_url'),
                auteur=session.get('username', 'Admin'),
                est_publie=data.get('est_publie', True),
                sync_status='pending'
            )
            db.session.add(item)
            db.session.commit()
            
            if item.est_publie:
                success, message = sync_activite_to_site(item)
                
        elif type == 'realisation':
            date_realisation = None
            if data.get('date_realisation'):
                date_realisation = datetime.strptime(data.get('date_realisation'), '%Y-%m-%d').date()
                
            item = Realisation(
                titre=data.get('titre'),
                description=data.get('description'),
                image_url=data.get('image_url'),
                categorie=data.get('categorie'),
                date_realisation=date_realisation,
                sync_status='pending'
            )
            db.session.add(item)
            db.session.commit()
            success, message = sync_realisation_to_site(item)
            
        elif type == 'annonce':
            date_debut = None
            date_fin = None
            if data.get('date_debut'):
                date_debut = datetime.fromisoformat(data.get('date_debut').replace('Z', '+00:00'))
            if data.get('date_fin'):
                date_fin = datetime.fromisoformat(data.get('date_fin').replace('Z', '+00:00'))
                
            item = Annonce(
                titre=data.get('titre'),
                contenu=data.get('contenu'),
                type_annonce=data.get('type_annonce', 'info'),
                date_debut=date_debut,
                date_fin=date_fin,
                est_active=data.get('est_active', True),
                sync_status='pending'
            )
            db.session.add(item)
            db.session.commit()
            
            if item.est_active:
                success, message = sync_annonce_to_site(item)
            else:
                success, message = True, "Créé (non actif)"
                
        elif type == 'offre':
            date_limite = None
            if data.get('date_limite'):
                date_limite = datetime.strptime(data.get('date_limite'), '%Y-%m-%d').date()
                
            item = Offre(
                titre=data.get('titre'),
                description=data.get('description'),
                type_offre=data.get('type_offre', 'autre'),
                lieu=data.get('lieu'),
                date_limite=date_limite,
                est_active=data.get('est_active', True),
                sync_status='pending'
            )
            db.session.add(item)
            db.session.commit()
            
            if item.est_active:
                success, message = sync_offre_to_site(item)
            else:
                success, message = True, "Créé (non actif)"
        else:
            return jsonify({'success': False, 'message': 'Type inconnu'}), 400
            
        return jsonify({
            'success': True,
            'id': item.id,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/<type>/<int:id>/modifier', methods=['POST'])
@login_required
def api_modifier(type, id):
    """API pour modifier un élément"""
    try:
        data = request.json
        
        if type == 'activite':
            item = Activite.query.get_or_404(id)
            ancien_publie = item.est_publie
            item.titre = data.get('titre')
            item.description = data.get('description')
            item.contenu = data.get('contenu')
            item.image_url = data.get('image_url')
            item.est_publie = data.get('est_publie', True)
            item.sync_status = 'pending'
            db.session.commit()
            
            if item.est_publie:
                success, message = sync_activite_to_site(item)
            elif ancien_publie and not item.est_publie:
                delete_from_site('activite', item.id)
                success, message = True, "Dépublié"
            else:
                success, message = True, "Modifié"
                
        elif type == 'realisation':
            item = Realisation.query.get_or_404(id)
            item.titre = data.get('titre')
            item.description = data.get('description')
            item.image_url = data.get('image_url')
            item.categorie = data.get('categorie')
            item.sync_status = 'pending'
            
            if data.get('date_realisation'):
                item.date_realisation = datetime.strptime(data.get('date_realisation'), '%Y-%m-%d').date()
            else:
                item.date_realisation = None
                
            db.session.commit()
            success, message = sync_realisation_to_site(item)
            
        elif type == 'annonce':
            item = Annonce.query.get_or_404(id)
            ancien_actif = item.est_active
            item.titre = data.get('titre')
            item.contenu = data.get('contenu')
            item.type_annonce = data.get('type_annonce', 'info')
            item.est_active = data.get('est_active', True)
            item.sync_status = 'pending'
            
            if data.get('date_debut'):
                item.date_debut = datetime.fromisoformat(data.get('date_debut').replace('Z', '+00:00'))
            else:
                item.date_debut = None
                
            if data.get('date_fin'):
                item.date_fin = datetime.fromisoformat(data.get('date_fin').replace('Z', '+00:00'))
            else:
                item.date_fin = None
                
            db.session.commit()
            
            if item.est_active:
                success, message = sync_annonce_to_site(item)
            elif ancien_actif and not item.est_active:
                delete_from_site('annonce', item.id)
                success, message = True, "Désactivé"
            else:
                success, message = True, "Modifié"
                
        elif type == 'offre':
            item = Offre.query.get_or_404(id)
            ancien_actif = item.est_active
            item.titre = data.get('titre')
            item.description = data.get('description')
            item.type_offre = data.get('type_offre', 'autre')
            item.lieu = data.get('lieu')
            item.est_active = data.get('est_active', True)
            item.sync_status = 'pending'
            
            if data.get('date_limite'):
                item.date_limite = datetime.strptime(data.get('date_limite'), '%Y-%m-%d').date()
            else:
                item.date_limite = None
                
            db.session.commit()
            
            if item.est_active:
                success, message = sync_offre_to_site(item)
            elif ancien_actif and not item.est_active:
                delete_from_site('offre', item.id)
                success, message = True, "Désactivé"
            else:
                success, message = True, "Modifié"
        else:
            return jsonify({'success': False, 'message': 'Type inconnu'}), 400
            
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/<type>/<int:id>/supprimer', methods=['POST'])
@login_required
def api_supprimer(type, id):
    """API pour supprimer un élément"""
    try:
        if type == 'activite':
            item = Activite.query.get_or_404(id)
            if item.est_publie:
                delete_from_site('activite', id)
            db.session.delete(item)
            
        elif type == 'realisation':
            item = Realisation.query.get_or_404(id)
            delete_from_site('realisation', id)
            db.session.delete(item)
            
        elif type == 'annonce':
            item = Annonce.query.get_or_404(id)
            if item.est_active:
                delete_from_site('annonce', id)
            db.session.delete(item)
            
        elif type == 'offre':
            item = Offre.query.get_or_404(id)
            if item.est_active:
                delete_from_site('offre', id)
            db.session.delete(item)
        else:
            return jsonify({'success': False, 'message': 'Type inconnu'}), 400
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Supprimé'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/<type>/<int:id>/sync', methods=['POST'])
@login_required
def api_sync(type, id):
    """API pour synchroniser un élément"""
    try:
        if type == 'activite':
            item = Activite.query.get_or_404(id)
            success, message = sync_activite_to_site(item)
        elif type == 'realisation':
            item = Realisation.query.get_or_404(id)
            success, message = sync_realisation_to_site(item)
        elif type == 'annonce':
            item = Annonce.query.get_or_404(id)
            success, message = sync_annonce_to_site(item)
        elif type == 'offre':
            item = Offre.query.get_or_404(id)
            success, message = sync_offre_to_site(item)
        else:
            return jsonify({'success': False, 'message': 'Type inconnu'}), 400
            
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_image():
    """Upload d'image vers le site principal"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nom de fichier vide'}), 400
            
        # Upload vers le site principal
        files = {'file': (file.filename, file.stream, file.mimetype)}
        headers = {'X-API-Key': API_KEY}
        
        response = requests.post(
            f"{SITE_URL}/api/upload",
            files=files,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'success': False, 'message': f'Erreur {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- ROUTES DE SYNCHRONISATION MANUELLE ---
@app.route('/sync/all')
@login_required
def sync_all():
    """Synchroniser tous les éléments"""
    try:
        activites = Activite.query.filter_by(est_publie=True).all()
        realisations = Realisation.query.all()
        annonces = Annonce.query.filter_by(est_active=True).all()
        offres = Offre.query.filter_by(est_active=True).all()
        
        total = len(activites) + len(realisations) + len(annonces) + len(offres)
        success_count = 0
        
        for item in activites:
            if sync_activite_to_site(item)[0]: success_count += 1
        for item in realisations:
            if sync_realisation_to_site(item)[0]: success_count += 1
        for item in annonces:
            if sync_annonce_to_site(item)[0]: success_count += 1
        for item in offres:
            if sync_offre_to_site(item)[0]: success_count += 1
            
        flash(f'✅ {success_count}/{total} éléments synchronisés', 'success')
        
    except Exception as e:
        flash(f'❌ Erreur: {str(e)}', 'danger')
        
    return redirect(url_for('admin_panel'))

# --- ROUTES API POUR LE SITE PRINCIPAL ---
@app.route('/api/health')
def api_health():
    site_connected, site_message = check_site_connection()
    return jsonify({
        'status': 'ok',
        'service': 'labmath-admin',
        'timestamp': datetime.utcnow().isoformat(),
        'site_connected': site_connected,
        'site_message': site_message
    })

# --- GESTION DES ERREURS ---
@app.errorhandler(404)
def page_not_found(e):
    if 'user_id' in session:
        return render_template('404.html'), 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_server_error(e):
    db.session.rollback()
    if 'user_id' in session:
        return render_template('500.html', error=str(e)), 500
    return redirect(url_for('login'))

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Créer les tables
    db.create_all()
    
    # Supprimer les colonnes problématiques
    try:
        db.engine.execute('ALTER TABLE realisations DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE activites DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE annonces DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE offres DROP COLUMN IF EXISTS date_modification')
        print("✅ Colonnes problématiques supprimées")
    except:
        pass
    
    print("✅ Base de données initialisée")
    print(f"🌐 Site principal: {SITE_URL}")
    print(f"🔑 API Key: {'Configurée' if API_KEY else 'Non configurée'}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)