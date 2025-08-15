# video_recorder_final.py
import os
import cv2
import gradio as gr
import threading
import time
from datetime import datetime

# ---------- 工具 ----------
def safe_list_cameras(max_test=5):
    cams = []
    for idx in range(max_test):
        cap = cv2.VideoCapture(idx)
        if cap.read()[0]:
            cams.append(idx)
        cap.release()
    return cams if cams else [0]

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# ---------- 全局 ----------
rec = {
    "cap": None,
    "out": None,
    "running": False,
    "lock": threading.Lock(),
    "current_path": ""
}

# ---------- 帧读取 ----------
def get_frame(cam_id, mirror):
    if rec["cap"] is None or not rec["cap"].isOpened():
        rec["cap"] = cv2.VideoCapture(cam_id)
    ret, frame = rec["cap"].read()
    if not ret:
        return None
    if mirror:
        frame = cv2.flip(frame, 1)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

# ---------- 录制 ----------
def start_recording(cam_id):
    with rec["lock"]:
        if rec["running"]:
            return "已在录制", gr.update(interactive=False), gr.update(interactive=True)

        ensure_dir("VIDEO_MP4")
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        save_path = os.path.join("VIDEO_MP4", f"video_{timestamp}.mp4")
        rec["current_path"] = save_path

        if rec["cap"] is None or not rec["cap"].isOpened():
            rec["cap"] = cv2.VideoCapture(cam_id)

        w = int(rec["cap"].get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(rec["cap"].get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        rec["out"] = cv2.VideoWriter(save_path, fourcc, 25, (w, h))
        rec["running"] = True

        def write_loop():
            while True:
                with rec["lock"]:
                    if not rec["running"]:
                        break
                    ret, f = rec["cap"].read()
                    if ret and rec["out"]:
                        rec["out"].write(f)
                time.sleep(0.02)
        threading.Thread(target=write_loop, daemon=True).start()

    return f"开始录制 → {save_path}", gr.update(interactive=False), gr.update(interactive=True)

def stop_recording():
    with rec["lock"]:
        if not rec["running"]:
            return "未在录制", gr.update(interactive=True), gr.update(interactive=False)

        rec["running"] = False
        if rec["out"]:
            rec["out"].release()
            rec["out"] = None
        saved = rec["current_path"]
    return f"已保存：{saved}", gr.update(interactive=True), gr.update(interactive=False)

# ---------- Gradio UI ----------
css = """
.gradio-container{max-width:700px;margin:auto;padding-top:2em}
#preview{border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.15)}
"""

with gr.Blocks(css=css, title="简易摄像头录制器") as demo:
    gr.Markdown("## 📹 简易摄像头录制器")

    with gr.Row():
        cam_choice = gr.Dropdown(
            choices=safe_list_cameras(), value=0,
            label="选择摄像头", interactive=True
        )
        mirror = gr.Checkbox(label="镜像预览", value=False)

    preview = gr.Image(label="实时预览", elem_id="preview", height=400)

    with gr.Row():
        btn_start = gr.Button("▶️ 开始录制", variant="primary")
        btn_stop  = gr.Button("⏹️ 结束录制", interactive=False)

    status = gr.Textbox(label="状态", interactive=False, lines=2)

    # 用 Timer 实现 10 fps 预览
    timer = gr.Timer(value=0.1, active=True)
    timer.tick(
        fn=get_frame,
        inputs=[cam_choice, mirror],
        outputs=preview
    )

    btn_start.click(
        start_recording,
        inputs=[cam_choice],
        outputs=[status, btn_start, btn_stop]
    )
    btn_stop.click(
        stop_recording,
        outputs=[status, btn_start, btn_stop]
    )

if __name__ == "__main__":
    demo.launch()