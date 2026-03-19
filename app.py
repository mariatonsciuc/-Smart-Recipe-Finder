import customtkinter as ctk
import speech_recognition as sr
import requests
import threading
from PIL import Image
from io import BytesIO
import webbrowser
import urllib.parse
import re 

# --- CONFIGURARE INTERFAȚĂ ---
# Setăm tema globală a aplicației (Dark Mode și accente albastre)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- CONFIGURARE API ---
# Cheia de acces pentru Spoonacular API.
API_KEY = "your_key" 

class BackendManager:
    """
    Clasa responsabilă pentru logica de Backend.
    Gestionează:
    1. Comunicarea cu API-ul extern (Spoonacular).
    2. Procesarea textului (NLP simplificat).
    3. Procesarea vocii (Speech-to-Text).
    4. Descărcarea imaginilor.
    """
    def __init__(self):
        """
        Constructorul clasei Backend.
        Inițializează recunoașterea vocală și configurează header-ul pentru API.
        """
        self.recognizer = sr.Recognizer()
        self.base_url = "https://api.spoonacular.com/recipes"
        # Header-ul HTTP necesar pentru autentificarea la Spoonacular
        self.headers = {"x-api-key": API_KEY}

    def search_smart_recipe(self, ingredients_str):
        """
        Algoritmul principal de căutare a rețetelor ('Smart Search').
        
        Logica:
        1. Curăță și formatează inputul utilizatorului (Regex).
        2. Interoghează API-ul pentru a găsi 20 de rețete potențiale.
        3. Aplică un algoritm local de sortare pentru a prioritiza rețetele
           care folosesc cele mai multe ingrediente din frigider.
        4. Extrage detaliile complete pentru rețeta câștigătoare.

        Args:
            ingredients_str (str): Lista de ingrediente brută (ex: "eggs, ham cheese").

        Returns:
            dict: Obiect JSON cu detaliile rețetei (titlu, instrucțiuni, imagine).
            str: Mesaj de eroare ("ERROR_CONN", "ERROR_AUTH") în caz de probleme.
            None: Dacă nu s-au găsit rezultate.
        """
        try:
            # 1. Înlocuim virgulele cu spații pentru a normaliza
            # 2. Folosim regex pentru a sparge textul în cuvinte, ignorând spațiile multiple
            # Ex: "peanut butter, jelly" -> ["peanut", "butter", "jelly"]
            
            # Curățăm textul de caractere ciudate, păstrăm doar litere și virgule/spații
            clean_text = re.sub(r'[^a-zA-Z0-9, ]', '', ingredients_str)
            
            # Dacă userul a folosit virgule, separăm după virgule
            if "," in clean_text:
                items = [x.strip() for x in clean_text.split(",") if x.strip()]
            else:
                # Dacă nu are virgule, separăm după spații
                items = [x.strip() for x in clean_text.split(" ") if x.strip()]

            # Reconstruim string-ul pentru API (format: item1,item2,item3)
            formatted_ingr = ",".join(items)
            
            # Calculăm câte ingrediente a dat userul
            user_ingredient_count = len(items)

            print(f"DEBUG - Caut ingredientele: {formatted_ingr}")

            # --- PASUL 1: Căutare Extinsă ---
            search_url = f"{self.base_url}/findByIngredients"
            params = {
                "ingredients": formatted_ingr,
                "number": 20,             # Cerem 20 de rețete ca să avem de unde alege
                "ranking": 2,             # 2 = Minimize missing ingredients (mai safe pentru combinații)
                "ignorePantry": "true"
            }
            
            response = requests.get(search_url, headers=self.headers, params=params)
            
            # Verificare status coduri HTTP
            if response.status_code == 401: return "ERROR_AUTH"
            if response.status_code == 402: return "ERROR_QUOTA" # Ai depășit limita zilnică
            
            results = response.json()
            if not results: return None
            
            # --- PASUL 2: ALGORITM DE FILTRARE STRICTĂ ---
            # Adăugăm un scor personalizat pentru fiecare rețetă
            valid_results = []
            
            for recipe in results:
                used_count = recipe['usedIngredientCount']
                missed_count = recipe['missedIngredientCount']
                
                # Dacă utilizatorul a dat mai mult de 2 ingrediente,
                # refuzăm orice rețetă care folosește doar 1 ingredient.
                if user_ingredient_count > 2 and used_count < 2:
                    continue 
                
                # Calculăm un scor: (Ingrediente folosite * 3) - Ingrediente lipsă
                # Asta prioritizează masiv ce avem noi în frigider
                score = (used_count * 3) - missed_count
                recipe['_custom_score'] = score
                valid_results.append(recipe)
            
            # Dacă am filtrat tot și nu a rămas nimic (prea strict), revenim la rezultatele brute
            if not valid_results:
                valid_results = results
                for r in valid_results: r['_custom_score'] = r['usedIngredientCount']

            # Sortăm după scorul nostru personalizat (descrescător)
            valid_results.sort(key=lambda x: x['_custom_score'], reverse=True)
            
            best_match = valid_results[0]
            recipe_id = best_match['id']
            
            print(f"DEBUG - Rețetă aleasă: {best_match['title']} (Score: {best_match['_custom_score']})")

            # --- PASUL 3: Detalii complete ---
            # Facem un nou request folosind ID-ul rețetei pentru a primi instrucțiunile
            info_url = f"{self.base_url}/{recipe_id}/information"
            info_response = requests.get(info_url, headers=self.headers)
            return info_response.json()

        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return "ERROR_CONN"
        except Exception as e:
            print(f"General Error: {e}")
            return None

    def get_image_from_url(self, url):
        """
        Descarcă o imagine de la un URL și o convertește într-un format compatibil cu PIL.
        
        Args:
            url (str): Adresa web a imaginii.
            
        Returns:
            PIL.Image: Obiectul imagine gata de afișare.
            None: Dacă descărcarea eșuează.
        """
        try:
            if not url: return None
            response = requests.get(url)
            img_data = BytesIO(response.content) # Convertim bytes în stream
            return Image.open(img_data)
        except:
            return None

    def listen_to_microphone(self):
        """
        Activează microfonul și convertește vorbirea în text folosind Google Speech Recognition API.
        
        Returns:
            str: Textul recunoscut (în engleză).
            str: Coduri de eroare ("TIMEOUT", "UNKNOWN", "ERROR_API").
        """
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                # Ascultăm mai mult (timeout 7s) pentru a permite utilizatorului să gândească
                audio = self.recognizer.listen(source, timeout=7, phrase_time_limit=15)
                return self.recognizer.recognize_google(audio, language="en-US")
            except sr.WaitTimeoutError: return "TIMEOUT"
            except sr.UnknownValueError: return "UNKNOWN"
            except sr.RequestError: return "ERROR_API"


class RecipeApp(ctk.CTk):
    """
    Clasa responsabilă pentru Interfața Grafică (Frontend).
    Moștenește din ctk.CTk (fereastra principală).
    """
    def __init__(self):
        """
        Constructorul interfeței.
        Configurează layout-ul, sidebar-ul, butoanele și zona de afișare a conținutului.
        """
        super().__init__()
        self.backend = BackendManager()
        self.current_source_url = ""
        self.current_recipe_title = ""

        # GUI Setup - Configurare fereastră principală
        self.title("Smart Recipe Finder - Advanced")
        self.geometry("1100x800")
        
        # Grid layout: 2 coloane (Sidebar fix, Content elastic)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR (Stânga) ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        # Elemente Sidebar
        ctk.CTkLabel(self.sidebar, text="Smart Kitchen", font=("Arial", 24, "bold")).grid(row=0, column=0, padx=20, pady=30)
        ctk.CTkLabel(self.sidebar, text="Ingredients (comma or space):").grid(row=1, column=0, padx=20, pady=(10,0))
        
        self.input_entry = ctk.CTkTextbox(self.sidebar, height=100, width=200)
        self.input_entry.grid(row=2, column=0, padx=20, pady=10)
        self.input_entry.insert("0.0", "chicken, curry, garlic") # Text default pentru demo
        
        ctk.CTkButton(self.sidebar, text="🔍 Find Best Match", command=self.start_search).grid(row=3, column=0, padx=20, pady=10)
        
        self.voice_btn = ctk.CTkButton(self.sidebar, text="🎤 Voice Input", fg_color="#e74c3c", hover_color="#c0392b", command=self.start_voice)
        self.voice_btn.grid(row=4, column=0, padx=20, pady=10)
        
        self.status_lbl = ctk.CTkLabel(self.sidebar, text="Status: Ready", text_color="gray", wraplength=200)
        self.status_lbl.grid(row=6, column=0, padx=20, pady=20)

        # --- MAIN AREA (Dreapta) ---
        self.main_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Elemente Principale
        self.title_lbl = ctk.CTkLabel(self.main_frame, text="Recipe Result", font=("Arial", 28, "bold"), wraplength=600)
        self.title_lbl.pack(pady=20)

        self.img_lbl = ctk.CTkLabel(self.main_frame, text="[No Image]")
        self.img_lbl.pack(pady=10)

        self.meta_lbl = ctk.CTkLabel(self.main_frame, text="", font=("Arial", 14, "italic"))
        self.meta_lbl.pack(pady=5)

        # BUTTONS FRAME - Zona de sub imagine
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        self.link_btn = ctk.CTkButton(self.btn_frame, text="📖 Full Recipe", width=160, state="disabled", command=self.open_source)
        self.link_btn.grid(row=0, column=0, padx=10)

        self.yt_btn = ctk.CTkButton(self.btn_frame, text="▶ YouTube Video", width=160, fg_color="#FF0000", hover_color="#CC0000", state="disabled", command=self.open_youtube)
        self.yt_btn.grid(row=0, column=1, padx=10)

        self.text_area = ctk.CTkTextbox(self.main_frame, width=700, height=400, font=("Consolas", 14))
        self.text_area.pack(pady=20)
        self.text_area.configure(state="disabled") # Read-only mode

    def start_search(self):
        """
        Inițiază procesul de căutare.
        Validare input -> Pornire thread separat (pentru a nu bloca GUI-ul).
        """
        ing = self.input_entry.get("0.0", "end").strip()
        if not ing: 
            self.status_lbl.configure(text="Please enter ingredients!", text_color="red")
            return
        self.status_lbl.configure(text="Searching & Optimizing...", text_color="orange")
        # Folosim threading pentru ca fereastra să nu înghețe cât timp se descarcă datele
        threading.Thread(target=self.run_search, args=(ing,)).start()

    def start_voice(self):
        """
        Inițiază procesul de recunoaștere vocală pe un thread separat.
        """
        self.status_lbl.configure(text="Listening...", text_color="orange")
        self.voice_btn.configure(state="disabled")
        threading.Thread(target=self.run_voice).start()

    def run_voice(self):
        """
        Logica de fundal pentru voce.
        Apelează backend-ul și actualizează UI-ul cu textul auzit.
        """
        text = self.backend.listen_to_microphone()
        self.voice_btn.configure(state="normal")
        
        if text in ["TIMEOUT", "UNKNOWN", "ERROR_API"]:
            self.status_lbl.configure(text="Voice Error", text_color="red")
        else:
            # Înlocuim "and" cu virgulă pentru o formatare mai bună
            final_text = text.replace(" and ", ", ")
            
            # Update GUI (Thread-safe în ctk)
            self.input_entry.delete("0.0", "end")
            self.input_entry.insert("0.0", final_text)
            self.status_lbl.configure(text=f"Heard: {final_text}", text_color="green")
            
            # Declanșăm automat căutarea după ce am auzit ingredientele
            self.run_search(final_text)

    def run_search(self, ingredients):
        """
        Logica principală de căutare (Rulează în Thread).
        Obține datele din backend și formatează rezultatele pentru afișare.
        
        Args:
            ingredients (str): Lista de ingrediente.
        """
        data = self.backend.search_smart_recipe(ingredients)
        
        # Gestionare erori backend
        if not data:
            self.status_lbl.configure(text="No good match found.", text_color="red")
            return
        if data == "ERROR_QUOTA":
            self.status_lbl.configure(text="API Limit Reached (150/day)", text_color="red")
            return
        if data in ["ERROR_CONN", "ERROR_AUTH"]:
            self.status_lbl.configure(text="Connection/API Key Error", text_color="red")
            return

        # Extragere date din JSON-ul primit
        title = data.get('title')
        self.current_recipe_title = title 
        self.current_source_url = data.get('sourceUrl')
        img_url = data.get('image')
        ready_in = data.get('readyInMinutes', '?')
        servings = data.get('servings', '?')
        
        # Formatare text ingrediente
        content = "INGREDIENTS:\n"
        for ing in data.get('extendedIngredients', []):
            content += f"• {ing['original']}\n"
            
        content += "\nINSTRUCTIONS:\n"
        if data.get('instructions'):
            # Curățare HTML (eliminare tag-uri <ol>, <li> etc.)
            instr = re.sub('<[^<]+?>', '', data['instructions']) 
            content += instr
        else:
            content += "See full instructions on the website."

        # Descărcare imagine
        img = self.backend.get_image_from_url(img_url)
        
        # Actualizare finală UI
        self.update_ui(title, content, img, f"Time: {ready_in} min | Servings: {servings}")

    def update_ui(self, title, content, img, meta):
        """
        Actualizează elementele vizuale ale ferestrei cu datele rețetei.
        """
        self.title_lbl.configure(text=title)
        self.meta_lbl.configure(text=meta)
        
        # Update text area (necesită activare temporară pentru scriere)
        self.text_area.configure(state="normal")
        self.text_area.delete("0.0", "end")
        self.text_area.insert("0.0", content)
        self.text_area.configure(state="disabled")
        
        # Update imagine
        if img:
            ctk_img = ctk.CTkImage(img, size=(500, 350))
            self.img_lbl.configure(image=ctk_img, text="")
        
        # Activare buton link sursă
        if self.current_source_url:
            self.link_btn.configure(state="normal", text="📖 Full Recipe")
        else:
            self.link_btn.configure(state="disabled")
            
        # Butonul de YouTube este mereu activ dacă avem un titlu
        self.yt_btn.configure(state="normal", text="▶ YouTube Video")
        self.status_lbl.configure(text="Success!", text_color="green")

    def open_source(self):
        """Deschide link-ul rețetei originale în browser-ul default."""
        if self.current_source_url: webbrowser.open(self.current_source_url)
            
    def open_youtube(self):
        """
        Generează dinamic un link de căutare YouTube bazat pe titlul rețetei.
        Rezolvă problema lipsei de video-uri din API.
        """
        if self.current_recipe_title:
            # Encodează titlul pentru URL (ex: "Pasta Carbonara" -> "Pasta+Carbonara+recipe")
            query = urllib.parse.quote(self.current_recipe_title + " recipe")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")

if __name__ == "__main__":
    app = RecipeApp()
    app.mainloop()