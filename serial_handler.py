import threading, time, math, os
from collections import defaultdict, deque

# -- Khai báo PySerial --
pyserial = None
list_ports = None
SERIAL_ENABLED = True
try:
    import serial as pyserial
    from serial.tools import list_ports
except Exception:
    SERIAL_ENABLED = False

# -- Biến toàn cục phần cứng --
ser = None
serial_thread = None
stop_serial_thread = False

DATA_LOCK = threading.Lock()
MAX_LOCK = threading.Lock()

data_buffer = []
LAST_SESSION = []
MAX_ANGLES = {"hip": 0.0, "knee": 0.0, "ankle": 0.0}
HIP_STATE = {"mode": "front", "prev_pitch2": 0.0}
PITCH_MID = 90.0
PITCH_HYS = 10.0
HIP_CROSS_TH = 40.0
DEADZONE = 2.0

_SMOOTH_STATE = {"hip": 0.0, "knee": 0.0, "ankle": 0.0}
# Giảm alpha xuống 0.05 để chống rung "lật" quá nhanh khi mạch đo với mẫu lên đến 100Hz
_SMOOTH_ALPHA = {"hip": 0.05, "knee": 0.05, "ankle": 0.05}


def norm_deg(x: float) -> float:
    while x > 180: x -= 360
    while x < -180: x += 360
    return x


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def quaternion_to_euler(w: float, x: float, y: float, z: float):
    """
    Chuyển đổi từ góc Quaternion (w, x, y, z) sang góc Euler (Yaw, Roll, Pitch) theo độ.
    Sử dụng cho chi dưới (Hip, Knee, Ankle) với chống Gimbal Lock.
    """
    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    
    if abs(sinp) >= 0.999: # Rơi vào điểm mù Gimbal Lock (Góc Pitch = 90 độ)
        pitch = math.copysign(math.pi / 2, sinp)
        # Khi bị khóa trục, Yaw và Roll bị gộp làm 1. Gán toàn bộ góc chuyển động cho Roll (Vì UI dùng Roll tính góc chân)
        yaw = 0.0
        roll = 2 * math.atan2(x, w) if sinp > 0 else -2 * math.atan2(x, w)
    else:
        pitch = math.asin(sinp)
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(yaw), math.degrees(roll), math.degrees(pitch)


def quaternion_multiply(q1, q2):
    """Nhân hai quaternion: q1 * q2"""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    )

def quaternion_inverse(q):
    """Tính quaternion nghịch đảo"""
    w, x, y, z = q
    norm_sq = w*w + x*x + y*y + z*z
    if norm_sq == 0:
        return (1.0, 0.0, 0.0, 0.0)
    return (w/norm_sq, -x/norm_sq, -y/norm_sq, -z/norm_sq)

def compute_relative_quaternion(q_sensor, q_reference):
    """
    Tính quaternion tương đối: q_rel = (q_reference^-1) * q_sensor
    Lưu ý: Dựa trên công thức tài liệu q_{relative} = q_{IMU2} x q_{IMU1}^{-1}
    Khi đó IMU2 là phần ngoài (sensor), IMU1 là phần gốc (reference)
    """
    q_ref_inv = quaternion_inverse(q_reference)
    return quaternion_multiply(q_sensor, q_ref_inv)


# --- CÁC HÀM QUY ĐỔI QUATERNION CHO PHẦN CHI TRÊN (Dựa trên tài liệu nghiên cứu) ---

def upper_body_q_to_trunk(w: float, x: float, y: float, z: float):
    """
    Trunk w.r.t Lower Back (XYZ Sequence)
    Trả về: (theta1, theta2, theta3) = (Flexion/Extension, Lateral Flexion, Rotation)
    """
    sin_t2 = 2 * (w * y - z * x)
    if abs(sin_t2) >= 0.999:
        theta2 = math.copysign(math.pi / 2, sin_t2)
        theta1 = 2 * math.atan2(x, w) if sin_t2 > 0 else -2 * math.atan2(x, w)
        theta3 = 0.0
    else:
        theta1 = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        theta2 = math.asin(sin_t2)
        theta3 = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return math.degrees(theta1), math.degrees(theta2), math.degrees(theta3)


def upper_body_q_to_arm(w: float, x: float, y: float, z: float):
    """
    Arm w.r.t Trunk (YXZ Sequence)
    Trả về: (theta4, theta5, theta6) = (Flexion/Ext, Adduction/Abduction, Internal Rot)
    Lưu ý: YXZ thì trục giữa là X (asin), trục đầu Y (atan2), trục cuối Z (atan2)
    """
    sin_t5 = 2 * (w * x - y * z)
    if abs(sin_t5) >= 0.999:
        theta5 = math.copysign(math.pi / 2, sin_t5)
        theta4 = 2 * math.atan2(y, w) if sin_t5 > 0 else -2 * math.atan2(y, w)
        theta6 = 0.0
    else:
        theta4 = math.atan2(2 * (w * y + x * z), 1 - 2 * (x * x + y * y))
        theta5 = math.asin(sin_t5)
        theta6 = math.atan2(2 * (w * z + x * y), 1 - 2 * (x * x + z * z))
    return math.degrees(theta4), math.degrees(theta5), math.degrees(theta6)


def upper_body_q_to_forearm(w: float, x: float, y: float, z: float):
    """
    Forearm w.r.t Arm (XZY Sequence)
    Trả về: (theta7, off_axis, theta8) = (Flexion/Ext, Lỗi ngoài trục, Pronation/Supination)
    Lưu ý: XZY thì trục giữa là Z (asin), trục đầu X (atan2), trục cuối Y (atan2)
    """
    sin_z = 2 * (w * z - x * y)
    if abs(sin_z) >= 0.999:
        off_axis = math.copysign(math.pi / 2, sin_z)
        theta7 = 2 * math.atan2(x, w) if sin_z > 0 else -2 * math.atan2(x, w)
        theta8 = 0.0
    else:
        theta7 = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + z * z))
        off_axis = math.asin(sin_z)
        theta8 = math.atan2(2 * (w * y + x * z), 1 - 2 * (y * y + z * z))
    return math.degrees(theta7), math.degrees(off_axis), math.degrees(theta8)


def upper_body_q_to_hand(w: float, x: float, y: float, z: float):
    """
    Hand w.r.t Forearm (XYZ Sequence)
    Trả về: (theta9, off_axis, theta10) = (Flexion/Ext, Lỗi ngoài trục, Radial/Ulnar Deviation)
    """
    sin_y = 2 * (w * y - z * x)
    if abs(sin_y) >= 0.999:
        off_axis = math.copysign(math.pi / 2, sin_y)
        theta9 = 2 * math.atan2(x, w) if sin_y > 0 else -2 * math.atan2(x, w)
        theta10 = 0.0
    else:
        theta9 = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        off_axis = math.asin(sin_y)
        theta10 = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return math.degrees(theta9), math.degrees(off_axis), math.degrees(theta10)




def _smooth(key: str, x: float) -> float:
    a = _SMOOTH_ALPHA.get(key, 0.25)
    prev = _SMOOTH_STATE.get(key, x)
    y = a * x + (1 - a) * prev
    _SMOOTH_STATE[key] = y
    return y


def reset_max_angles():
    with MAX_LOCK:
        MAX_ANGLES["hip"] = 0.0
        MAX_ANGLES["knee"] = 0.0
        MAX_ANGLES["ankle"] = 0.0


def auto_detect_port():
    if not list_ports: return None
    ports = list(list_ports.comports())
    for p in ports:
        if any(x in (p.description or "").upper() for x in ["USB", "ACM", "CP210", "CH340", "UART", "SERIAL"]):
            return p.device
    return ports[0].device if ports else None


def parse_serial_line(line: str):
    parts = [p.strip() for p in line.strip().split(",") if p.strip() != ""]
    if not parts: return None
    tag = parts[0].upper()
    try:
        if tag == "IMU":
            # Định dạng quaternion mới (9 phần tử): IMU, id, seq, w, x, y, z, pico_ts, master_ts
            if len(parts) >= 9:
                sid = int(parts[1])
                # parts[2] là packet counter/sequence, ta bỏ qua
                w, x, y, z = float(parts[3]), float(parts[4]), float(parts[5]), float(parts[6])
                ts = int(parts[7])  # dùng pico_ts_us làm timestamp
                yaw, roll, pitch = quaternion_to_euler(w, x, y, z)
                return ("imu", sid, ts, yaw, roll, pitch, w, x, y, z)
                
            # Định dạng cũ (góc Euler tĩnh): IMU, id, ts, yaw, roll, pitch
            elif len(parts) >= 6:
                return ("imu", int(parts[1]), int(float(parts[2])), float(parts[3]), float(parts[4]), float(parts[5]))
            
        elif tag == "EMG" and len(parts) >= 4:
            return ("emg", int(parts[1]), int(float(parts[2])), float(parts[3]))
    except Exception:
        return None
    return None


def stop_serial_reader():
    global ser, serial_thread, stop_serial_thread
    stop_serial_thread = True
    try:
        if ser is not None: ser.close()
    except Exception:
        pass
    finally:
        ser = None

    if serial_thread and serial_thread.is_alive():
        try:
            serial_thread.join(timeout=1.0)
        except Exception:
            pass
    serial_thread = None
    return True


# TRUYỀN socketio VÀO ĐÂY ĐỂ TRÁNH LỖI IMPORT VÒNG TRÒN
def start_serial_reader(socketio, port=None, baud=115200):
    global ser, serial_thread, stop_serial_thread

    if not SERIAL_ENABLED or pyserial is None: return False
    if not port: port = os.environ.get("SERIAL_PORT") or auto_detect_port()
    if not port: return False

    stop_serial_reader()

    try:
        ser = pyserial.Serial(port, baud, timeout=0.5)
        ser.reset_input_buffer()
    except Exception as e:
        print("Không mở được cổng serial:", e)
        return False

    stop_serial_thread = False
    last_angles = defaultdict(lambda: {"yaw": 0.0, "roll": 0.0, "pitch": 0.0, "ts": 0.0})

    def reader_loop():
        global stop_serial_thread
        while not stop_serial_thread:
            try:
                raw = ser.readline()
                if not raw: continue
                line = raw.decode("utf-8", errors="ignore").strip()
                parsed = parse_serial_line(line)
                if not parsed: continue

                ptype = parsed[0]
                now_ms = time.time() * 1000.0

                if ptype == "imu":
                    if len(parsed) == 10: # Quaternion format (imu, sid, ts, yaw, roll, pitch, w, x, y, z)
                        _, sid, ts, yaw, roll, pitch, qw, qx, qy, qz = parsed
                        last_angles[sid] = {"yaw": yaw, "roll": roll, "pitch": pitch, "ts": ts, "q": (qw, qx, qy, qz)}
                    else: # Euler format
                        _, sid, ts, yaw, roll, pitch = parsed
                        last_angles[sid] = {"yaw": yaw, "roll": roll, "pitch": pitch, "ts": ts, "q": (1.0, 0.0, 0.0, 0.0)}

                    # ----- PHẦN CHI DƯỚI -----
                    p1 = last_angles.get(1, {}).get("pitch", 0.0)
                    p2 = last_angles.get(2, {}).get("pitch", 0.0)
                    # IMU 3 hỏng, dùng IMU 4 thay thế cho vai trò của khớp gối (p3)
                    p3 = last_angles.get(4, {}).get("pitch", 0.0) 
                    # Bàn chân (p4) cố định 90 độ để giữ song song với mặt đất
                    p4 = 90.0 
                    pitch2 = last_angles.get(2, {}).get("pitch", 0.0)

                    raw_hip = norm_deg(p1 - p2)
                    raw_knee = norm_deg(p3 - p2)
                    raw_ankle = norm_deg(p4 - p3)-90
                    hip_val = -raw_hip
                    
                    if abs(hip_val) < DEADZONE:
                        hip_val = 0.0

                    hip = _smooth("hip", clamp(hip_val, -10.0, 130.0)) 
                    knee = _smooth("knee", clamp(raw_knee, -10.0, 130.0))
                    ankle = _smooth("ankle", clamp(raw_ankle, 50.0, 110.0))

                    # ----- PHẦN CHI TRÊN (Đọc Quaternion gốc từ map) -----
                    # Giả sử thiết lập ID: LowerBack(4), Trunk(5), Arm(6), Forearm(7), Hand(8)
                    q_lowerback= last_angles.get(4, {}).get("q", (1.0, 0.0, 0.0, 0.0))
                    q_trunk   = last_angles.get(1, {}).get("q", (1.0, 0.0, 0.0, 0.0))
                    q_arm     = last_angles.get(2, {}).get("q", (1.0, 0.0, 0.0, 0.0))
                    q_forearm = last_angles.get(7, {}).get("q", (1.0, 0.0, 0.0, 0.0))
                    q_hand    = last_angles.get(8, {}).get("q", (1.0, 0.0, 0.0, 0.0))

                    # Theo Equation (4): q_relative = q_child * q_parent^(-1)
                    q_rel_trunk   = compute_relative_quaternion(q_trunk, q_lowerback)
                    q_rel_arm     = compute_relative_quaternion(q_arm, q_trunk)
                    q_rel_forearm = compute_relative_quaternion(q_forearm, q_arm)
                    q_rel_hand    = compute_relative_quaternion(q_hand, q_forearm)

                    theta1, theta2, theta3 = upper_body_q_to_trunk(*q_rel_trunk)
                    theta4, theta5, theta6 = upper_body_q_to_arm(*q_rel_arm)
                    theta7, off_axis1, theta8 = upper_body_q_to_forearm(*q_rel_forearm)
                    theta9, off_axis2, theta10 = upper_body_q_to_hand(*q_rel_hand)

                    with MAX_LOCK:
                        if hip > MAX_ANGLES["hip"]: MAX_ANGLES["hip"] = hip
                        if knee > MAX_ANGLES["knee"]: MAX_ANGLES["knee"] = knee
                        if ankle > MAX_ANGLES["ankle"]: MAX_ANGLES["ankle"] = ankle
                        max_payload = {
                            "maxHip": MAX_ANGLES["hip"],
                            "maxKnee": MAX_ANGLES["knee"],
                            "maxAnkle": MAX_ANGLES["ankle"],
                        }

                    with DATA_LOCK:
                        data_buffer.append({
                            "t_ms": now_ms, "hip": hip, "knee": knee, "ankle": ankle,
                            "upper_body": {
                                "trunk": (theta1, theta2, theta3),
                                "arm": (theta4, theta5, theta6),
                                "forearm": (theta7, theta8),
                                "hand": (theta9, theta10)
                            }
                        })
                    now_sys = time.time()
                    if now_sys - getattr(reader_loop, "last_emit", 0) > 0.033:
                        socketio.emit("imu_data", {
                            "t": now_ms, "hip": hip, "knee": knee, "ankle": ankle, 
                            "upper_body": {
                                "trunk": (theta1, theta2, theta3),
                                "arm": (theta4, theta5, theta6),
                                "forearm": (theta7, theta8),
                                "hand": (theta9, theta10)
                            },
                            **max_payload
                        })
                        reader_loop.last_emit = now_sys

            except Exception as e:
                print("Lỗi đọc serial:", e)
                if "ClearCommError" in str(e) or "Access is denied" in str(e): break

    serial_thread = threading.Thread(target=reader_loop, daemon=True)
    serial_thread.start()
    return True
