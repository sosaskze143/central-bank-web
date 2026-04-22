import os
import random
import string
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, flash
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "secret_central_bank_key_123"

# --- 1. إعداد FIREBASE (يدعم الاستضافة والجهاز المحلي) ---
def initialize_firebase():
    # محاولة القراءة من Render (السر الذي وضعناه)
    firebase_json = os.environ.get('FIREBASE_JSON')
    
    try:
        if firebase_json:
            # إذا كنا على Render
            key_dict = json.loads(firebase_json)
            cred = credentials.Certificate(key_dict)
        else:
            # إذا كنا نشتغل محلياً على الجهاز
            cred = credentials.Certificate("firebase_key.json")
        
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Firebase Initialization Error: {e}")
        return None

db = initialize_firebase()

# --- 2. إعداد GEMINI API ---
API_KEY = "AIzaSyDKo86mLaLYLQox20QvM3gM2BtiPN8H9go"
genai.configure(api_key=API_KEY)

def extract_with_fallback(file_bytes, mime_type):
    # ترتيب الموديلات للتنقل بينها في حال الفشل
    models = ["gemini-1.5-flash", "gemini-2.0-flash"]
    
    prompt = """
    Extract the following data from the document:
    1. Full Name (الاسم الرباعي)
    2. National ID (رقم الهوية)
    3. Registration Number (رقم التسجيل) - MUST BE CASE SENSITIVE.
    
    Return ONLY a valid JSON: {"name": "...", "id": "...", "reg": "..."}
    """
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([
                prompt,
                {'mime_type': mime_type, 'data': file_bytes}
            ])
            # تنظيف النص المستخرج لضمان أنه JSON نقي
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    return None

# --- 3. المسارات (Routes) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        flash("لم يتم اختيار ملف")
        return redirect(url_for('index'))
        
    file = request.files.get('file')
    if file.filename == '':
        flash("اسم الملف فارغ")
        return redirect(url_for('index'))

    # استخراج البيانات باستخدام الذكاء الاصطناعي
    try:
        file_bytes = file.read()
        extracted = extract_with_fallback(file_bytes, file.content_type)
    except Exception as e:
        flash("حدث خطأ أثناء معالجة الملف")
        return redirect(url_for('index'))

    if not extracted:
        flash("فشل في استخراج البيانات. تأكد من وضوح الصورة.")
        return redirect(url_for('index'))

    # تنظيف البيانات المدخلة
    u_id = str(extracted.get('id', '')).strip()
    u_name = str(extracted.get('name', '')).strip()
    u_reg = str(extracted.get('reg', '')).strip()

    if not u_id or not db:
        flash("بيانات غير مكتملة أو فشل الاتصال بقاعدة البيانات")
        return redirect(url_for('index'))

    # منطق الحالات الثلاث
    user_ref = db.collection('users').document(u_id)
    doc = user_ref.get()

    if doc.exists:
        stored_data = doc.to_dict()
        # الحالة 2 و 3: التحقق الصارم (حساس لحالة الأحرف)
        if stored_data.get('name') == u_name and stored_data.get('reg') == u_reg:
            # نجاح الدخول
            return render_template('dashboard.html', user=stored_data)
        else:
            # خطأ في البيانات (الاسم أو رقم التسجيل غلط)
            flash("خطأ في البيانات الموحدة. يرجى مراجعة الإدارة.")
            return redirect(url_for('index'))
    else:
        # الحالة 1: تسجيل مستخدم جديد لأول مرة
        iban = "ZH" + ''.join(random.choices(string.digits, k=15))
        acc = "ACC" + ''.join(random.choices(string.digits, k=9))
        
        new_user = {
            "name": u_name,
            "id": u_id,
            "reg": u_reg,
            "iban": iban,
            "acc": acc
        }
        user_ref.set(new_user)
        return render_template('dashboard.html', user=new_user)

if __name__ == '__main__':
    # لتشغيله محلياً
    app.run(host='0.0.0.0', port=5000, debug=True)