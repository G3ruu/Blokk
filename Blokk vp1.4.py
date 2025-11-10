import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

import google.generativeai as genai
from PIL import Image
import json
import os
import time
import threading
import psutil
import re
import datetime # --- (pour les stats) ---
from pypdf import PdfReader # --- (pour les PDF) ---
import requests # --- (pour les URL) ---
from bs4 import BeautifulSoup # --- (pour les URL) ---
import sys 

# -----------------------------------------------------------------
# ---  Fonction pour trouver les fichiers (pour .exe) ---
# -----------------------------------------------------------------
def resource_path(relative_path):
    """
    Obtient le chemin absolu vers une ressource.
    Fonctionne pour le mode "développement" et pour le .exe PyInstaller.
    """
    try:
        # PyInstaller crée un dossier temporaire et y stocke le chemin
        base_path = sys._MEIPASS
    except Exception:
        # Pas dans un .exe, on est en mode "développement"
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# -----------------------------------------------------------------
# --- Classe de Pop-up personnalisée avec Scrollbar ---
# -----------------------------------------------------------------
class ScrollableMessageDialog(ttk.Toplevel):
    def __init__(self, parent, title, message, bootstyle="default"):
        super().__init__(parent) 
        self.title(title)        
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame, orient=VERTICAL)
        text_widget = tk.Text(frame, wrap=WORD, font=("Helvetica", 10), 
                              yscrollcommand=scrollbar.set, relief="flat")
        scrollbar.config(command=text_widget.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        text_widget.pack(side=LEFT, fill=BOTH, expand=True)
        text_widget.insert(END, message)
        text_widget.config(state=DISABLED)
        ok_button = ttk.Button(self, text="OK", command=self.destroy, bootstyle=bootstyle)
        ok_button.pack(pady=10)
        self.wait_window()

# --- CONFIGURATION DE L'API (supprimée d'ici) ---
# La configuration se fait maintenant dans __init__

# -----------------------------------------------------------------
# --- MODULE 2 - LOGIQUE DE BLOCAGE (Inchangé) ---
# -----------------------------------------------------------------
hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
redirect_ip = "127.0.0.1"

def bloquer_sites(sites_a_bloquer):
    print("Début du blocage des sites...")
    try:
        with open(hosts_path, 'r+') as fichier:
            contenu = fichier.read()
            for site in sites_a_bloquer:
                if site and site not in contenu:
                    fichier.write(f"\n{redirect_ip} {site}")
        print("Sites bloqués.")
        return True
    except PermissionError:
        messagebox.showerror("Erreur de Permission", 
                             "Impossible de bloquer les sites.\n"
                             "Assure-toi de lancer ce script en tant qu'Administrateur.")
        return False
    except Exception as e:
        messagebox.showerror("Erreur Fichier Hosts", f"Une erreur inconnue est survenue : {e}")
        return False

def debloquer_sites(sites_a_bloquer):
    print("Début du déblocage des sites...")
    try:
        with open(hosts_path, 'r+') as fichier:
            lignes = fichier.readlines()
            fichier.seek(0)
            for ligne in lignes:
                if not any(site in ligne for site in sites_a_bloquer if site):
                    fichier.write(ligne)
            fichier.truncate()
        print("Sites débloqués.")
    except Exception as e:
        print(f"Erreur déblocage sites: {e}")

def tuer_processus_interdits(apps_a_bloquer):
    print("Scan des processus en cours...")
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] in apps_a_bloquer:
            try:
                proc.kill()
                print(f"PROCESSUS TUÉ : {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

def thread_killer_loop(stop_event, apps_a_bloquer):
    while not stop_event.is_set():
        tuer_processus_interdits(apps_a_bloquer)
        time.sleep(5) 
    print("Thread 'killer' arrêté.")


# --- CLASSE PRINCIPALE DE L'APPLICATION (v2.2 Partageable - CORRIGÉE) ---
class AppDevoirsIA(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly") 
        
        self.title("Blokk v1.4")
        self.geometry("800x700")

        icon_path = resource_path("icon.ico")
        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Erreur lors du chargement de l'icône de la fenêtre : {e}")
        
        self.mode_focus_actif = False
        self.devoirs_termines = False
        self.evaluation_reussie = False
        
        self.thread_killer = None
        self.thread_stop_event = None

        self.sites_a_bloquer = []
        self.apps_a_bloquer = []
        self.devoirs_data = {} 

        # Initialisation des variables API
        self.api_key = ""
        self.model = None
        
        self.sites_a_bloquer_defaut = [
            "www.youtube.com", "youtube.com", "www.tiktok.com", "tiktok.com",
            "www.instagram.com", "instagram.com", "www.facebook.com", "facebook.com",
            "www.twitch.tv", "twitch.tv", "www.reddit.com", "reddit.com"
        ]
        self.apps_a_bloquer_defaut = [
            "Steam.exe", "steamwebhelper.exe", "SteamService.exe",
            "Discord.exe", "Update.exe"
        ]
        
        # --- Construction des onglets (doit être fait AVANT de charger les params) ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # --- ONGLET 1 : DEVOIRS ---
        self.tab_devoirs = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_devoirs, text="Devoirs à Corriger")
        frame_gauche = ttk.Frame(self.tab_devoirs, width=200, padding=10)
        frame_gauche.pack(side=LEFT, fill=Y)
        label_liste = ttk.Label(frame_gauche, text="Mes Devoirs", font=("Helvetica", 12, "bold"))
        label_liste.pack(pady=5)
        self.listbox_devoirs = tk.Listbox(frame_gauche, height=25)
        self.listbox_devoirs.pack(fill=BOTH, expand=True)
        self.listbox_devoirs.bind('<<ListboxSelect>>', self.charger_devoir_selectionne)
        frame_droite = ttk.Frame(self.tab_devoirs, padding=10)
        frame_droite.pack(side=RIGHT, fill=BOTH, expand=True)
        label_titre = ttk.Label(frame_droite, text="Titre du devoir, du CCTL ou du CER:")
        label_titre.pack(anchor="w")
        self.entry_titre_devoir = ttk.Entry(frame_droite, font=("Helvetica", 12))
        self.entry_titre_devoir.pack(fill="x", pady=5)
        label_sujet = ttk.Label(frame_droite, text="Sujet / Énoncé / Question :")
        label_sujet.pack(anchor="w")
        self.text_sujet_devoir = tk.Text(frame_droite, height=5, font=("Helvetica", 10))
        self.text_sujet_devoir.pack(fill="x", pady=5)
        label_reponse = ttk.Label(frame_droite, text="Ta Réponse (Vérifié par GEMINI PRO) :")
        label_reponse.pack(anchor="w")
        self.text_reponse_devoir = tk.Text(frame_droite, height=15, font=("Helvetica", 10))
        self.text_reponse_devoir.pack(fill="x", pady=5)
        self.btn_charger_reponse = ttk.Button(frame_droite, text="Charger la réponse depuis une image",
                                             command=self.charger_reponse_depuis_image,
                                             bootstyle="info-outline")
        self.btn_charger_reponse.pack(fill=X, pady=5) 
        btn_sauvegarder = ttk.Button(frame_droite, text="Sauvegarder ce devoir", 
                                     command=self.sauvegarder_devoir, 
                                     bootstyle="primary-outline")
        btn_sauvegarder.pack(pady=10)

        # --- ONGLET 2 : ÉVALUATION ---
        self.tab_eval = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_eval, text="Préparation d'Évaluation")
        frame_eval_top = ttk.Frame(self.tab_eval)
        frame_eval_top.pack(fill=BOTH, expand=True)
        frame_cours = ttk.Labelframe(frame_eval_top, text="1. Colle ton cours ici", padding=10)
        frame_cours.pack(side=LEFT, fill=BOTH, expand=True, padx=5)
        self.text_cours = tk.Text(frame_cours, height=15, font=("Helvetica", 10))
        self.text_cours.pack(fill=BOTH, expand=True)
        frame_import_buttons = ttk.Frame(frame_cours)
        frame_import_buttons.pack(fill=X, pady=5)
        self.btn_charger_image = ttk.Button(frame_import_buttons, text="Depuis Image", 
                                            command=self.charger_cours_depuis_image,
                                            bootstyle="info-outline")
        self.btn_charger_image.pack(side=LEFT, expand=True, padx=2)
        self.btn_charger_pdf = ttk.Button(frame_import_buttons, text="Depuis PDF", 
                                          command=self.importer_depuis_pdf,
                                          bootstyle="info-outline")
        self.btn_charger_pdf.pack(side=LEFT, expand=True, padx=2)
        self.btn_charger_url = ttk.Button(frame_import_buttons, text="Depuis URL", 
                                          command=self.importer_depuis_url,
                                          bootstyle="info-outline")
        self.btn_charger_url.pack(side=LEFT, expand=True, padx=2)
        self.btn_generer_eval = ttk.Button(frame_cours, text="Générer l'exercice", 
                                           command=self.generer_exercice_ia,
                                           bootstyle="primary", state=DISABLED)
        self.btn_generer_eval.pack(fill=X, pady=10)
        frame_exercice = ttk.Labelframe(frame_eval_top, text="2. Exercice généré par l'IA", padding=10)
        frame_exercice.pack(side=RIGHT, fill=BOTH, expand=True, padx=5)
        self.text_exercice_genere = tk.Text(frame_exercice, height=15, font=("Helvetica", 10))
        self.text_exercice_genere.pack(fill=BOTH, expand=True)
        self.text_exercice_genere.config(state=DISABLED) 
        frame_eval_bottom = ttk.Labelframe(self.tab_eval, text="3. Écris tes réponses ici", padding=10)
        frame_eval_bottom.pack(fill=BOTH, expand=True, pady=10)
        self.text_reponses_eval = tk.Text(frame_eval_bottom, height=10, font=("Helvetica", 10))
        self.text_reponses_eval.pack(fill=BOTH, expand=True)

        # --- ONGLET 3 : PARAMÈTRES ---
        self.tab_parametres = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_parametres, text="Paramètres")
        
        frame_api = ttk.Labelframe(self.tab_parametres, text="Clé API Google AI (Gemini)", padding=10)
        frame_api.pack(fill=X, padx=5, pady=5)
        self.entry_api_key = ttk.Entry(frame_api, font=("Helvetica", 10), show="*")
        self.entry_api_key.pack(fill=X, expand=True)
        
        frame_sites = ttk.Labelframe(self.tab_parametres, text="Sites à Bloquer (un par ligne)", padding=10)
        frame_sites.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.text_sites_bloques = tk.Text(frame_sites, height=10, font=("Helvetica", 10))
        self.text_sites_bloques.pack(fill=BOTH, expand=True)
        
        frame_apps = ttk.Labelframe(self.tab_parametres, text="Applications à Bloquer (ex: Steam.exe)", padding=10)
        frame_apps.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.text_apps_bloquees = tk.Text(frame_apps, height=10, font=("Helvetica", 10))
        self.text_apps_bloquees.pack(fill=BOTH, expand=True)
        
        btn_sauvegarder_params = ttk.Button(self.tab_parametres, text="Sauvegarder les Paramètres",
                                             command=self.sauvegarder_parametres,
                                             bootstyle="success")
        btn_sauvegarder_params.pack(pady=10)

        # --- ONGLET 4 : STATISTIQUES ---
        self.tab_stats = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_stats, text="Statistiques")
        stats_frame = ttk.Labelframe(self.tab_stats, text="Historique des Évaluations", padding=10)
        stats_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        columns = ("date", "titre", "score")
        self.stats_tree = ttk.Treeview(stats_frame, columns=columns, show="headings", bootstyle="dark")
        self.stats_tree.heading("date", text="Date et Heure")
        self.stats_tree.column("date", width=200)
        self.stats_tree.heading("titre", text="Sujet de l'évaluation")
        self.stats_tree.column("titre", width=300)
        self.stats_tree.heading("score", text="Score")
        self.stats_tree.column("score", width=100, anchor=CENTER)
        self.stats_tree.pack(fill=BOTH, expand=True)
        btn_reset_stats = ttk.Button(self.tab_stats, text="Réinitialiser l'historique",
                                      command=self.reset_historique,
                                      bootstyle="danger-outline")
        btn_reset_stats.pack(pady=10)

        # --- ZONE D'ACTION PRINCIPALE ---
        frame_action = ttk.Frame(self)
        frame_action.pack(side=BOTTOM, fill="x", pady=10)
        self.btn_verifier_devoir = ttk.Button(frame_action, text="VÉRIFIER DEVOIR", 
                                              bootstyle="success",
                                              command=self.lancer_verification_devoir)
        self.btn_verifier_devoir.pack(side=LEFT, expand=True, padx=10)
        self.btn_verifier_eval = ttk.Button(frame_action, text="SOUMETTRE ÉVAL", 
                                            bootstyle="success-outline",
                                            command=self.lancer_verification_eval,
                                            state=DISABLED) 
        self.btn_verifier_eval.pack(side=LEFT, expand=True, padx=10)
        self.btn_bloquer = ttk.Button(self, text="Activer le mode Focus", 
                                      bootstyle="danger-outline",
                                      command=self.commencer_mode_focus)
        self.btn_bloquer.pack(side=BOTTOM, fill="x", padx=20, pady=5)
        
        # --- CHARGEMENT DES DONNÉES (CORRIGÉ) ---
        if not self.charger_parametres(): # Charge config, demande la clé si besoin
            self.destroy() # Ferme si l'utilisateur annule la saisie de la clé
            return
            
        if not self.configurer_ia(): # Allume l'IA
            self.destroy() # Ferme si la clé est mauvaise
            return
            
        # Charge le reste
        self.charger_session_json() 
        self.charger_historique()
        
    # --- FIN DE __INIT__ ---


    # --- FONCTIONS DE PARAMÈTRES (CORRIGÉES) ---
    
    def configurer_ia(self):
        """Configure l'API Gemini avec la clé chargée."""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('models/gemini-2.5-pro') 
            print("Modèle IA chargé avec succès.")
            return True
        except Exception as e:
            ScrollableMessageDialog(self, "Erreur API", 
                                    f"La clé API fournie est incorrecte ou la connexion a échoué.\n\nErreur: {e}\n\nVeuillez relancer l'application et vérifier votre clé.", 
                                    bootstyle="danger")
            return False

    def sauvegarder_parametres(self):
        print("Sauvegarde des paramètres...")
        
        self.api_key = self.entry_api_key.get().strip()
        self.sites_a_bloquer = [ligne.strip() for ligne in self.text_sites_bloques.get("1.0", tk.END).strip().splitlines() if ligne.strip()]
        self.apps_a_bloquer = [ligne.strip() for ligne in self.text_apps_bloquees.get("1.0", tk.END).strip().splitlines() if ligne.strip()]
        
        config = { 
            "api_key": self.api_key,
            "sites": self.sites_a_bloquer, 
            "apps": self.apps_a_bloquer 
        }
        
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            # Re-configurer l'IA avec la nouvelle clé
            if not self.configurer_ia():
                messagebox.showerror("Clé API invalide", "La nouvelle clé API n'a pas pu être validée. Veuillez la corriger.")
            else:
                messagebox.showinfo("Sauvegardé", "Paramètres et clé API sauvegardés et validés.")
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder config.json: {e}")

    def charger_parametres(self):
        """Charge config.json et demande la clé si elle est absente."""
        print("Chargement des paramètres...")
        config = {}
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.api_key = config.get("api_key", "")
            self.sites_a_bloquer = config.get("sites", self.sites_a_bloquer_defaut)
            self.apps_a_bloquer = config.get("apps", self.apps_a_bloquer_defaut)
            print("Paramètres chargés depuis config.json.")

        except FileNotFoundError:
            print("config.json non trouvé. Utilisation des paramètres par défaut.")
            self.api_key = ""
            self.sites_a_bloquer = self.sites_a_bloquer_defaut[:]
            self.apps_a_bloquer = self.apps_a_bloquer_defaut[:]
        except Exception as e:
            messagebox.showerror("Erreur Config", f"Impossible de lire config.json: {e}")
            
        # Logique de première utilisation
        if not self.api_key:
            self.withdraw() # Cache la fenêtre principale
            self.api_key = simpledialog.askstring("Clé API requise", 
                                                  "Bienvenue sur Blokk !\n\n"
                                                  "Veuillez coller votre clé API Google AI (Gemini) pour continuer.\n"
                                                  "Vous pouvez l'obtenir gratuitement sur 'aistudio.google.com'.", 
                                                  parent=self)
            
            if not self.api_key: # L'utilisateur a cliqué sur "Annuler"
                messagebox.showerror("Erreur", "Une clé API est obligatoire pour utiliser l'application.")
                return False # Échec
            else:
                # Sauvegarder immédiatement la clé pour la prochaine fois
                config = {
                    "api_key": self.api_key,
                    "sites": self.sites_a_bloquer,
                    "apps": self.apps_a_bloquer
                }
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=4)
                except Exception as e:
                     messagebox.showerror("Erreur", f"Impossible de sauvegarder config.json: {e}")
                self.deiconify() # Fait réapparaître la fenêtre
        
        # Remplir les boîtes de texte de l'onglet Paramètres
        self.entry_api_key.delete(0, tk.END)
        self.entry_api_key.insert(0, self.api_key)
        self.text_sites_bloques.delete("1.0", tk.END)
        self.text_sites_bloques.insert("1.0", "\n".join(self.sites_a_bloquer))
        self.text_apps_bloquees.delete("1.0", tk.END)
        self.text_apps_bloquees.insert("1.0", "\n".join(self.apps_a_bloquer))
        
        return True # Succès

    # --- FONCTIONS DE SESSION (Inchangées) ---
    def sauvegarder_session_json(self):
        # ... (code inchangé, identique à ton fichier)
        print("Sauvegarde de la session...")
        devoirs_a_sauver = {}
        for titre, data in self.devoirs_data.items():
            if not data["corrige"]:
                devoirs_a_sauver[titre] = data
        eval_a_sauver = {
            "cours": self.text_cours.get("1.0", tk.END).strip(),
            "exercice": self.text_exercice_genere.get("1.0", tk.END).strip(),
            "reponses": self.text_reponses_eval.get("1.0", tk.END).strip()
        }
        data_a_sauver = { "devoirs": devoirs_a_sauver, "evaluation": eval_a_sauver }
        try:
            with open("session_data.json", "w", encoding="utf-8") as f:
                json.dump(data_a_sauver, f, ensure_ascii=False, indent=4)
            print("Session sauvegardée dans session_data.json")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la session : {e}")

    def charger_session_json(self):
        # ... (code inchangé, identique à ton fichier)
        print("Chargement de la session...")
        try:
            with open("session_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.devoirs_data = data.get("devoirs", {})
            if self.devoirs_data:
                print(f"Devoirs en cours chargés : {len(self.devoirs_data)} trouvé(s)")
                for titre in self.devoirs_data:
                    self.listbox_devoirs.insert(tk.END, titre)
            eval_data = data.get("evaluation", {})
            cours, exercice, reponses = eval_data.get("cours"), eval_data.get("exercice"), eval_data.get("reponses")
            if cours: self.text_cours.insert("1.0", cours)
            if exercice:
                self.text_exercice_genere.config(state=NORMAL)
                self.text_exercice_genere.insert("1.0", exercice)
                self.text_exercice_genere.config(state=DISABLED)
                self.btn_verifier_eval.config(state=NORMAL, bootstyle="success")
                self.btn_generer_eval.config(text="Exercice généré !", state=DISABLED)
            if reponses: self.text_reponses_eval.insert("1.0", reponses)
            print("Session précédente chargée.")
        except FileNotFoundError:
            print("Aucun fichier de session (session_data.json) trouvé. On commence à zéro.")
        except Exception as e:
            print(f"Erreur lors du chargement de la session : {e}")
            
    # --- FONCTIONS OCR (Modifiées pour utiliser self.model) ---
    def charger_reponse_depuis_image(self):
        file_path = filedialog.askopenfilename(title="Sélectionner une image de ta réponse", filetypes=[("Fichiers Image", "*.png *.jpg *.jpeg")])
        if not file_path: return
        messagebox.showinfo("Chargement d'image", "Chargement de l'image et extraction du texte par l'IA en cours...\nMerci de patienter.")
        threading.Thread(target=self._process_reponse_image_in_background, args=(file_path,)).start()
    def _process_reponse_image_in_background(self, file_path):
        try:
            img = Image.open(file_path)
            prompt_content = ["Extrais tout le texte manuscrit ou imprimé de cette image et retranscris-le.", img]
            response = self.model.generate_content(prompt_content) # MODIFIÉ
            extracted_text = response.text
            self.after(0, lambda: self._update_reponse_text(extracted_text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Lecture Image", f"Impossible de lire l'image ou d'extraire le texte.\nErreur: {e}"))
    def _update_reponse_text(self, text):
        self.text_reponse_devoir.delete("1.0", tk.END)
        self.text_reponse_devoir.insert("1.0", text)
        messagebox.showinfo("Extraction Réussie", "Le texte de ton image a été extrait.")
        
    def charger_cours_depuis_image(self):
        file_path = filedialog.askopenfilename(title="Sélectionner une image de cours", filetypes=[("Fichiers Image", "*.png *.jpg *.jpeg")])
        if not file_path: return
        messagebox.showinfo("Chargement d'image", "Chargement de l'image et extraction du texte par l'IA en cours...\nMerci de patienter.")
        threading.Thread(target=self._process_image_in_background, args=(file_path,)).start()
    def _process_image_in_background(self, file_path):
        try:
            img = Image.open(file_path)
            prompt_content = ["Extrais tout le texte de cette image et retranscris-le.", img]
            response = self.model.generate_content(prompt_content) # MODIFIÉ
            extracted_text = response.text
            self.after(0, lambda: self._update_cours_text(extracted_text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Lecture Image", f"Impossible de lire l'image ou d'extraire le texte.\nErreur: {e}"))
    def _update_cours_text(self, text):
        self.text_cours.delete("1.0", tk.END)
        self.text_cours.insert("1.0", text)
        messagebox.showinfo("Extraction Réussie", "Le texte de l'image a été extrait.")

    # --- FONCTIONS D'IMPORT PDF/URL (Inchangées) ---
    def importer_depuis_pdf(self):
        file_path = filedialog.askopenfilename(title="Sélectionner un fichier PDF", filetypes=[("Fichiers PDF", "*.pdf")])
        if not file_path: return
        messagebox.showinfo("Chargement PDF", "Lecture du PDF en cours... Merci de patienter.")
        threading.Thread(target=self._process_pdf_in_background, args=(file_path,)).start()
    def _process_pdf_in_background(self, file_path):
        try:
            text = ""
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
            self.after(0, lambda: self._update_cours_text(text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur PDF", f"Impossible de lire le fichier PDF.\nErreur: {e}"))
    def importer_depuis_url(self):
        url = simpledialog.askstring("Importer depuis URL", "Entre l'URL de la page web :", parent=self)
        if not url: return
        messagebox.showinfo("Chargement URL", "Récupération de la page web... Merci de patienter.")
        threading.Thread(target=self._process_url_in_background, args=(url,)).start()
    def _process_url_in_background(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
            text = "\n".join(elem.get_text() for elem in text_elements)
            self.after(0, lambda: self._update_cours_text(text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur URL", f"Impossible de récupérer la page.\nErreur: {e}"))
    
    # --- FONCTIONS DE STATISTIQUES (Inchangées) ---
    def charger_historique(self):
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        try:
            with open("historique.json", "r", encoding="utf-8") as f:
                historique = json.load(f)
            for entree in historique:
                titre = entree.get("titre", "N/A")
                score = entree.get("score", "??%")
                self.stats_tree.insert("", END, values=(entree["date"], titre, score))
            print("Historique chargé.")
        except FileNotFoundError:
            print("Aucun fichier d'historique trouvé.")
        except Exception as e:
            print(f"Erreur chargement historique : {e}")

    def sauvegarder_historique(self, score, titre):
        print("Sauvegarde du score...")
        nouvelle_entree = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": f"{score}%",
            "titre": titre
        }
        try:
            with open("historique.json", "r", encoding="utf-8") as f:
                historique = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            historique = []
        historique.append(nouvelle_entree)
        try:
            with open("historique.json", "w", encoding="utf-8") as f:
                json.dump(historique, f, ensure_ascii=False, indent=4)
            print("Score sauvegardé dans l'historique.")
            self.stats_tree.insert("", END, values=(nouvelle_entree["date"], nouvelle_entree["titre"], nouvelle_entree["score"]))
        except Exception as e:
            print(f"Erreur sauvegarde historique : {e}")
            
    def reset_historique(self):
        print("Réinitialisation de l'historique...")
        if not messagebox.askyesno("Confirmer", "Es-tu sûr de vouloir supprimer tout l'historique des statistiques ?\nCette action est irréversible."):
            return
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        try:
            if os.path.exists("historique.json"):
                os.remove("historique.json")
            messagebox.showinfo("Réinitialisé", "L'historique des statistiques a été supprimé.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de supprimer historique.json : {e}")


    # --- FONCTIONS DE L'ONGLET 1 (Modifiées pour self.model et bugs visuels) ---
    def sauvegarder_devoir(self):
        titre = self.entry_titre_devoir.get()
        sujet = self.text_sujet_devoir.get("1.0", tk.END).strip()
        reponse = self.text_reponse_devoir.get("1.0", tk.END).strip()
        if not titre or not sujet or not reponse:
            messagebox.showwarning("Champs manquants", "Tu dois remplir le Titre, le Sujet ET Ta Réponse.")
            return
        self.devoirs_data[titre] = {"sujet": sujet, "reponse": reponse, "corrige": False}
        if titre not in self.listbox_devoirs.get(0, tk.END):
            self.listbox_devoirs.insert(tk.END, titre)
        messagebox.showinfo("Sauvegardé", f"Le devoir '{titre}' a été sauvegardé.")
        self.entry_titre_devoir.delete(0, tk.END)
        self.text_sujet_devoir.delete("1.0", tk.END)
        self.text_reponse_devoir.delete("1.0", tk.END)

    def charger_devoir_selectionne(self, event):
        try:
            titre_selectionne = self.listbox_devoirs.get(self.listbox_devoirs.curselection())
            titre_propre = titre_selectionne.replace("✅ ", "").replace(" (CORRECT)", "")
            data = self.devoirs_data[titre_propre]
            self.entry_titre_devoir.delete(0, tk.END)
            self.text_sujet_devoir.delete("1.O", tk.END)
            self.text_reponse_devoir.delete("1.0", tk.END)
            self.entry_titre_devoir.insert(0, titre_propre)
            self.text_sujet_devoir.insert("1.0", data["sujet"])
            self.text_reponse_devoir.insert("1.0", data["reponse"])
        except tk.TclError:
            pass

    def lancer_verification_devoir(self):
        if not self.mode_focus_actif:
            messagebox.showerror("Mode Focus Inactif", 
                                 "Tu dois d'abord cliquer sur 'Activer le mode Focus'.")
            return
        try:
            titre_selectionne = self.listbox_devoirs.get(self.listbox_devoirs.curselection())
            titre_propre = titre_selectionne.replace("✅ ", "").replace(" (CORRECT)", "")
        except tk.TclError:
            messagebox.showerror("Erreur", "Tu dois sélectionner un devoir dans la liste de gauche.")
            return
        data = self.devoirs_data[titre_propre]
        sujet, reponse_eleve = data["sujet"], data["reponse"]
        if data["corrige"]:
            messagebox.showinfo("Déjà corrigé", "Ce devoir est déjà marqué 'CORRECT'.")
            return
            
        self.btn_verifier_devoir.config(text="Vérification en cours...") # 1. Texte
        self.update_idletasks() # 2. Redessin
        self.btn_verifier_devoir.config(state=DISABLED) # 3. Désactivation
        
        prompt = f"""
        Tu es "Professeur Gemini", un correcteur de devoirs strict mais juste.
        RÈGLES DE RÉPONSE OBLIGATOIRES :
        1.  Ta réponse doit OBLIGATOIREMENT commencer par un seul mot : "CORRECT" ou "INCORRECT".
        2.  Après ce premier mot, saute une ligne et donne une explication courte et claire (2-3 phrases maximum).
        SUJET : "{sujet}"
        RÉPONSE DE L'ÉLÈVE : "{reponse_eleve}"
        Ta correction :
        """
        try:
            response = self.model.generate_content(prompt) # MODIFIÉ
            correction = response.text
            if correction.strip().startswith("CORRECT"):
                self.devoirs_data[titre_propre]["corrige"] = True
                idx = self.listbox_devoirs.get(0, tk.END).index(titre_selectionne)
                self.listbox_devoirs.delete(idx)
                self.listbox_devoirs.insert(idx, f"✅ {titre_propre} (CORRECT)")
                ScrollableMessageDialog(self, "Correction IA : CORRECT", correction, bootstyle="success")
                self.verifier_si_devoirs_finis()
            elif correction.strip().startswith("INCORRECT"):
                ScrollableMessageDialog(self, "Correction IA : INCORRECT", correction, bootstyle="danger")
            else:
                ScrollableMessageDialog(self, "Erreur de formatage IA", 
                                        f"L'IA a donné une réponse inattendue :\n\n{correction}", 
                                        bootstyle="warning")
        except Exception as e:
            messagebox.showerror("Erreur API", f"Une erreur est survenue lors de la connexion à l'IA.\n{e}")
        self.btn_verifier_devoir.config(text="VÉRIFIER DEVOIR", state=NORMAL)

    def verifier_si_devoirs_finis(self):
        if not self.devoirs_data:
            self.devoirs_termines = False
            return
        tous_finis = all(data["corrige"] for data in self.devoirs_data.values())
        if tous_finis:
            print("Statut Devoirs : TERMINÉ")
            self.devoirs_termines = True
            self.tenter_deblocage()
        else:
            self.devoirs_termines = False
            

    # --- FONCTIONS DE L'ONGLET 2 (Modifiées pour self.model et bugs) ---
    def generer_exercice_ia(self):
        if not self.mode_focus_actif:
            messagebox.showerror("Mode Focus Inactif", 
                                 "Tu dois d'abord activer le 'Mode Focus'.")
            return
        cours = self.text_cours.get("1.0", tk.END).strip()
        if not cours:
            messagebox.showwarning("Cours manquant", "Tu dois coller ton cours dans la case n°1.")
            return
        self.btn_generer_eval.config(text="Génération en cours... L'IA réfléchit...", state=DISABLED)
        self.update_idletasks()
        
        prompt = f"""
        Tu es un professeur exigeant.
        Voici le cours d'un élève :
        --- DÉBUT DU COURS ---
        {cours}
        --- FIN DU COURS ---
        
        Ta mission est de créer un exercice difficile pour le préparer à une évaluation.
        RÈGLES DE L'EXERCICE :
        1.  L'exercice doit contenir exactement 5 questions.
        2.  Mélange les types de questions (ex: QCM, question ouverte, analyse de cas, définition...).
        3.  Les questions doivent être difficiles et tester la compréhension profonde.
        4.  Ne fournis AUCUNE réponse.
        
        Formate ta réponse en commençant par : "EXERCICE DE PRÉPARATION :"
        """
        
        try:
            response = self.model.generate_content(prompt) # MODIFIÉ
            exercice_genere = response.text
            
            self.text_exercice_genere.config(state=NORMAL)
            self.text_exercice_genere.delete("1.0", tk.END)
            self.text_exercice_genere.insert("1.0", exercice_genere)
            self.text_exercice_genere.config(state=DISABLED)
            
            self.btn_verifier_eval.config(state=NORMAL, bootstyle="success")
            self.btn_generer_eval.config(text="Exercice généré !", state=DISABLED)
            
            messagebox.showinfo("Exercice Prêt !", "L'IA a généré ton exercice. Écris tes réponses en bas et clique sur 'Soumettre Éval'.")

        except Exception as e:
            messagebox.showerror("Erreur API", f"Une erreur est survenue lors de la génération de l'IA.\n{e}")
            self.btn_generer_eval.config(text="Générer l'exercice", state=NORMAL)

    def lancer_verification_eval(self):
        cours = self.text_cours.get("1.0", tk.END).strip()
        exercice = self.text_exercice_genere.get("1.0", tk.END).strip()
        reponses_eleve = self.text_reponses_eval.get("1.0", tk.END).strip()
        
        if not reponses_eleve:
            messagebox.showwarning("Réponses manquantes", "Tu dois écrire tes réponses dans la case n°3 avant de soumettre.")
            return
            
        self.btn_verifier_eval.config(text="Correction en cours...") # 1. Texte
        self.update_idletasks() # 2. Redessin
        self.btn_verifier_eval.config(state=DISABLED) # 3. Désactivation
        
        prompt = f"""
        Tu es "Professeur Gemini", un correcteur d'évaluation.
        Voici les éléments :
        1. LE COURS DE RÉFÉRENCE : {cours}
        2. L'EXERCICE QUI A ÉTÉ DONNÉ : {exercice}
        3. LES RÉPONSES DE L'ÉLÈVE : {reponses_eleve}
        
        MISSION DE CORRECTION :
        1.  Évalue les réponses de l'élève en te basant STRICTEMENT sur le cours et l'exercice.
        2.  Donne un score global sous la forme d'un pourcentage. Le score DOIT être sur sa propre ligne et formaté exactement comme ceci : "SCORE: [nombre]%"
        3.  Après le score, saute une ligne et fournis une correction détaillée pour chaque réponse fausse.
        4.  Si le score est >= 85%, commence ta correction par "FÉLICITATIONS !".
        5.  Si le score est < 75%, commence ta correction par "INCORRECT.".
        6.  Si le score est entre 75% et 84%, commence ta correction par "CORRECT, MAIS...".
        """
        
        try:
            response = self.model.generate_content(prompt) # MODIFIÉ
            correction_complete = response.text
            
            score = -1
            match = re.search(r"SCORE: (\d+)%", correction_complete)
            
            if match:
                score = int(match.group(1))
                print(f"Score détecté : {score}%")
            else:
                print("Erreur : Score non trouvé dans la réponse de l'IA.")
                ScrollableMessageDialog(self, "Erreur d'analyse IA", 
                                        f"L'IA n'a pas retourné de score en %.\n\nRéponse brute :\n{correction_complete}", 
                                        bootstyle="warning")
                self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", state=NORMAL)
                return
            if score >= 85:
                self.evaluation_reussie = True
                titre_eval = self.text_cours.get("1.0", "2.0").strip()
                if len(titre_eval) > 70:
                    titre_eval = titre_eval[:70] + "..."
                self.sauvegarder_historique(score, titre_eval) 

                ScrollableMessageDialog(self, "Félicitations !", 
                                        f"Score : {score}%\n\n{correction_complete}", 
                                        bootstyle="success") 
                
                self.tenter_deblocage() # FIX LOGIQUE
                
            elif score >= 75:
                self.evaluation_reussie = False
                ScrollableMessageDialog(self, "Presque !", 
                                        f"Score : {score}%\n\n{correction_complete}\n\nC'est bien, mais vise au moins 85% ! Corrige tes réponses et ressoumets.", 
                                        bootstyle="warning")
                self.btn_verifier_eval.config(text="SOUMETTRE À NOUVEAU", state=NORMAL)
                
            else:
                self.evaluation_reussie = False
                ScrollableMessageDialog(self, "Incorrect", 
                                        f"Score : {score}%\n\n{correction_complete}\n\nRevois ton cours. L'exercice va être réinitialisé, tu devras en générer un nouveau.", 
                                        bootstyle="danger")
                
                self.text_exercice_genere.config(state=NORMAL)
                self.text_exercice_genere.delete("1.0", tk.END)
                self.text_exercice_genere.insert("1.0", "Échoué. Clique sur 'Générer l'exercice' pour un nouvel essai.")
                self.text_exercice_genere.config(state=DISABLED)
                self.text_reponses_eval.delete("1.0", tk.END)
                
                self.btn_generer_eval.config(text="Générer un NOUVEL exercice", state=NORMAL)
                self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", state=DISABLED, bootstyle="success-outline")

        except Exception as e:
            messagebox.showerror("Erreur API", f"Une erreur est survenue lors de la correction de l'IA.\n{e}")
            self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", state=NORMAL)
            
    # --- FONCTIONS DE BLOCAGE (Classe) ---
    def tenter_deblocage(self):
        if self.devoirs_termines or self.evaluation_reussie:
            messagebox.showinfo("BRAVO !", "Tu as terminé une de tes tâches ! Le mode focus va se désactiver.")
            self.debloquer_applications()
        
    def commencer_mode_focus(self):
        cours_colle = len(self.text_cours.get("1.0", tk.END).strip()) > 10
        devoirs_sauvegardes = bool(self.devoirs_data) and not all(data["corrige"] for data in self.devoirs_data.values())
        
        if not devoirs_sauvegardes and not cours_colle:
             messagebox.showwarning("Rien à faire", "Tu dois d'abord sauvegarder un devoir (onglet 1) OU coller un cours (onglet 2) avant d'activer le mode focus.")
             return
             
        print("Mode concentration ACTIVÉ !")
        
        succes_sites = bloquer_sites(self.sites_a_bloquer) 
        
        if succes_sites:
            self.mode_focus_actif = True
            self.devoirs_termines = False
            self.evaluation_reussie = False
            
            if not devoirs_sauvegardes: self.devoirs_termines = True
            if not cours_colle: self.evaluation_reussie = True
            
            self.btn_bloquer.config(text="Mode Focus ACTIF", bootstyle="danger", state=DISABLED)
            
            if cours_colle and not self.text_exercice_genere.get("1.0", tk.END).strip():
                self.btn_generer_eval.config(state=NORMAL)
            
            print("Démarrage du thread 'killer'...")
            self.thread_stop_event = threading.Event()
            self.thread_killer = threading.Thread(target=thread_killer_loop, 
                                                  args=(self.thread_stop_event, self.apps_a_bloquer,), 
                                                  daemon=True)
            self.thread_killer.start()
            
            messagebox.showinfo("Focus Activé", 
                                "Mode concentration activé. Sites et applications bloqués. Au travail !")

    def debloquer_applications(self):
        print("Mode concentration DÉSACTIVÉ !")
        
        if self.thread_killer and self.thread_killer.is_alive():
            self.thread_stop_event.set()
            self.thread_killer.join(timeout=2)
        
        debloquer_sites(self.sites_a_bloquer) 
        
        self.mode_focus_actif = False
        self.btn_bloquer.config(text="Activer le mode Focus", bootstyle="danger-outline", state=NORMAL)
        
        self.devoirs_data = {}
        self.listbox_devoirs.delete(0, tk.END)
        self.text_cours.delete("1.0", tk.END)
        self.text_exercice_genere.config(state=NORMAL)
        self.text_exercice_genere.delete("1.0", tk.END)
        self.text_exercice_genere.config(state=DISABLED)
        self.text_reponses_eval.delete("1.0", tk.END)
        self.btn_generer_eval.config(text="Générer l'exercice", state=DISABLED)
        
        self.btn_verifier_eval.config(state=NORMAL) # 1. Dégel
        self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", bootstyle="success-outline") # 2. Texte
        self.update_idletasks() # 3. Redessin
        self.btn_verifier_eval.config(state=DISABLED) # 4. Re-désactivation

        messagebox.showinfo("Terminé !", "Applications et sites débloqués ! Session terminée.")

    def on_closing(self):
        print("Fermeture de l'application...")
        self.sauvegarder_session_json() 
        if self.mode_focus_actif:
            self.debloquer_applications()
        self.destroy()


# --- Lancement de l'application ---
if __name__ == "__main__":
    try:
        os.listdir(os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32\\drivers\\etc'))
    except PermissionError:
        messagebox.showwarning("Droits Admin Requis", 
                             "Pense à (re)lancer ce script en tant qu'Administrateur "
                             "pour que le blocage fonctionne.")

    app = AppDevoirsIA()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()