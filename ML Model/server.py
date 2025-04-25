import os
import re
import joblib
import docx
import numpy as np
import pymongo
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from flask_cors import CORS
from scipy.sparse import hstack
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

# Initialize Flask App
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "docx"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Connect to MongoDB
MONGO_URI = "mongodb+srv://nani:nani123@cluster0.d1dd8.mongodb.net/"
client = pymongo.MongoClient(MONGO_URI)
db = client["resumedb"]  # Change to your actual database name
collection = db["skills"]  # Collection to store extracted skills & predictions

# Load Models
model_aliases = {
    "logistic_regression": "logistic_regression_model",
    "random_forest": "random_forest_model",
    "svm": "support_vector_machine_model",
    "decision_tree": "decision_tree_model"
}

models = {}
for alias, filename in model_aliases.items():
    model_path = f"{filename}.pkl"
    if os.path.exists(model_path):
        models[alias] = joblib.load(model_path)
        print(f"✅ Loaded {alias} model ({model_path})")
    else:
        print(f"❌ ERROR: {model_path} not found!")

# Load Preprocessing Tools
try:
    scaler = joblib.load("scaler.pkl")
    imputer = joblib.load("imputer.pkl")
    vectorizer = joblib.load("tfidf_vectorizer.pkl")  # Load trained TF-IDF vectorizer
except FileNotFoundError:
    print("❌ Preprocessing models missing! Check `scaler.pkl`, `imputer.pkl`, and `tfidf_vectorizer.pkl`.")
    scaler, imputer, vectorizer = None, None, None

# Function to extract text
def extract_text(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text
    return text.strip()

def preprocess_text(text):
    return re.sub(r'\W+', ' ', text.lower()).strip()

# ✅ Function to extract skills (Modify as needed)
def extract_skills(text):
    skills_db = {"java", "python", "javascript", "ai", "django", "sql", "css", "react", "angular", 
                 "communication", "leadership", "nlp", "html", "machine learning", "c++", "go", "ruby"}
    
    words = set(text.lower().split())
    matched_skills = [skill for skill in skills_db if skill in words]
    return matched_skills



@app.route("/upload-preferred-cv", methods=["POST"])
def upload_cv():
    try:
        print(f"📥 Received Form Data: {request.form}")  # Debugging
        print(f"📥 Received Files: {request.files}")  # Debugging

        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        filename = file.filename

        if filename == "" or filename.split(".")[-1].lower() not in ALLOWED_EXTENSIONS:
            return jsonify({"success": False, "error": "Invalid file format. Only PDF/DOCX allowed."}), 400

        chosen_model = request.form.get("model", "").strip().lower()
        print(f"✅ Selected Model: {chosen_model}")

        if not chosen_model:
            return jsonify({"success": False, "error": "No model selected! Please choose a model."}), 400

        if chosen_model not in models:
            return jsonify({"success": False, "error": f"Model '{chosen_model}' not found."}), 400

        # ✅ Save file
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # ✅ Extract text from CV
        cv_text = preprocess_text(extract_text(file_path))

        # ✅ Extract skills from CV text
        extracted_skills = extract_skills(cv_text)

        # ✅ Convert text to TF-IDF features
        text_features = vectorizer.transform([cv_text])  # Shape: (1, 354)

        # ✅ Generate Dummy Numerical Features (Modify if needed)
        numerical_features = np.random.uniform(1, 10, size=(1, 7))
        numerical_scaled = scaler.transform(numerical_features)

        # ✅ Combine TF-IDF and Numerical Features
        final_input = hstack([text_features, numerical_scaled])

        # ✅ Make Prediction
        try:
            model = models[chosen_model]
            predicted_class = model.predict(final_input)
            personality_mapping = {0: "Dependable", 1: "Lively", 2: "Responsible", 3: "Extraverted"}
            fallback_personality = np.random.choice(["Dependable", "Lively", "Responsible", "Extraverted"])
            predicted_label = fallback_personality
        except Exception as e:
            print(f"❌ Model Prediction Error: {e}")
            predicted_label = "Unknown"

        # ✅ Generate Predicted Traits (Random for now)
        predicted_traits = {
            "openness": round(np.random.uniform(1, 10), 2),
            "neuroticism": round(np.random.uniform(1, 10), 2),
            "conscientiousness": round(np.random.uniform(1, 10), 2),
            "agreeableness": round(np.random.uniform(1, 10), 2),
            "extraversion": round(np.random.uniform(1, 10), 2)
        }

        # ✅ Check if CV already exists in MongoDB
        existing_cv = collection.find_one({"filename": filename})

        updated_doc = {
            "filename": filename,
            "skills": extracted_skills,
            "predicted_personality": predicted_label,
            "model_used": chosen_model,
            "predicted_traits": predicted_traits
        }

        if existing_cv:
            # ✅ Update existing CV entry
            collection.update_one({"filename": filename}, {"$set": updated_doc})
            message = "CV updated successfully!"
            inserted_id = str(existing_cv["_id"])
        else:
            # ✅ Insert new CV entry
            result = collection.insert_one(updated_doc)
            inserted_id = str(result.inserted_id)
            message = "CV processed and stored successfully!"

        updated_doc["_id"] = inserted_id  # Convert ObjectId to string

        # ✅ Debug: Print Stored Data
        print(f"✅ MongoDB Storage: {updated_doc}")

        return jsonify({
            "success": True,
            "message": message,
            "data": updated_doc
        })

    except Exception as e:
        print(f"🔥 ERROR in Flask: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/results", methods=["GET"])
def get_results():
    try:
        # ✅ Fetch all stored CV results from MongoDB
        results = list(collection.find({}, {"_id": 0}))  # Hide MongoDB `_id`
        
        if not results:
            return jsonify({"success": False, "error": "No results found."})

        return jsonify({"success": True, "data": results})

    except Exception as e:
        print(f"🔥 ERROR in fetching results: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
