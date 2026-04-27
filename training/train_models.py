import pandas as pd
import pickle
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.feature_extraction import extract_features

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from xgboost import XGBClassifier

# ---------------- PATH ----------------
base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base_dir)

dataset_path = os.path.join(project_root, "real_dataset.csv")
model_dir = os.path.join(project_root, "model")
os.makedirs(model_dir, exist_ok=True)

print("📂 Dataset:", dataset_path)

# ---------------- LOAD DATA ----------------
data = pd.read_csv(dataset_path)

# CLEAN
data = data.dropna()
data = data[data['url'].astype(str).str.startswith("http")]

# ---------------- FEATURE EXTRACTION ----------------
print("\n⚙️ Extracting Features...")

X = data['url'].apply(lambda x: extract_features(str(x)))
X = pd.DataFrame(X.tolist()).fillna(0)

y = data['label']

# SAVE FEATURE NAMES
pickle.dump(X.columns.tolist(), open(os.path.join(model_dir, "feature_names.pkl"), "wb"))

# ---------------- SPLIT ----------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ---------------- MODELS ----------------
models = {
    "RandomForest": RandomForestClassifier(n_estimators=300, max_depth=25, n_jobs=-1),

    "LogisticRegression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000))
    ]),

    "SVM": Pipeline([
        ("scaler", StandardScaler()),
        ("model", SVC(probability=True))
    ]),

    "DecisionTree": DecisionTreeClassifier(max_depth=25),

    "XGBoost": XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        eval_metric='logloss',
        n_jobs=-1
    )
}

# ---------------- TRAIN + EVALUATE ----------------
results = []
trained_models = {}

print("\n🚀 Training Models...\n")

for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"✅ {name}")
    print(f"   Accuracy : {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall   : {rec:.4f}")
    print(f"   F1 Score : {f1:.4f}\n")

    pickle.dump(model, open(os.path.join(model_dir, f"{name}.pkl"), "wb"))

    trained_models[name] = model

    results.append({
        "Model": name,
        "Accuracy": acc,
        "Precision": prec,
        "Recall": rec,
        "F1 Score": f1
    })

# ---------------- COMPARISON TABLE ----------------
df = pd.DataFrame(results)
df_sorted = df.sort_values(by="F1 Score", ascending=False)

print("\n📊 MODEL COMPARISON TABLE:\n")
print(df_sorted.to_string(index=False))

# ---------------- PAIRWISE COMPARISON ----------------
print("\n🔹 Pairwise Comparison:\n")

for i in range(len(df_sorted) - 1):
    m1 = df_sorted.iloc[i]
    m2 = df_sorted.iloc[i + 1]

    print(f"➡ {m1['Model']} vs {m2['Model']}")

    if m1["F1 Score"] > m2["F1 Score"]:
        winner = m1["Model"]
        reason = "Higher F1 Score"
    elif m1["F1 Score"] < m2["F1 Score"]:
        winner = m2["Model"]
        reason = "Higher F1 Score"
    else:
        if m1["Accuracy"] > m2["Accuracy"]:
            winner = m1["Model"]
            reason = "Same F1 → Higher Accuracy"
        else:
            winner = m2["Model"]
            reason = "Same F1 → Higher Accuracy"

    print(f"🏆 Winner: {winner}")
    print(f"📌 Reason: {reason}")
    print("-"*40)

# ---------------- BEST MODEL ----------------
best_row = df_sorted.iloc[0]
best_model_name = best_row["Model"]
best_model_score = best_row["F1 Score"]

print("\n🥇 BEST SINGLE MODEL:")
print(f"👉 {best_model_name} (F1: {best_model_score:.4f})")

# ---------------- ENSEMBLE ----------------
print("\n🚀 Training Ensemble Model...\n")

ensemble = VotingClassifier(
    estimators=[
        ('rf', trained_models["RandomForest"]),
        ('xgb', trained_models["XGBoost"]),
        ('lr', trained_models["LogisticRegression"])
    ],
    voting='soft'
)

ensemble.fit(X_train, y_train)
y_pred = ensemble.predict(X_test)

ens_acc = accuracy_score(y_test, y_pred)
ens_prec = precision_score(y_test, y_pred)
ens_rec = recall_score(y_test, y_pred)
ens_f1 = f1_score(y_test, y_pred)

print("\n🔥 ENSEMBLE PERFORMANCE:")
print(f"Accuracy : {ens_acc:.4f}")
print(f"Precision: {ens_prec:.4f}")
print(f"Recall   : {ens_rec:.4f}")
print(f"F1 Score : {ens_f1:.4f}")

# ---------------- FINAL DECISION ----------------
print("\n⚖️ FINAL DECISION:")

if ens_f1 > best_model_score:
    final_model = "Ensemble"
    final_obj = ensemble
    final_score = ens_f1
    reason = "Better than all models"
else:
    final_model = best_model_name
    final_obj = trained_models[best_model_name]
    final_score = best_model_score
    reason = "Best individual model"

print(f"\n🏆 FINAL MODEL: {final_model}")
print(f"📊 Final F1 Score: {final_score:.4f}")
print(f"📌 Reason: {reason}")

# ---------------- SAVE ----------------
pickle.dump(final_obj, open(os.path.join(model_dir, "best_model.pkl"), "wb"))

print("\n✅ FINAL MODEL SAVED → best_model.pkl")