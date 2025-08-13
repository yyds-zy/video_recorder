import os
import cv2
import time
import gradio as gr
import numpy as np
from datetime import datetime
import threading

# 降低 OpenCV 日志级别，抑制索引越界等噪声
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

# 目标保存目录
SAVE_DIR = "VIDEO_MP4"
os.makedirs(SAVE_DIR, exist_ok=True)

# 全局状态
cap = None
writer = None
running = False
stop_event = threading.Event()
current_filename = None


def list_cameras(max_test: int = 3):
    cameras = []
    for i in range(max_test):
        try:
            test = cv2.VideoCapture(i)
            if test.isOpened():
                cameras.append(f"摄像头 {i}")
                test.release()
        except Exception:
            pass
    return cameras if cameras else ["摄像头 0"]


def parse_index(label_or_int):
    if isinstance(label_or_int, int):
        return label_or_int
    try:
        return int(str(label_or_int).split()[-1])
    except Exception:
        return 0


def generate_filename():
    ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    return os.path.join(SAVE_DIR, f"video_{ts}.mp4")


def start_record(camera_choice, mirror_preview):
    """
    启动预览并录制，作为生成器持续输出 (image_rgb, status_text)
    点击停止后，外部会设置 stop_event，从而结束循环
    """
    global cap, writer, running, current_filename

    if running:
        # 已在运行，直接流出画面与状态
        status = f"录制中: {os.path.basename(current_filename)}"
    else:
        # 初始化摄像头
        idx = parse_index(camera_choice)
        cap = cv2.VideoCapture(idx)
        if not cap or not cap.isOpened():
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            yield img, f"无法打开摄像头 {idx}"
            return

        # 获取尺寸与 VideoWriter
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        fps = 30.0
        current_filename = generate_filename()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(current_filename, fourcc, fps, (width, height))
        if not writer or not writer.isOpened():
            img = np.zeros((height, width, 3), dtype=np.uint8)
            yield img, "无法创建视频文件"
            cap.release()
            cap = None
            return

        running = True
        stop_event.clear()
        status = f"录制中: {os.path.basename(current_filename)}"

    # 主循环：读取帧 -> 写入 -> 显示
    while running and (cap is not None) and cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break
        # 写入原始帧（不镜像保存）
        writer.write(frame)

        # 预览镜像仅影响显示
        display = cv2.flip(frame, 1) if mirror_preview else frame
        display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        yield display_rgb, status

        # 控制输出速率（约30fps）
        time.sleep(1/30.0)

    # 停止时不在这里释放，由 stop_record 控制


def stop_record():
    """停止预览与录制，并返回 (image_rgb, status_text)"""
    global cap, writer, running, current_filename

    if not running:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        return img, "未在录制"

    stop_event.set()
    running = False

    try:
        if writer:
            writer.release()
    finally:
        writer = None

    try:
        if cap:
            cap.release()
    finally:
        cap = None

    # 返回一张黑图
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    if current_filename:
        return img, f"已保存: {os.path.basename(current_filename)}"
    else:
        return img, "已停止"


# --------------- Gradio 界面 ---------------
with gr.Blocks(css="""
    .main {max-width: 980px; margin: 0 auto;}
    .header {text-align:center; margin: 10px 0 20px;}
    .header h1 {margin: 0; font-size: 2.0em;}
    .panel {border: 1px solid #e9ecef; border-radius: 12px; padding: 16px; background: #fff;}
    .status {background:#e3f2fd; border-left:4px solid #2196f3; padding:10px 12px; border-radius:6px;}
""") as demo:
    gr.HTML("""
        <div class="main">
          <div class="header">
            <h1>🎥 视频录制软件（Gradio）</h1>
            <div style="color:#6c757d;">支持摄像头选择、实时预览（可镜像）、一键开始/结束录制，MP4 30fps</div>
          </div>
        </div>
    """)

    with gr.Row(elem_classes="main"):
        with gr.Column(scale=1):
            # 用 Dropdown 替代原 HTML 标题，仅作面板标题展示
            section_title = gr.Dropdown(choices=["🎛️ 控制"], value="🎛️ 控制", label="面板")

            camera_dd = gr.Dropdown(choices=list_cameras(), value=list_cameras()[0], label="选择摄像头")
            mirror_cb = gr.Checkbox(value=True, label="预览镜像（仅显示，不影响保存）")

            start_btn = gr.Button("🔴 开始录制（含预览）", variant="primary")
            stop_btn = gr.Button("⏹️ 结束录制（含预览）", variant="secondary")

        with gr.Column(scale=2):
            # 用 Dropdown 显示右侧预览面板标题
            preview_title = gr.Dropdown(choices=["📹 实时预览"], value="📹 实时预览", label="面板")
            preview = gr.Image(label="预览")
            status_tb = gr.Textbox(label="状态", interactive=False)

    # 事件绑定
    # 开始：返回生成器，持续更新 预览与状态
    start_btn.click(
        fn=start_record,
        inputs=[camera_dd, mirror_cb],
        outputs=[preview, status_tb]
    )

    # 结束：立即释放资源，并返回黑图与状态
    stop_btn.click(
        fn=stop_record,
        outputs=[preview, status_tb]
    )

if __name__ == "__main__":
    # 使用默认 7860 端口，避免不兼容参数
    demo.launch()
