import pandas as pd
import numpy as np
import re
import joblib
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE
from scipy.sparse import hstack

# **Step 1: Load Data**
file_path = "training_dataset.csv"  
df = pd.read_csv(file_path)

# **Step 2: Data Preprocessing**
df.columns = df.columns.str.strip()  # Clean column names

# Define feature columns (numerical personality traits)
features = ["Gender", "Age", "Openness", "Neuroticism", "Conscientiousness", "Agreeableness", "Extraversion"]

# Convert gender to numeric
df["Gender"] = df["Gender"].map({"Male": 1, "Female": 0})

# Convert features to numeric values
df[features] = df[features].apply(pd.to_numeric, errors="coerce")

# Handle missing values using median imputation
imputer = SimpleImputer(strategy="median")
df[features] = imputer.fit_transform(df[features])

# Encode personality class labels
label_encoder = LabelEncoder()
df["Personality (Class label)"] = label_encoder.fit_transform(df["Personality (Class label)"])

# **Fix: Ensure Class Labels are Sequential**
unique_classes = sorted(df["Personality (Class label)"].unique())
class_mapping = {old_label: new_label for new_label, old_label in enumerate(unique_classes)}
df["Personality (Class label)"] = df["Personality (Class label)"].map(class_mapping)

# **Remove Classes with Fewer than 2 Samples**
class_counts = df["Personality (Class label)"].value_counts()
df = df[df["Personality (Class label)"].isin(class_counts[class_counts > 1].index)]

# **Step 3: TF-IDF Vectorization for Resume Text**
if "CV_Text" in df.columns:
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    X_text = vectorizer.fit_transform(df["CV_Text"].fillna(""))  
else:
    raise ValueError("Missing 'CV_Text' column in dataset!")

# **Step 4: Combine TF-IDF with Numerical Features**
X_numerical = df[features]  
scaler = StandardScaler()
X_numerical_scaled = scaler.fit_transform(X_numerical)

X_final = hstack([X_text, X_numerical_scaled])  

# Define target variable
y = df["Personality (Class label)"]

# **Step 5: Train-Test Split**
X_train, X_test, y_train, y_test = train_test_split(X_final, y, test_size=0.3, random_state=42, stratify=y)

# **Apply SMOTE to Balance Classes**
smote = SMOTE(sampling_strategy="auto", random_state=42)
X_train, y_train = smote.fit_resample(X_train, y_train)

# **Step 6: Define & Train ML Models**
models = {
    "Logistic Regression": LogisticRegression(class_weight="balanced", max_iter=1000, solver="saga"),
    "Random Forest": RandomForestClassifier(n_estimators=500, max_depth=30, random_state=42),
    "Support Vector Machine": SVC(kernel="linear", probability=True, random_state=42),
    "Decision Tree": DecisionTreeClassifier(max_depth=30, random_state=42),
}

best_model = None
best_accuracy = 0

for name, model in models.items():
    print(f"\n🔹 Training {name}...")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"✅ {name} Accuracy: {accuracy:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        best_model = model

    joblib.dump(model, f"{name.replace(' ', '_').lower()}_model.pkl")

# **Step 7: Save Preprocessing Tools**
joblib.dump(scaler, "scaler.pkl")
joblib.dump(imputer, "imputer.pkl")
joblib.dump(vectorizer, "tfidf_vectorizer.pkl")
joblib.dump(label_encoder, "label_encoder.pkl")

print("\n🎯 Best Model:", type(best_model).__name__, "with Accuracy:", round(best_accuracy * 100, 2), "%")
print("✅ Optimized models and preprocessing tools saved successfully!")
