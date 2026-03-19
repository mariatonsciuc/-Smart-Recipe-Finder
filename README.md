# Smart Recipe Finder - AI Culinary Assistant 🍳

## Project Overview
Smart Recipe Finder is an intelligent, Python-based desktop application designed to help users find the optimal recipes based on the ingredients they currently have. By combining natural language processing, speech recognition, and smart ranking algorithms, the app minimizes food waste and simplifies meal planning.

## Key Features
* **Modern GUI:** Built with `customtkinter`, featuring a highly scalable, modern interface with native Dark Mode support.
* **Voice Search (Speech-to-Text):** Integrated Google Speech API with custom NLP post-processing to transform continuous speech into formatted ingredient lists (e.g., parsing "apples and sugar" into "apples, sugar").
* **Smart Ranking Algorithm:** Automatically filters and sorts recipe candidates, prioritizing them based on the ratio of owned ingredients versus missing ones.
* **Contextual Video Search:** Dynamically generates YouTube search links based on the chosen recipe's title, bypassing the limitations of the core API.
* **Robust Error Handling:** Gracefully handles invalid inputs, connection timeouts, API quota limits, and voice recognition failures.

## Tech Stack & Architecture
* **Language:** Python
* **GUI Framework:** CustomTkinter
* **APIs:** Spoonacular API, Google Speech API
* **Libraries:** `SpeechRecognition`, `PIL` (Pillow), `threading`, `re` (Regex)
* **Architecture:** Object-Oriented Programming (OOP) with a strict separation of concerns between the frontend (`RecipeApp` class) and the backend (`BackendManager` class).

## Technical Implementation Details
* **Advanced API Querying:** Utilizes a two-step fetching process. It first retrieves the top 20 candidate recipes based on the provided ingredients, then performs a deep fetch to extract complete details for the best match.
* **Input Parsing via Regex:** Implemented robust regular expressions to accurately interpret user input, regardless of whether they use commas, multiple spaces, or unstructured text.
* **Asynchronous Media Processing:** Downloads recipe images asynchronously, processing them directly from byte streams into PIL objects and resizing them dynamically without saving to disk.
* **UI Threading:** Network operations and API calls are handled on separate threads to prevent the graphical user interface from "freezing" during execution.

## End-to-End User Flow
1. **Input:** The user provides a list of ingredients via text or voice command.
2. **Processing:** The application cleans and parses the input using Regex and NLP rules.
3. **Querying:** The backend queries the Spoonacular API for potential matches.
4. **Ranking:** The local Smart Ranking algorithm evaluates candidates to find the optimal recipe.
5. **Display:** The best recipe is displayed in the UI, complete with a processed image and a dynamically generated YouTube tutorial link.
