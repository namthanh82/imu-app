import csv
import io
import logging
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for, flash
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_socketio import SocketIO
from werkzeug.security import check_password_hash, generate_password_hash

import database
import serial_handler
from database import load_records_from_file


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def load_app_env():
    """Load secrets for Flask + /api/analyze. Matches chatbot.py: root .env and imurtrack_ai/.env."""
    load_dotenv(resource_path(".env"), override=False)
    load_dotenv(resource_path(os.path.join("imurtrack_ai", ".env")), override=False)
    # Allow OPENAI_API_KEY (etc.) in .env next to ReTrack.exe without rebuilding
    if getattr(sys, "frozen", False):
        exe_env = os.path.join(os.path.dirname(sys.executable), ".env")
        if os.path.isfile(exe_env):
            load_dotenv(exe_env, override=True)


load_app_env()

app = Flask(__name__, static_folder=resource_path('static'), template_folder=resource_path('templates'))
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")

socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=10, ping_timeout=30, async_mode="threading")

# --- Xử lý Login ---
login_manager = LoginManager(app)
login_manager.login_view = "login"
_login_user = os.environ.get("LOGIN_USERNAME", "komlab")
_login_pass = os.environ.get("LOGIN_PASSWORD", "123456")
USERS = {_login_user: generate_password_hash(_login_pass)}


class User(UserMixin):
    def __init__(self, u): self.id = u


@login_manager.user_loader
def load_user(u):
    return User(u) if u in USERS else None


EXERCISE_VIDEOS = {
    "Gập khớp cổ chân": "/static/videos/knee_flexion.mp4",
    "Gập khớp gối": "/static/videos/knee_flexion.mp4",
    "Gập khớp háng": "/static/videos/hip_flexion3.mp4",
}


SESSION_CSV_HEADERS = [
    "Time(ms)",
    "ShoulderLT", "ShoulderRT",
    "ElbowLT", "ElbowRT",
    "HandLT", "HandRT",
    "TrunkLT", "TrunkRT",
    "HipLT", "HipRT",
    "KneeLT", "KneeRT",
    "AnkleLT", "AnkleRT",
    "EMG_Raw",
]


def safe_filename(value, fallback="KhachHang"):
    value = (value or fallback).strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    value = re.sub(r"\s+", "_", value).strip("._")
    return value or fallback


def session_csv_text(samples):
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(SESSION_CSV_HEADERS)
    for r in samples:
        emg_val = r.get("emg", 0.0)
        if isinstance(emg_val, dict):
            emg_val = emg_val.get("v", 0.0)
        writer.writerow([
            r.get("t_ms", r.get("t", 0)),
            r.get("shoulderLT", 0.0), r.get("shoulderRT", 0.0),
            r.get("elbowLT", 0.0), r.get("elbowRT", 0.0),
            r.get("handLT", 0.0), r.get("handRT", 0.0),
            r.get("trunkLT", 0.0), r.get("trunkRT", 0.0),
            r.get("hipLT", 0.0), r.get("hipRT", 0.0),
            r.get("kneeLT", 0.0), r.get("kneeRT", 0.0),
            r.get("ankleLT", 0.0), r.get("ankleRT", 0.0),
            emg_val,
        ])
    return si.getvalue()


def save_session_csv(samples, patient_code, folder=None, prefix="BanGhi_DoLuong"):
    folder = folder or database.EXPORT_DIR
    os.makedirs(folder, exist_ok=True)
    filename = f"{prefix}_{safe_filename(patient_code)}_{int(time.time())}.csv"
    path = os.path.abspath(os.path.join(folder, filename))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(session_csv_text(samples))
    return path, filename


def choose_output_folder(title="Chọn thư mục lưu file"):
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askdirectory(title=title) or ""
    finally:
        root.destroy()


def latest_vas_summary(patient_code):
    summary = {}
    with database.VAS_LOCK:
        rows = list(database.VAS_STORE)
    for rec in reversed(rows):
        if patient_code and rec.get("patient_code") != patient_code:
            continue
        name = rec.get("exercise_name") or rec.get("exercise_region") or "VAS"
        phase = rec.get("phase")
        if phase not in ("before", "after"):
            continue
        item = summary.setdefault(name, {"before": None, "after": None})
        if item[phase] is None:
            item[phase] = rec.get("vas")
    return summary


# ================= ROUTES GIAO DIỆN (HTML) =================
@socketio.on("connect")
def _on_connect():
    socketio.emit("imu_data", {"t": time.time() * 1000, "hipLT": 0, "kneeLT": 0, "ankleLT": 0})


@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = None
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        if u in USERS and check_password_hash(USERS[u], p):
            login_user(User(u))
            return redirect(url_for("dashboard"))
        error_message = "Sai tài khoản hoặc mật khẩu"
    return render_template("login.html", error_message=error_message)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", username=current_user.id, videos=EXERCISE_VIDEOS)


@app.get("/flaskwebgui-keep-server-alive")
def flaskwebgui_keep_server_alive():
    return ("", 204)


@app.route("/calibration")
@login_required
def calibration():
    open_guide = request.args.get("guide", "0") in ("1", "true", "yes")
    return render_template("calibration.html", username=current_user.id, open_guide=open_guide)


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json or {}
    user_query = data.get('message', '') or data.get('query', '')
    if not user_query.strip():
        return jsonify({'answer': 'Vui lòng nhập câu hỏi.'}), 400
    try:
        from imurtrack_ai.chatbot import get_answer

        answer = get_answer(user_query)
        return jsonify({'answer': answer})
    except Exception as e:
        print(f"Chatbot Error: {str(e)}")
        if "OPENAI_API_KEY" in str(e):
            answer = "Chatbot chưa được cấu hình `OPENAI_API_KEY`. Vui lòng thêm khóa OpenAI vào file `.env`, sau đó build lại hoặc chạy lại ứng dụng."
        else:
            answer = f"Chatbot AI đang gặp lỗi cấu hình hoặc kết nối: `{str(e)}`. Vui lòng kiểm tra `.env`, kết nối mạng và dữ liệu trong `imurtrack_ai/data`."
        return jsonify({'answer': answer}), 200


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """AI analysis of patient measurement data from the Charts page."""
    import openai
    data = request.json or {}
    exercise_name = data.get('exercise_name', 'Không rõ')
    patient_code  = data.get('patient_code',  'Ẩn danh')
    fma_score     = data.get('fma_score',     None)
    vas_before    = data.get('vas_before',    None)
    vas_after     = data.get('vas_after',     None)
    rom           = data.get('rom', {})   # dict: {joint_name: {min, max, range}}
    follow_up     = data.get('follow_up_question', '').strip()

    # Build ROM summary text
    rom_lines = []
    for joint, vals in (rom or {}).items():
        r = vals.get('range', 0)
        mn = vals.get('min', 0)
        mx = vals.get('max', 0)
        rom_lines.append(f"  - {joint}: Min={mn:.1f}°, Max={mx:.1f}°, Biên độ={r:.1f}°")
    rom_text = '\n'.join(rom_lines) if rom_lines else '  (Không có dữ liệu ROM)'

    vas_text = ''
    if vas_before is not None or vas_after is not None:
        vas_text = f"VAS trước tập: {vas_before if vas_before is not None else 'N/A'}/10, sau tập: {vas_after if vas_after is not None else 'N/A'}/10"
    else:
        vas_text = 'VAS: Chưa ghi nhận'

    fma_text = f"Điểm FMA bài tập: {fma_score}/2" if fma_score is not None else "FMA: Chưa có điểm"

    system_prompt = """Bạn là bác sĩ/AI chuyên phân tích lâm sàng phục hồi chức năng.
Nhiệm vụ của bạn là đọc dữ liệu từ ReTrack IMU và đưa ra **báo cáo lâm sàng chi tiết**, không trả lời chung chung.

BẮT BUỘC trả lời bằng **tiếng Việt** và theo đúng cấu trúc Markdown sau:
### 1. Tóm tắt ngắn
### 2. Phân tích chi tiết
- **Góc khớp**: nêu khớp nào bất thường, bên trái/phải, xu hướng tăng/giảm
- **ROM**: nhận xét đạt/chưa đạt mục tiêu, mức cải thiện
- **VAS**: đánh giá trước/sau, giảm đau hay tăng đau
- **EMG**: nếu có tín hiệu cơ, nhận xét mức hoạt hóa, bất đối xứng, dấu hiệu mỏi/căng
### 3. Kết luận lâm sàng
### 4. Khuyến nghị
- bài tập
- cường độ
- lưu ý an toàn
- nên theo dõi thêm chỉ số nào

Yêu cầu:
- Không viết chung chung kiểu "cần theo dõi thêm" nếu có thể suy ra cụ thể.
- Nếu thiếu dữ liệu, phải chỉ rõ thiếu ở đâu và thiếu ảnh hưởng thế nào.
- Ưu tiên nhận xét dựa trên số liệu, nêu con số khi có thể.
- Giọng chuyên nghiệp, ngắn gọn nhưng đủ chi tiết."""

    user_msg = f"""## Dữ liệu đo lường bệnh nhân

**Mã bệnh nhân:** {patient_code}
**Bài tập:** {exercise_name}
**{fma_text}**
**{vas_text}**

### Biên độ vận động (ROM) theo từng khớp:
{rom_text}
"""
    if follow_up:
        user_msg += f"\n### Câu hỏi/yêu cầu bổ sung từ người dùng:\n{follow_up}\n\nHãy bám sát toàn bộ dữ liệu bên trên và trả lời chi tiết hơn, có phân tích cụ thể từng mục." 
    else:
        user_msg += "\nDựa trên dữ liệu trên, hãy viết **báo cáo đầy đủ** gồm: tóm tắt ngắn, phân tích chi tiết (góc khớp/ROM/VAS/EMG nếu có), kết luận lâm sàng và khuyến nghị rõ ràng." 

    try:
        ai_key = os.environ.get("OPENAI_API_KEY") or ""
        if not ai_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        client = openai.OpenAI(api_key=ai_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg}
            ],
            temperature=0.5,
            max_tokens=1200
        )
        analysis = resp.choices[0].message.content
        return jsonify({'analysis': analysis})
    except Exception as e:
        print(f"Analyze Error: {e}")
        fallback = f"### KẾT LUẬN LÂM SÀNG\n\n- **Mã bệnh nhân:** {patient_code}\n- **Bài tập:** {exercise_name}\n- **FMA:** {fma_text}\n- **VAS:** {vas_text}\n\n### Nhận xét\n\n- Chưa thể gọi AI phân tích tự động do thiếu cấu hình hoặc kết nối.\n- Vui lòng kiểm tra `OPENAI_API_KEY` hoặc thử lại sau.\n- Hệ thống vẫn đã ghi nhận dữ liệu đo lường hiện có để tiếp tục đánh giá."
        return jsonify({'analysis': fallback}), 200
@app.route('/api/ask_expert', methods=['POST'])
def ask_expert():
    data = request.json
    question = data.get('question', '').strip()
    
    if question:
        # Lưu câu hỏi vào file text lưu ở thư mục gốc để chuyên gia xem
        with open("cau_hoi_cho_duyet.txt", "a", encoding="utf-8") as f:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{now}] Khách hàng hỏi: {question}\n")
            
    return jsonify({'ok': True})
@app.route("/records")
@login_required
def records():
    with database.RECORD_LOCK:
        rows = list(database.RECORD_STORE)
    rows.sort(key=lambda r: r.get("created_at_ts", 0), reverse=True)
    for r in rows:
        if "vas_summary" not in r or r["vas_summary"] is None: r["vas_summary"] = {}
    return render_template("records.html", username=current_user.id, records=rows)


@app.route("/patients/manage")
@login_required
def view_patients_manage():
    return render_template("patients_manage.html")

@app.route("/patients/new", methods=["GET", "POST"])
@login_required
def view_patients_new():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Thiếu họ tên", "danger")
            return redirect(url_for("view_patients_new"))
        code = database.gen_patient_code(full_name)
        _, raw = database.load_patients_rows()
        raw[code] = {
            "DateOfBirth": request.form.get("dob", ""),
            "Gender": "Male" if request.form.get("sex", "").lower() == "male" else "FeMale",
            "Height": request.form.get("height", ""),
            "ID": request.form.get("national_id", ""),
            "PatientCode": code,
            "Weight": request.form.get("weight", ""),
            "name": full_name
        }
        database.save_patients_data(raw)
        flash(f"Đã lưu thành công bệnh nhân {full_name} (Mã: {code})", "success")
        return redirect(url_for("dashboard"))
    return render_template("patients.html")


@app.route("/charts")
@login_required
def charts():
    patient_code = request.args.get("patient_code", "").strip()
    exercise_name = request.args.get("exercise", "").strip()

    # Lấy VAS
    vas_before = None
    vas_after = None
    region = None
    exercise_lower = exercise_name.lower()
    if "hip" in exercise_lower:
        region = "hip"
    elif "knee" in exercise_lower:
        region = "knee"
    elif "ankle" in exercise_lower:
        region = "ankle"

    with database.VAS_LOCK:
        for rec in reversed(database.VAS_STORE):
            if patient_code and rec.get("patient_code") != patient_code:
                continue
            if region and rec.get("exercise_region") != region:
                continue
            if exercise_name and rec.get("exercise_name") and rec.get("exercise_name") != exercise_name:
                continue
            ph = rec.get("phase")
            if ph == "before" and vas_before is None:
                vas_before = rec.get("vas")
            elif ph == "after" and vas_after is None:
                vas_after = rec.get("vas")
            if vas_before is not None and vas_after is not None:
                break

    if (vas_before is None or vas_after is None) and patient_code:
        with database.VAS_LOCK:
            for rec in reversed(database.VAS_STORE):
                if rec.get("patient_code") != patient_code:
                    continue
                ph = rec.get("phase")
                if ph == "before" and vas_before is None:
                    vas_before = rec.get("vas")
                elif ph == "after" and vas_after is None:
                    vas_after = rec.get("vas")
                if vas_before is not None and vas_after is not None:
                    break

    if not serial_handler.LAST_SESSION:
        return render_template("charts.html", username=current_user.id, t_ms=[], hipLT=[], hipRT=[], kneeLT=[], kneeRT=[], ankleLT=[], ankleRT=[], shoulderLT=[], shoulderRT=[], elbowLT=[], elbowRT=[], handLT=[], handRT=[], trunkLT=[], trunkRT=[], emg=[],
                               emg_rms=[], emg_env=[], patient_code=patient_code, exercise_name=exercise_name,
                               vas_before=vas_before, vas_after=vas_after)

    rows = sorted(list(serial_handler.LAST_SESSION), key=lambda x: x["t_ms"])
    t0 = rows[0]["t_ms"] if rows else 0
    t_ms = [round((r["t_ms"] - t0) / 1000.0, 3) for r in rows]

    hipLT = [r.get("hipLT", 0.0) for r in rows]
    hipRT = [r.get("hipRT", 0.0) for r in rows]
    kneeLT = [r.get("kneeLT", 0.0) for r in rows]
    kneeRT = [r.get("kneeRT", 0.0) for r in rows]
    ankleLT = [r.get("ankleLT", 0.0) for r in rows]
    ankleRT = [r.get("ankleRT", 0.0) for r in rows]
    shoulderLT = [r.get("shoulderLT", 0.0) for r in rows]
    shoulderRT = [r.get("shoulderRT", 0.0) for r in rows]
    elbowLT = [r.get("elbowLT", 0.0) for r in rows]
    elbowRT = [r.get("elbowRT", 0.0) for r in rows]
    handLT = [r.get("handLT", 0.0) for r in rows]
    handRT = [r.get("handRT", 0.0) for r in rows]
    trunkLT = [r.get("trunkLT", 0.0) for r in rows]
    trunkRT = [r.get("trunkRT", 0.0) for r in rows]
    
    # Trích xuất dữ liệu EMG để truyền sang Giao diện
    emgArr = []
    for r in rows:
        val = r.get("emg")
        if isinstance(val, dict):
            emgArr.append(float(val.get("v", 0.0)))
        else:
            emgArr.append(float(val) if val is not None else 0.0)

    # Đã thay emg=[] thành emg=emgArr
    return render_template("charts.html", username=current_user.id, t_ms=t_ms, hipLT=hipLT, hipRT=hipRT, kneeLT=kneeLT, kneeRT=kneeRT, ankleLT=ankleLT, ankleRT=ankleRT, shoulderLT=shoulderLT, shoulderRT=shoulderRT, elbowLT=elbowLT, elbowRT=elbowRT, handLT=handLT, handRT=handRT, trunkLT=trunkLT, trunkRT=trunkRT,
                           emg=emgArr, emg_rms=[], emg_env=[], patient_code=patient_code, exercise_name=exercise_name,
                           vas_before=vas_before, vas_after=vas_after)


@app.route("/charts_emg")
@login_required
def charts_emg():
    return render_template("emg_chart.html", username=current_user.id)


@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html", username=current_user.id)


# ================= ROUTES API (Xử lý Data/Hardware) =================
@app.route("/ports")
@login_required
def ports():
    _port = os.environ.get("SERIAL_PORT", "COM14")
    return jsonify(ports=[{"device": _port, "desc": f"Mạch IMU ({_port})"}])


@app.post("/session/start")
@login_required
def session_start():
    serial_handler.data_buffer = []
    serial_handler.reset_max_angles()
    if serial_handler.SERIAL_ENABLED:
        data = request.get_json(silent=True) or {}
        
        port = os.environ.get("SERIAL_PORT", "COM14")
        
        baud = int(data.get("baud") or os.environ.get("SERIAL_BAUD", "115200"))
        
        if not port:
            return jsonify(ok=False, msg="Không tìm thấy mạch IMU. Vui lòng cắm cáp USB vào máy tính!"), 400
            
        if not serial_handler.start_serial_reader(socketio, port=port, baud=baud):
            return jsonify(ok=False, msg=f"Cổng {port} đang bị nghẽn (Có thể phần mềm Arduino IDE đang mở). Hãy tắt Arduino và thử lại!"), 400
            
        return jsonify(ok=True, mode="serial", port=port, baud=baud)
        
    return jsonify(ok=True, mode="noserial")


@app.post("/session/stop")
@login_required
def session_stop():
    # 1. Tắt đọc mạch an toàn
    try:
        if serial_handler.SERIAL_ENABLED: 
            serial_handler.stop_serial_reader()
    except Exception:
        pass
    
    # 2. Hứng dữ liệu từ giao diện Dashboard gửi lên
    data = request.get_json(silent=True) or {}
    samples = data.get("samples", [])
    
    # 3. Ghi đè dữ liệu thẳng vào bộ nhớ (Đã xóa bỏ DATA_LOCK gây sập server)
    if samples:
        serial_handler.LAST_SESSION = samples
    else:
        try:
            serial_handler.LAST_SESSION = list(serial_handler.data_buffer)
        except Exception:
            serial_handler.LAST_SESSION = []
            
    # 4. Xóa bộ đệm
    try:
        serial_handler.data_buffer.clear()
    except Exception:
        pass
        
    return jsonify(ok=True, msg="Đã kết thúc phiên đo")

@app.route("/session/export_csv")
@login_required
def session_export_csv():
    patient_code = request.args.get("patient_code", "KhachHang")
    
    # Kiểm tra xem có dữ liệu không
    if not serial_handler.LAST_SESSION:
        flash("Không có dữ liệu đo lường nào để xuất CSV!", "danger")
        return redirect(url_for("charts"))

    output = session_csv_text(serial_handler.LAST_SESSION)
    
    # Đặt tên file có kèm mã bệnh nhân và thời gian để không bị trùng
    filename = f"BanGhi_DoLuong_{safe_filename(patient_code)}_{int(time.time())}.csv"

    # Trả về file cho trình duyệt tải xuống
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@app.post("/api/save_current_csv")
@login_required
def api_save_current_csv():
    data = request.get_json(silent=True) or {}
    patient_code = data.get("patient_code") or "KhachHang"
    samples = list(serial_handler.LAST_SESSION or [])
    if not samples:
        return jsonify(ok=False, msg="Không có dữ liệu đo lường nào để lưu CSV."), 400

    folder = choose_output_folder("Chọn thư mục lưu CSV")
    if not folder:
        return jsonify(ok=False, msg="Bạn đã hủy chọn thư mục."), 400

    try:
        path, filename = save_session_csv(samples, patient_code, folder=folder)
    except Exception as e:
        return jsonify(ok=False, msg=f"Không lưu được CSV: {e}"), 500
    return jsonify(ok=True, filename=filename, path=path)


@app.get("/api/patients")
@login_required
def api_patients_all():
    rows, raw = database.load_patients_rows()
    return jsonify(rows=rows, raw=raw)


@app.post("/api/patients")
@login_required
def api_patients_save():
    data = request.get_json(force=True) or {}
    code = (data.get("patient_code") or "").strip()
    full_name = (data.get("name") or "").strip()
    
    if not full_name: 
        return jsonify(ok=False, msg="Thiếu họ tên"), 400

    _, raw = database.load_patients_rows()
    if not code: 
        code = database.gen_patient_code(full_name)

    gender_input = data.get("gender", "").lower().strip()
    
    # SỬA LỖI Ở ĐÂY: Lưu đầy đủ các trường thông tin thay vì ghi đè làm mất tên
    raw[code] = {
        "PatientCode": code,
        "name": full_name,
        "ID": data.get("cccd", data.get("national_id", "")),
        "DateOfBirth": data.get("dob", ""),
        "Gender": "Male" if gender_input in ["nam", "male", "m"] else "FeMale",
        "Weight": data.get("weight", ""),
        "Height": data.get("height", "")
    }
    database.save_patients_data(raw)
    return jsonify(ok=True, patient_code=code)


@app.delete("/api/patients/<patient_code>")
@login_required
def api_patient_delete(patient_code):
    _, raw = database.load_patients_rows()
    if patient_code in raw:
        del raw[patient_code]
        database.save_patients_data(raw)
        return jsonify(ok=True)
    return jsonify(ok=False, msg="Không tìm thấy bệnh nhân"), 404


load_records_from_file()
@app.post("/api/save_record")
@login_required
def api_save_record():
    data = request.get_json(force=True) or {}
    now = datetime.now(database.VN_TZ)
    patient_code = data.get("patient_code", "")
    samples = list(serial_handler.LAST_SESSION or [])
    csv_path = ""
    csv_filename = ""
    if samples:
        try:
            csv_path, csv_filename = save_session_csv(samples, patient_code or "KhachHang")
        except Exception as e:
            print("[WARN] save session csv error:", e)
    record = {
        "created_at_ts": now.timestamp(),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "patient_code": patient_code,
        "measure_date": data.get("measure_date", ""),
        "patient_info": data.get("patient_info", {}),
        "exercise_scores": data.get("exercise_scores", {}),
        "vas_summary": latest_vas_summary(patient_code),
        "csv_path": csv_path,
        "csv_filename": csv_filename
    }
    with database.RECORD_LOCK:
        database.RECORD_STORE.append(record)
        database.save_records_to_file()
    return jsonify(ok=True, msg="saved", record=record)


@app.post("/api/export_record_report")
@login_required
def api_export_record_report():
    data = request.get_json(silent=True) or {}
    created_at_ts = str(data.get("created_at_ts", "")).strip()
    record = None
    with database.RECORD_LOCK:
        for candidate in database.RECORD_STORE:
            if str(candidate.get("created_at_ts", "")) == created_at_ts:
                record = dict(candidate)
                break
    if not record:
        return jsonify(ok=False, msg="Không tìm thấy bệnh án."), 404

    folder = choose_output_folder("Chọn thư mục lưu báo cáo")
    if not folder:
        return jsonify(ok=False, msg="Bạn đã hủy chọn thư mục."), 400

    info = record.get("patient_info") or {}
    patient_code = record.get("patient_code") or info.get("patient_code") or "KhachHang"
    filename = f"BaoCao_{safe_filename(patient_code)}_{int(time.time())}.csv"
    path = os.path.abspath(os.path.join(folder, filename))

    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["RETRACK REPORT"])
            writer.writerow(["Thời gian lưu", record.get("created_at", "")])
            writer.writerow(["Ngày đo", record.get("measure_date", "")])
            writer.writerow([])
            writer.writerow(["THÔNG TIN BỆNH NHÂN"])
            writer.writerow(["Mã BN", patient_code])
            writer.writerow(["Họ và tên", info.get("name", "")])
            writer.writerow(["CCCD", info.get("cccd", "")])
            writer.writerow(["Ngày sinh", info.get("dob", "")])
            writer.writerow(["Giới tính", info.get("gender", "")])
            writer.writerow(["Cân nặng", info.get("weight", "")])
            writer.writerow(["Chiều cao", info.get("height", "")])
            writer.writerow([])
            writer.writerow(["BÀI TẬP", "ROM Knee", "Điểm"])
            for name, score in (record.get("exercise_scores") or {}).items():
                writer.writerow([name, score.get("romKnee", ""), score.get("score", "")])
            writer.writerow([])
            writer.writerow(["VAS", "Trước", "Sau"])
            for name, vas in (record.get("vas_summary") or {}).items():
                writer.writerow([name, vas.get("before", ""), vas.get("after", "")])
            writer.writerow([])
            writer.writerow(["DỮ LIỆU ĐO LƯỜNG"])

            csv_path = record.get("csv_path") or ""
            if csv_path and os.path.exists(csv_path):
                with open(csv_path, "r", encoding="utf-8-sig", newline="") as src:
                    for row in csv.reader(src):
                        writer.writerow(row)
            elif serial_handler.LAST_SESSION:
                for row in csv.reader(io.StringIO(session_csv_text(serial_handler.LAST_SESSION))):
                    writer.writerow(row)
            else:
                writer.writerow(["Không có dữ liệu đo lường CSV cho bệnh án này."])
    except Exception as e:
        return jsonify(ok=False, msg=f"Không lưu được báo cáo: {e}"), 500

    return jsonify(ok=True, filename=filename, path=path)


@app.post("/api/delete_record")
@login_required
def api_delete_record():
    data = request.get_json(silent=True) or {}
    idx = data.get("index")
    with database.RECORD_LOCK:
        if idx is not None and 0 <= idx < len(database.RECORD_STORE):
            database.RECORD_STORE.pop(idx)
            database.save_records_to_file()
            return jsonify(ok=True)
    return jsonify(ok=False, msg="Index không hợp lệ"), 400


@app.post("/save_vas")
def save_vas():
    data = request.get_json(silent=True) or {}
    rec = {
        "patient_code": data.get("patient_code"),
        "exercise_name": data.get("exercise_name"),
        "exercise_region": data.get("exercise_region"),
        "phase": data.get("phase"),
        "vas": float(data.get("vas", 0)),
        "ts": time.time(),
    }
    with database.VAS_LOCK:
        database.VAS_STORE.append(rec)
    return jsonify(ok=True)


def start_server(port=None):
    port = int(port or os.environ.get("PORT", 5000))
    socketio.run(app, host='127.0.0.1', port=port, debug=False, allow_unsafe_werkzeug=True, use_reloader=False)


def wait_for_server(port, timeout=20):
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/login"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def run_desktop_app():
    import webview

    load_records_from_file()
    port = 5000
    print(f"Starting desktop app on port {port}...")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    server_thread = threading.Thread(target=start_server, kwargs={"port": port}, daemon=True)
    server_thread.start()
    wait_for_server(port)

    webview.create_window(
        "ReTrack",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        min_size=(1024, 700),
    )
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    run_desktop_app()