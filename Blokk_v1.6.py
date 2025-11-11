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
import sounddevice as sd # --- (Audio) ---
import soundfile as sf  # --- (Audio) ---
import numpy as np      # --- (Audio) ---
from pypresence import Presence # --- NOUVEAU (Discord) ---

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

# --- CONFIGURATION DE L'API ---
API_KEY = "AIzaSyAOl_b-yechbS1hk585B-mRYgOpYdI-YwM" # Colle ta clé

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('models/gemini-2.5-pro') 
    print("Modèle IA chargé avec succès.")
except Exception as e:
    ScrollableMessageDialog(None, "Erreur API", 
                            f"Impossible de charger le modèle IA. Vérifie ta clé API et ta connexion.\n{e}", 
                            bootstyle="danger")
    exit()

# -----------------------------------------------------------------
# --- MODULE 2 - LOGIQUE DE BLOCAGE (Inchangé) ---
# -----------------------------------------------------------------
hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
redirect_ip = "127.0.0.1"

def bloquer_sites(sites_a_bloquer):
    # ... (code inchangé, identique à ton fichier)
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
    # ... (code inchangé, identique à ton fichier)
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
    # ... (code inchangé, identique à ton fichier)
    print("Scan des processus en cours...")
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] in apps_a_bloquer:
            try:
                proc.kill()
                print(f"PROCESSUS TUÉ : {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

def thread_killer_loop(stop_event, apps_a_bloquer):
    # ... (code inchangé, identique à ton fichier)
    while not stop_event.is_set():
        tuer_processus_interdits(apps_a_bloquer)
        time.sleep(5) 
    print("Thread 'killer' arrêté.")


# --- CLASSE PRINCIPALE DE L'APPLICATION (v1.5 Discord) ---
class AppDevoirsIA(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly") 
        
        self.title("Blokk v1.5 (Discord)")
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
        
        # --- NOUVEAU : Variables Discord ---
        self.discord_rpc = None
        self.discord_client_id = "1437780831505743977" # ❗❗❗ COLLE TON ID ICI ❗❗❗
        self.discord_thread_stop = threading.Event()
        self.discord_thread = None
        
        # --- Variables Audio ---
        self.is_recording = False
        self.target_widget_for_audio = None
        self.recording_stream = None
        self.recording_frames = []
        self.audio_filename = "temp_audio.wav"
        
        self.sites_a_bloquer_defaut = [
            "www.youtube.com", "youtube.com", "www.tiktok.com", "tiktok.com",
            "www.instagram.com", "instagram.com", "www.facebook.com", "facebook.com",
            "www.twitch.tv", "twitch.tv", "www.reddit.com", "reddit.com"
        ]
        self.apps_a_bloquer_defaut = [
            "Steam.exe", "steamwebhelper.exe", "SteamService.exe",
            "Discord.exe", "Update.exe"
        ]
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # -----------------------------------------------------------------
        # --- ONGLET 1 : DEVOIRS (Modifié) ---
        # -----------------------------------------------------------------
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
        
        frame_reponse_titre = ttk.Frame(frame_droite)
        frame_reponse_titre.pack(fill=X)
        
        label_reponse = ttk.Label(frame_reponse_titre, text="Ta Réponse (Vérifié par GEMINI PRO) :")
        label_reponse.pack(side=LEFT, anchor="w")
        
        self.btn_mic_devoir = ttk.Button(frame_reponse_titre, text="🎤", 
                                         command=lambda: self.toggle_recording(self.text_reponse_devoir, self.btn_mic_devoir),
                                         bootstyle="light-outline")
        self.btn_mic_devoir.pack(side=LEFT, padx=10)
        
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

        # -----------------------------------------------------------------
        # --- ONGLET 2 : ÉVALUATION (Modifié) ---
        # -----------------------------------------------------------------
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

        frame_eval_bottom = ttk.Frame(self.tab_eval, padding=(0, 10, 0, 0))
        frame_eval_bottom.pack(fill=BOTH, expand=True)
        
        frame_reponse_eval_titre = ttk.Frame(frame_eval_bottom)
        frame_reponse_eval_titre.pack(fill=X)
        
        label_reponse_eval = ttk.Label(frame_reponse_eval_titre, text="3. Écris tes réponses ici :")
        label_reponse_eval.pack(side=LEFT, anchor="w", pady=5)

        self.btn_mic_eval = ttk.Button(frame_reponse_eval_titre, text="🎤", 
                                       command=lambda: self.toggle_recording(self.text_reponses_eval, self.btn_mic_eval),
                                       bootstyle="light-outline")
        self.btn_mic_eval.pack(side=LEFT, padx=10)
        
        self.text_reponses_eval = tk.Text(frame_eval_bottom, height=10, font=("Helvetica", 10))
        self.text_reponses_eval.pack(fill=BOTH, expand=True)
        
        self.btn_charger_reponse_eval = ttk.Button(frame_eval_bottom, text="Charger la réponse depuis une image",
                                             command=self.charger_reponse_eval_depuis_image,
                                             bootstyle="info-outline")
        self.btn_charger_reponse_eval.pack(fill=X, pady=5) 

        # -----------------------------------------------------------------
        # --- ONGLET 3 : PARAMÈTRES (Inchangé) ---
        # -----------------------------------------------------------------
        self.tab_parametres = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_parametres, text="Paramètres")
        
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

        # -----------------------------------------------------------------
        # --- ONGLET 4 : STATISTIQUES (Inchangé) ---
        # -----------------------------------------------------------------
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


        # -----------------------------------------------------------------
        # --- ZONE D'ACTION PRINCIPALE (Inchangée) ---
        # -----------------------------------------------------------------
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
        
        # --- CHARGEMENT DES DONNÉES ---
        self.charger_parametres()
        self.charger_session_json() 
        self.charger_historique()
        
        # --- NOUVEAU : Démarrer le thread Discord ---
        self.lancer_thread_discord()


    # --- FONCTIONS DE PARAMÈTRES (Inchangées) ---
    def sauvegarder_parametres(self):
        # ... (code inchangé, identique à ton fichier)
        print("Sauvegarde des paramètres...")
        sites_bruts = self.text_sites_bloques.get("1.0", tk.END).strip()
        apps_brutes = self.text_apps_bloquees.get("1.0", tk.END).strip()
        self.sites_a_bloquer = [ligne.strip() for ligne in sites_bruts.splitlines() if ligne.strip()]
        self.apps_a_bloquer = [ligne.strip() for ligne in apps_brutes.splitlines() if ligne.strip()]
        config = { "sites": self.sites_a_bloquer, "apps": self.apps_a_bloquer }
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("Sauvegardé", "Paramètres de blocage sauvegardés.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder config.json: {e}")

    def charger_parametres(self):
        # ... (code inchangé, identique à ton fichier)
        print("Chargement des paramètres...")
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            self.sites_a_bloquer = config.get("sites", self.sites_a_bloquer_defaut)
            self.apps_a_bloquer = config.get("apps", self.apps_a_bloquer_defaut)
            print("Paramètres chargés depuis config.json.")
        except FileNotFoundError:
            print("config.json non trouvé. Utilisation des paramètres par défaut.")
            self.sites_a_bloquer = self.sites_a_bloquer_defaut[:]
            self.apps_a_bloquer = self.apps_a_bloquer_defaut[:]
        except Exception as e:
            messagebox.showerror("Erreur Config", f"Impossible de lire config.json: {e}")
        self.text_sites_bloques.delete("1.0", tk.END)
        self.text_sites_bloques.insert("1.0", "\n".join(self.sites_a_bloquer))
        self.text_apps_bloquees.delete("1.0", tk.END)
        self.text_apps_bloquees.insert("1.0", "\n".join(self.apps_a_bloquer))

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
            
    # --- FONCTIONS OCR (Onglet 1 - Inchangées) ---
    def charger_reponse_depuis_image(self):
        # ... (code inchangé, identique à ton fichier)
        file_path = filedialog.askopenfilename(title="Sélectionner une image de ta réponse", filetypes=[("Fichiers Image", "*.png *.jpg *.jpeg")])
        if not file_path: return
        messagebox.showinfo("Chargement d'image", "Chargement de l'image et extraction du texte par l'IA en cours...\nMerci de patienter.")
        threading.Thread(target=self._process_reponse_image_in_background, args=(file_path,)).start()
    def _process_reponse_image_in_background(self, file_path):
        # ... (code inchangé, identique à ton fichier)
        try:
            img = Image.open(file_path)
            prompt_content = ["Extrais tout le texte manuscrit ou imprimé de cette image et retranscris-le.", img]
            response = model.generate_content(prompt_content)
            extracted_text = response.text
            self.after(0, lambda: self._update_reponse_text(extracted_text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Lecture Image", f"Impossible de lire l'image ou d'extraire le texte.\nErreur: {e}"))
    def _update_reponse_text(self, text):
        # ... (code inchangé, identique à ton fichier)
        self.text_reponse_devoir.delete("1.0", tk.END)
        self.text_reponse_devoir.insert("1.0", text)
        messagebox.showinfo("Extraction Réussie", "Le texte de ton image a été extrait.")
        
    # --- FONCTIONS OCR (Onglet 2 - Cours - Inchangées) ---
    def charger_cours_depuis_image(self):
        # ... (code inchangé, identique à ton fichier)
        file_path = filedialog.askopenfilename(title="Sélectionner une image de cours", filetypes=[("Fichiers Image", "*.png *.jpg *.jpeg")])
        if not file_path: return
        messagebox.showinfo("Chargement d'image", "Chargement de l'image et extraction du texte par l'IA en cours...\nMerci de patienter.")
        threading.Thread(target=self._process_image_in_background, args=(file_path,)).start()
    def _process_image_in_background(self, file_path):
        # ... (code inchangé, identique à ton fichier)
        try:
            img = Image.open(file_path)
            prompt_content = ["Extrais tout le texte de cette image et retranscris-le.", img]
            response = model.generate_content(prompt_content)
            extracted_text = response.text
            self.after(0, lambda: self._update_cours_text(extracted_text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Lecture Image", f"Impossible de lire l'image ou d'extraire le texte.\nErreur: {e}"))
    def _update_cours_text(self, text):
        # ... (code inchangé, identique à ton fichier)
        self.text_cours.delete("1.0", tk.END)
        self.text_cours.insert("1.0", text)
        messagebox.showinfo("Extraction Réussie", "Le texte de l'image a été extrait.")

    # --- NOUVEAU : FONCTIONS OCR (Onglet 2 - Réponse) ---
    def charger_reponse_eval_depuis_image(self):
        file_path = filedialog.askopenfilename(title="Sélectionner une image de ta réponse", filetypes=[("Fichiers Image", "*.png *.jpg *.jpeg")])
        if not file_path: return
        messagebox.showinfo("Chargement d'image", "Chargement de l'image et extraction du texte par l'IA en cours...\nMerci de patienter.")
        threading.Thread(target=self._process_reponse_eval_image_in_background, args=(file_path,)).start()

    def _process_reponse_eval_image_in_background(self, file_path):
        try:
            img = Image.open(file_path)
            prompt_content = ["Extrais tout le texte manuscrit ou imprimé de cette image et retranscris-le.", img]
            response = model.generate_content(prompt_content)
            extracted_text = response.text
            self.after(0, lambda: self._update_reponse_eval_text(extracted_text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Lecture Image", f"Impossible de lire l'image ou d'extraire le texte.\nErreur: {e}"))

    def _update_reponse_eval_text(self, text):
        self.text_reponses_eval.delete("1.0", tk.END)
        self.text_reponses_eval.insert("1.0", text)
        messagebox.showinfo("Extraction Réussie", "Le texte de ton image a été extrait.")

    # --- FONCTIONS D'IMPORT PDF/URL (Inchangées) ---
    def importer_depuis_pdf(self):
        # ... (code inchangé, identique à ton fichier)
        file_path = filedialog.askopenfilename(title="Sélectionner un fichier PDF", filetypes=[("Fichiers PDF", "*.pdf")])
        if not file_path: return
        messagebox.showinfo("Chargement PDF", "Lecture du PDF en cours... Merci de patienter.")
        threading.Thread(target=self._process_pdf_in_background, args=(file_path,)).start()
    def _process_pdf_in_background(self, file_path):
        # ... (code inchangé, identique à ton fichier)
        try:
            text = ""
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
            self.after(0, lambda: self._update_cours_text(text))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur PDF", f"Impossible de lire le fichier PDF.\nErreur: {e}"))
    def importer_depuis_url(self):
        # ... (code inchangé, identique à ton fichier)
        url = simpledialog.askstring("Importer depuis URL", "Entre l'URL de la page web :", parent=self)
        if not url: return
        messagebox.showinfo("Chargement URL", "Récupération de la page web... Merci de patienter.")
        threading.Thread(target=self._process_url_in_background, args=(url,)).start()
    def _process_url_in_background(self, url):
        # ... (code inchangé, identique à ton fichier)
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
        # ... (code inchangé, identique à ton fichier)
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
        # ... (code inchangé, identique à ton fichier)
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
        # ... (code inchangé, identique à ton fichier)
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


    # --- NOUVEAU : FONCTIONS D'ENREGISTREMENT AUDIO ---
    
    def toggle_recording(self, target_widget, button_widget):
        """Démarre ou arrête l'enregistrement audio."""
        if self.is_recording:
            # --- Arrêter l'enregistrement ---
            print("Arrêt de l'enregistrement...")
            self.is_recording = False
            self.recording_stream.stop()
            self.recording_stream.close()
            button_widget.config(text="🎤", bootstyle="light-outline") # Réinitialiser le bouton
            
            # Sauvegarder l'audio
            try:
                recording = np.concatenate(self.recording_frames, axis=0)
                sf.write(self.audio_filename, recording, samplerate=44100)
                print(f"Audio sauvegardé : {self.audio_filename}")
                
                messagebox.showinfo("Transcription en cours", "Enregistrement terminé. Transcription en cours... Merci de patienter.")
                self.target_widget_for_audio = target_widget
                threading.Thread(target=self._process_audio_in_background).start()
                
            except Exception as e:
                messagebox.showerror("Erreur Audio", f"Impossible de sauvegarder l'audio.\nErreur: {e}")

        else:
            # --- Démarrer l'enregistrement ---
            print("Démarrage de l'enregistrement...")
            self.is_recording = True
            self.recording_frames = []
            
            try:
                self.recording_stream = sd.InputStream(
                    callback=self.audio_callback, 
                    samplerate=44100, 
                    channels=1, 
                    dtype='float32'
                )
                self.recording_stream.start()
                button_widget.config(text="ARRÊTER 🔴", bootstyle="danger")
            except Exception as e:
                messagebox.showerror("Erreur Micro", f"Impossible d'accéder au microphone.\nErreur: {e}")
                self.is_recording = False
    
    def audio_callback(self, indata, frames, time, status):
        """Appelée à chaque fois que le micro reçoit du son."""
        if status:
            print(status, file=sys.stderr)
        self.recording_frames.append(indata.copy())

    def _process_audio_in_background(self):
        """Fonction threadée pour transcrire l'audio avec l'IA."""
        try:
            print("Téléversement de l'audio vers l'API...")
            audio_file = genai.upload_file(path=self.audio_filename)
            print("Téléversement terminé. Demande de transcription...")
            
            prompt_content = [
                "Transcris l'intégralité de cet enregistrement audio en texte. Ne rajoute rien d'autre, seulement la transcription.", 
                audio_file
            ]
            response = model.generate_content(prompt_content)
            extracted_text = response.text
            
            self.after(0, lambda: self._update_text_from_audio(extracted_text))
            
            print("Nettoyage des fichiers...")
            genai.delete_file(audio_file.name)
            if os.path.exists(self.audio_filename):
                os.remove(self.audio_filename)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur Transcription", f"Impossible de transcrire l'audio.\nErreur: {e}"))
            if os.path.exists(self.audio_filename):
                os.remove(self.audio_filename)

    def _update_text_from_audio(self, text):
        """Ajoute le texte transcrit à la boîte de réponse ciblée."""
        if self.target_widget_for_audio:
            self.target_widget_for_audio.insert(tk.END, text + " ")
            messagebox.showinfo("Transcription Réussie", "Le texte de votre audio a été ajouté.")
        self.target_widget_for_audio = None


    # --- NOUVEAU : FONCTIONS DISCORD RICH PRESENCE ---

    def lancer_thread_discord(self):
        """Lance le thread qui gère la connexion à Discord."""
        self.discord_thread_stop.clear()
        self.discord_thread = threading.Thread(target=self.discord_presence_loop, daemon=True)
        self.discord_thread.start()

    def discord_presence_loop(self):
        """La boucle qui tourne en fond pour Discord."""
        while not self.discord_thread_stop.is_set():
            try:
                # 1. Tenter de se connecter
                self.discord_rpc = Presence(self.discord_client_id)
                self.discord_rpc.connect()
                print("Connecté à Discord Rich Presence.")
                
                # 2. Mettre à jour le statut (on est en "pause" au début)
                self.update_discord_status("Inactif", "Prêt à travailler.")
                
                # 3. Boucle de maintien
                while not self.discord_thread_stop.is_set():
                    time.sleep(15) # pypresence s'occupe de garder la connexion
                    
            except Exception as e:
                # On met 'pass' pour ne pas spammer la console si Discord n'est pas lancé
                pass 
                
            # Si la connexion est perdue, attendre 30s avant de réessayer
            if not self.discord_thread_stop.is_set():
                time.sleep(30)
        
        # Fin du thread
        if self.discord_rpc:
            try:
                self.discord_rpc.close()
            except:
                pass # Ignorer les erreurs à la fermeture
        print("Thread Discord arrêté.")

    def update_discord_status(self, state, details):
        """Met à jour le statut affiché sur Discord."""
        if self.discord_rpc:
            try:
                self.discord_rpc.update(
                    state=state,
                    details=details,
                    large_image="icon_large", # Nom de l'asset uploadé sur le portail dev
                    large_text="Blokk"
                )
            except Exception as e:
                # Échoue silencieusement si la connexion est perdue
                pass

    # --- FONCTIONS DE L'ONGLET 1 (Inchangées) ---
    def sauvegarder_devoir(self):
        # ... (code inchangé)
        titre = self.entry_titre_devoir.get()
        sujet = self.text_sujet_devoir.get("1.0", tk.END).strip()
        reponse = self.text_reponse_devoir.get("1.0", tk.END).strip()
        if not titre or not sujet or not reponse:
            messagebox.showwarning("Champs manquants", "...")
            return
        self.devoirs_data[titre] = {"sujet": sujet, "reponse": reponse, "corrige": False}
        if titre not in self.listbox_devoirs.get(0, tk.END):
            self.listbox_devoirs.insert(tk.END, titre)
        messagebox.showinfo("Sauvegardé", f"Le devoir '{titre}' a été sauvegardé.")
        self.entry_titre_devoir.delete(0, tk.END)
        self.text_sujet_devoir.delete("1.0", tk.END)
        self.text_reponse_devoir.delete("1.0", tk.END)

    def charger_devoir_selectionne(self, event):
        # ... (code inchangé)
        try:
            titre_selectionne = self.listbox_devoirs.get(self.listbox_devoirs.curselection())
            titre_propre = titre_selectionne.replace("✅ ", "").replace(" (CORRECT)", "")
            data = self.devoirs_data[titre_propre]
            self.entry_titre_devoir.delete(0, tk.END)
            self.text_sujet_devoir.delete("1.0", tk.END)
            self.text_reponse_devoir.delete("1.0", tk.END)
            self.entry_titre_devoir.insert(0, titre_propre)
            self.text_sujet_devoir.insert("1.0", data["sujet"])
            self.text_reponse_devoir.insert("1.0", data["reponse"])
        except tk.TclError:
            pass

    def lancer_verification_devoir(self):
        # ... (code inchangé, AVEC FIX VISUEL)
        if not self.mode_focus_actif:
            messagebox.showerror("Mode Focus Inactif", "...")
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
            
        self.btn_verifier_devoir.config(text="Vérification en cours...")
        self.update_idletasks()
        self.btn_verifier_devoir.config(state=DISABLED)
        
        prompt = f"""...""" # (prompt inchangé)
        try:
            response = model.generate_content(prompt)
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
                ScrollableMessageDialog(self, "Erreur de formatage IA", f"...", bootstyle="warning")
        except Exception as e:
            messagebox.showerror("Erreur API", f"Une erreur est survenue lors de la connexion à l'IA.\n{e}")
        self.btn_verifier_devoir.config(text="VÉRIFIER DEVOIR", state=NORMAL)

    def verifier_si_devoirs_finis(self):
        # ... (code inchangé)
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
            
    # --- FONCTIONS DE L'ONGLET 2 (Évaluation) ---
    def generer_exercice_ia(self):
        # ... (code inchangé)
        if not self.mode_focus_actif:
            messagebox.showerror("Mode Focus Inactif", "...")
            return
        cours = self.text_cours.get("1.0", tk.END).strip()
        if not cours:
            messagebox.showwarning("Cours manquant", "Tu dois coller ton cours dans la case n°1.")
            return
        self.btn_generer_eval.config(text="Génération en cours... L'IA réfléchit...", state=DISABLED)
        self.update_idletasks()
        prompt = f"""...""" # (prompt inchangé)
        try:
            response = model.generate_content(prompt)
            exercice_genere = response.text
            self.text_exercice_genere.config(state=NORMAL)
            self.text_exercice_genere.delete("1.0", tk.END)
            self.text_exercice_genere.insert("1.0", exercice_genere)
            self.text_exercice_genere.config(state=DISABLED)
            self.btn_verifier_eval.config(state=NORMAL, bootstyle="success")
            self.btn_generer_eval.config(text="Exercice généré !", state=DISABLED)
            messagebox.showinfo("Exercice Prêt !", "...")
        except Exception as e:
            messagebox.showerror("Erreur API", f"Une erreur est survenue lors de la génération de l'IA.\n{e}")
            self.btn_generer_eval.config(text="Générer l'exercice", state=NORMAL)

    def lancer_verification_eval(self):
        # ... (code inchangé, AVEC TOUS LES FIX)
        cours = self.text_cours.get("1.0", tk.END).strip()
        exercice = self.text_exercice_genere.get("1.0", tk.END).strip()
        reponses_eleve = self.text_reponses_eval.get("1.0", tk.END).strip()
        if not reponses_eleve:
            messagebox.showwarning("Réponses manquantes", "...")
            return
        self.btn_verifier_eval.config(text="Correction en cours...")
        self.update_idletasks()
        self.btn_verifier_eval.config(state=DISABLED)
        prompt = f"""...""" # (prompt inchangé)
        try:
            response = model.generate_content(prompt)
            correction_complete = response.text
            score = -1
            match = re.search(r"SCORE: (\d+)%", correction_complete)
            if match:
                score = int(match.group(1))
                print(f"Score détecté : {score}%")
            else:
                print("Erreur : Score non trouvé dans la réponse de l'IA.")
                ScrollableMessageDialog(self, "Erreur d'analyse IA", f"...", bootstyle="warning")
                self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", state=NORMAL)
                return
            if score >= 85:
                self.evaluation_reussie = True
                titre_eval = self.text_cours.get("1.0", "2.0").strip()
                if len(titre_eval) > 70: titre_eval = titre_eval[:70] + "..."
                self.sauvegarder_historique(score, titre_eval) 
                ScrollableMessageDialog(self, "Félicitations !", f"...", bootstyle="success") 
                self.tenter_deblocage()
            elif score >= 75:
                self.evaluation_reussie = False
                ScrollableMessageDialog(self, "Presque !", f"...", bootstyle="warning")
                self.btn_verifier_eval.config(text="SOUMETTRE À NOUVEAU", state=NORMAL)
            else:
                self.evaluation_reussie = False
                ScrollableMessageDialog(self, "Incorrect", f"...", bootstyle="danger")
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
        # ... (code inchangé, AVEC LOGIQUE "OR")
        if self.devoirs_termines or self.evaluation_reussie:
            messagebox.showinfo("BRAVO !", "Tu as terminé une de tes tâches ! Le mode focus va se désactiver.")
            self.debloquer_applications()
        
    def commencer_mode_focus(self):
        # ... (code inchangé)
        cours_colle = len(self.text_cours.get("1.0", tk.END).strip()) > 10
        devoirs_sauvegardes = bool(self.devoirs_data) and not all(data["corrige"] for data in self.devoirs_data.values())
        if not devoirs_sauvegardes and not cours_colle:
             messagebox.showwarning("Rien à faire", "...")
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
            messagebox.showinfo("Focus Activé", "...")
            
            # --- NOUVEAU : Update Discord ---
            self.update_discord_status("En Mode Focus 🔒", "Concentration maximale.")

    def debloquer_applications(self):
        # ... (code inchangé, AVEC FIX VISUEL)
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
        self.btn_verifier_eval.config(state=NORMAL)
        self.btn_verifier_eval.config(text="SOUMETTRE ÉVAL", bootstyle="success-outline")
        self.update_idletasks()
        self.btn_verifier_eval.config(state=DISABLED)
        messagebox.showinfo("Terminé !", "Applications et sites débloqués ! Session terminée.")
        
        # --- NOUVEAU : Update Discord ---
        self.update_discord_status("En Pause ✅", "Travail terminé !")

    def on_closing(self):
        print("Fermeture de l'application...")
        
        # --- NOUVEAU : Arrêter Discord ---
        self.discord_thread_stop.set()
        
        self.sauvegarder_session_json() 
        if self.is_recording:
            self.recording_stream.stop()
            self.recording_stream.close()
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