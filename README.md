# Blokk v1.4

`Blokk` est une application de productivité et de révision "implacable" conçue pour vous forcer à vous concentrer. Elle bloque vos sites web et applications de distraction (jeux, réseaux sociaux) et ne les débloque que lorsque vous avez *prouvé* à une IA (Google Gemini) que vous avez terminé votre travail.



## 🎯 Le Concept

`Blokk` n'est pas un simple minuteur. C'est un tuteur IA qui agit comme un gardien.

1.  Vous entrez vos tâches (soit des devoirs à faire, soit un cours à réviser).
2.  Vous cliquez sur **"Activer le mode Focus"**.
3.  Immédiatement, `Blokk` **bloque** tous les sites et applications que vous avez configurés.
4.  Vous devez alors **prouver que vous avez travaillé** en accomplissant l'une des deux tâches :
    * **Option 1 (Devoirs) :** Soumettre vos devoirs à l'IA. L'IA doit valider *tous* vos devoirs comme "CORRECTS".
    * **Option 2 (Évaluation) :** L'IA génère un exercice basé sur votre cours. Vous devez répondre à l'exercice et obtenir un score d'au moins **85%**.
5.  Dès que l'une de ces conditions est remplie, `Blokk` **désactive le mode Focus** et débloque tout.

## ✨ Fonctionnalités

* **Mode Focus Stricte :** Bloque les sites web (via le fichier `hosts`) et les applications (en tuant les processus).
* **Correction de Devoirs (IA) :** Soumettez un énoncé et votre réponse. L'IA "Professeur Gemini" vous dit si c'est `CORRECT` ou `INCORRECT` avec une brève explication.
* **Générateur d'Évaluation (IA) :** Collez votre cours (texte brut, PDF, URL, ou même une image/screenshot) et l'IA génère un exercice de 5 questions pour tester votre compréhension.
* **Notation par IA :** L'IA corrige votre évaluation et vous donne un score en pourcentage.
* **Import de Données :** Chargez vos cours depuis des fichiers `.pdf`, des URL de pages web ou des images (OCR).
* **Historique des Scores :** L'onglet "Statistiques" conserve une trace de vos succès aux évaluations.
* **Entièrement Personnalisable :** Configurez précisément quels sites (`youtube.com`, `twitch.tv`, etc.) et quelles applications (`Steam.exe`, `Discord.exe`, etc.) doivent être bloqués.

---

## ⚠️ Prérequis Indispensables

Avant de commencer, vous avez besoin de deux choses :

1.  **Droits Administrateur (Windows) :** L'application **doit être lancée en tant qu'Administrateur** pour pouvoir modifier le fichier `hosts` (pour bloquer les sites) et tuer les processus (pour bloquer les applications).
2.  **Clé API Google Gemini :** L'application est propulsée par l'IA de Google.
    * Vous devez obtenir une clé API **gratuite** pour le modèle Gemini (le script utilise `gemini-1.5-pro`).
    * Obtenez votre clé sur [**Google AI Studio**](https://aistudio.google.com/).

## 🚀 Installation et Lancement

1.  Assurez-vous d'avoir Python 3 installé sur votre machine.
2.  Clonez ce dépôt ou téléchargez les fichiers (`Blokk v1.4.py`, `icon.ico`).
3.  Installez les bibliothèques Python nécessaires :
    ```bash
    pip install ttkbootstrap google-generativeai pillow pypdf requests beautifulsoup4 psutil
    ```
4.  **Important :** Faites un clic droit sur votre terminal (CMD, PowerShell) ou sur le script `.py` et choisissez **"Exécuter en tant qu'administrateur"**.
5.  Lancez le script :
    ```bash
    python "Blokk v1.4.py"
    ```
6.  Au premier lancement, une fenêtre vous demandera votre **Clé API Google Gemini**. Collez-la. L'application la sauvegardera dans un fichier `config.json` pour les prochaines fois.

---

## 📝 Comment l'utiliser

### Scénario 1 : Finir ses devoirs (Onglet 1)

1.  Allez dans l'onglet **"Devoirs à Corriger"**.
2.  Remplissez le "Titre", l' "Énoncé" (la question) et "Ta Réponse".
3.  Cliquez sur **"Sauvegarder ce devoir"**. Répétez pour tous vos devoirs.
4.  Une fois prêt, cliquez sur le gros bouton **"Activer le mode Focus"** en bas. Vos distractions sont maintenant bloquées.
5.  Sélectionnez un devoir dans la liste de gauche et cliquez sur **"VÉRIFIER DEVOIR"**.
6.  L'IA vous donnera une correction. Si c'est "INCORRECT", modifiez votre réponse dans la zone de texte, sauvegardez à nouveau, et re-vérifiez.
7.  Le mode Focus se terminera *uniquement* lorsque **tous les devoirs** de votre liste seront marqués "✅ CORRECT".

### Scénario 2 : Réviser une évaluation (Onglet 2)

1.  Allez dans l'onglet **"Préparation d'Évaluation"**.
2.  Dans la case n°1 ("Colle ton cours ici"), collez vos notes. Vous pouvez aussi utiliser les boutons "Depuis Image", "Depuis PDF" ou "Depuis URL" pour importer votre cours.
3.  Cliquez sur **"Activer le mode Focus"**.
4.  Maintenant, dans la case n°1, cliquez sur **"Générer l'exercice"**. L'IA va lire votre cours et créer un quiz dans la case n°2.
5.  Écrivez vos réponses dans la case n°3 ("Écris tes réponses ici").
6.  Cliquez sur **"SOUMETTRE ÉVAL"**.
7.  L'IA vous donnera un score :
    * **Score < 85% :** Échec. Vous devez corriger vos réponses et ressoumettre (ou parfois recommencer avec un nouvel exercice si vous avez trop échoué). Le blocage reste actif.
    * **Score >= 85% :** Réussite ! Le mode Focus se désactive et vos applications sont débloquées. Votre score est sauvegardé dans les statistiques.

## 🛑 Notes Importantes

* **Quitter l'application :** Si vous fermez l'application (même en force) alors que le mode Focus est actif, le script tentera de débloquer automatiquement vos sites et applications.
* **Fichiers de session :** L'application crée des fichiers `config.json` (pour vos paramètres), `session_data.json` (pour sauvegarder votre travail en cours si vous quittez) et `historique.json` (pour vos scores).
