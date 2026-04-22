import os
import random
import string
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, flash

# تأكد من تثبيت المكتبات: pip install google-generativeai flask firebase-admin
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "secret_central_bank_key_123"

# --- 1. إعداد FIREBASE ---
# تأكد من وجود ملف firebase_key.json في نفس المجلد
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Firebase Error: {e}")

# --- 2. إعداد GEMINI API ---
API_KEY = "AIzaSyDKo86mLaLYLQox20QvM3gM2BtiPN8H9go"
genai.configure(api_key=API_KEY)

def extract_with_fallback(file_bytes, mime_type):
    # الموديلات المطلوبة
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    prompt = """
    Extract: 1. Full Name, 2. National ID, 3. Registration Number (Exactly as written).
    Return ONLY JSON: {"name": "...", "id": "...", "reg": "..."}
    """
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, {'mime_type': mime_type, 'data': file_bytes}])
            return json.loads(response.text.replace("```json", "").replace("```", "").strip())
        except:
            continue
    return None

# --- 3. المسارات (Routes) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('file')
    if not file:
        flash("يرجى اختيار ملف")
        return redirect(url_for('index'))

    # استخراج البيانات
    extracted = extract_with_fallback(file.read(), file.content_type)
    if not extracted:
        flash("فشل في استخراج البيانات من الملف")
        return redirect(url_for('index'))

    u_id = str(extracted.get('id')).strip()
    u_name = str(extracted.get('name')).strip()
    u_reg = str(extracted.get('reg')).strip()

    user_ref = db.collection('users').document(u_id)
    doc = user_ref.get()

    if doc.exists:
        data = doc.to_dict()
        # الحالة 2 و 3: التحقق الصارم (Case Sensitive)
        if data['name'] == u_name and data['reg'] == u_reg:
            return render_template('dashboard.html', user=data)
        else:
            # خطأ في البيانات (لا نوضح ما هو الخطأ للأمان)
            flash("خطأ في البيانات الموحدة. يرجى مراجعة الإدارة.")
            return redirect(url_for('index'))
    else:
        # الحالة 1: تسجيل جديد
        iban = "ZH" + ''.join(random.choices(string.digits, k=15))
        acc = "ACC" + ''.join(random.choices(string.digits, k=9))
        new_user = {"name": u_name, "id": u_id, "reg": u_reg, "iban": iban, "acc": acc}
        user_ref.set(new_user)
        return render_template('dashboard.html', user=new_user)

if __name__ == '__main__':
    app.run(debug=True)