"""Giao diện điều khiển dự án nhận diện ô đỗ xe."""
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


BASE_DIR = Path(__file__).resolve().parent


class ParkingApp:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.events = queue.Queue()
        self.closing = False
        self.stop_requested = False

        root.title("Quản lý ô đỗ xe — YOLO")

        self.source_type = tk.StringVar(value="video")
        self.video = tk.StringVar()
        self.slots = tk.StringVar(
            value=str(BASE_DIR / "parking_slots.json")
        )
        self.model = tk.StringVar(value="yolo26n.pt")
        self.confidence = tk.StringVar(value="0.15")
        self.overlap = tk.StringVar(value="0.35")
        self.occupied_delay = tk.StringVar(value="3")
        self.free_delay = tk.StringVar(value="2")
        self.status = tk.StringVar(value="Sẵn sàng")

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll_events)

    def build_ui(self):
        self.root.geometry("800x560")
        self.root.minsize(720, 520)
        style = ttk.Style(self.root)
        style.configure("TButton", padding=(10, 6))
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Quản lý ô đỗ xe", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Chọn nguồn hình ảnh, cấu hình ô đỗ và bắt đầu nhận diện.").pack(anchor="w", pady=(3, 14))

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        home = ttk.Frame(self.tabs, padding=14)
        settings = ttk.Frame(self.tabs, padding=14)
        logs = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(home, text="  Sử dụng  ")
        self.tabs.add(settings, text="  Thiết lập nhận diện  ")
        self.tabs.add(logs, text="  Thông báo  ")
        self.log_tab = logs
        home.columnconfigure(0, weight=1)

        modes = ttk.Frame(home)
        modes.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for text, value in (("Video", "video"), ("Camera", "camera")):
            ttk.Radiobutton(modes, text=text, variable=self.source_type,
                            value=value, command=self.update_source_ui).pack(side="left", padx=(0, 20))

        self.video_row = ttk.Frame(home)
        self.video_row.grid(row=1, column=0, sticky="ew")
        self.video_row.columnconfigure(0, weight=1)
        ttk.Entry(self.video_row, textvariable=self.video).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(self.video_row, text="Chọn video…", command=self.choose_video).grid(row=0, column=1)

        self.camera_row = ttk.Frame(home)
        self.camera_row.grid(row=1, column=0, sticky="ew")
        self.camera_row.columnconfigure(0, weight=1)
        self.camera_choices = {}
        self.camera_label = tk.StringVar()
        self.camera_scanning = False
        self.camera_combo = ttk.Combobox(self.camera_row, textvariable=self.camera_label, state="readonly")
        self.camera_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.refresh_button = ttk.Button(self.camera_row, text="Làm mới", command=self.refresh_cameras)
        self.refresh_button.grid(row=0, column=1)
        self.camera_hint = tk.StringVar(value="Chọn Camera để tìm thiết bị đang kết nối.")
        ttk.Label(self.camera_row, textvariable=self.camera_hint).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.camera_row.grid_remove()

        slots = ttk.LabelFrame(home, text="Cấu hình ô đỗ", padding=10)
        slots.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        slots.columnconfigure(0, weight=1)
        ttk.Entry(slots, textvariable=self.slots).grid(row=0, column=0, sticky="ew", columnspan=3, pady=(0, 8))
        ttk.Button(slots, text="Mở JSON…", command=self.choose_slots).grid(row=1, column=0, sticky="w")
        ttk.Button(slots, text="Tạo mới…", command=self.new_slots).grid(row=1, column=1, padx=8)
        self.draw_button = ttk.Button(slots, text="Vẽ / sửa ô đỗ", command=self.start_editor)
        self.draw_button.grid(row=1, column=2)
        ttk.Label(home, text="Khi vẽ: Enter thêm ô • S lưu • Q thoát.\nĐổi video hoặc góc camera: dùng cấu hình ô đỗ tương ứng.",
                  wraplength=650).grid(row=3, column=0, sticky="w", pady=(10, 0))

        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="Mô hình YOLO").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Combobox(settings, textvariable=self.model, values=("yolo26n.pt", "yolo26s.pt")).grid(row=0, column=1, sticky="ew", padx=12)
        ttk.Button(settings, text="Chọn model…", command=self.choose_model).grid(row=0, column=2)
        fields = [("Ngưỡng tin cậy (0–1)", self.confidence),
                  ("Tỉ lệ phủ ô (0–1)", self.overlap),
                  ("Xác nhận có xe (giây)", self.occupied_delay),
                  ("Xác nhận ô trống (giây)", self.free_delay)]
        for row, (label, variable) in enumerate(fields, 1):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", pady=8)
            ttk.Entry(settings, textvariable=variable, width=14).grid(row=row, column=1, sticky="w", padx=12)
        ttk.Label(settings, text="Các giá trị mặc định phù hợp để bắt đầu. Dùng dấu chấm cho số thập phân.",
                  wraplength=640).grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 0))

        self.log = ScrolledText(logs, height=8, font=("Consolas", 10), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(14, 0))
        self.start_button = ttk.Button(controls, text="Bắt đầu nhận diện", command=self.start_detection)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="Dừng", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Label(controls, textvariable=self.status).pack(side="right")
        self.write_log("Chọn nguồn → vẽ và lưu ô đỗ → bắt đầu nhận diện. Nhấn Q trong cửa sổ OpenCV để kết thúc.")

    def update_source_ui(self):
        if self.source_type.get() == "camera":
            self.video_row.grid_remove()
            self.camera_row.grid()
            if not self.camera_choices and not self.camera_scanning:
                self.refresh_cameras()
        else:
            self.camera_row.grid_remove()
            self.video_row.grid()

    def refresh_cameras(self):
        if self.camera_scanning or self.is_running():
            return
        self.camera_scanning = True
        self.refresh_button.configure(state="disabled")
        self.camera_hint.set("Đang tìm camera, vui lòng chờ…")
        threading.Thread(target=self.scan_cameras, daemon=True).start()

    def scan_cameras(self):
        # Không truy cập Tkinter từ luồng dò thiết bị.
        try:
            import cv2
            found = []
            for index in range(21):
                capture = cv2.VideoCapture(index)
                try:
                    if capture.isOpened():
                        ok, frame = capture.read()
                        if ok and frame is not None:
                            found.append(index)
                finally:
                    capture.release()
            self.events.put(("cameras", (found, None)))
        except Exception as error:
            self.events.put(("cameras", ([], str(error))))

    def apply_cameras(self, result):
        found, error = result
        previous = self.camera_choices.get(self.camera_label.get())
        self.camera_choices = {f"Camera {index + 1} (ID {index})": str(index) for index in found}
        self.camera_combo.configure(values=tuple(self.camera_choices))
        selection = next((label for label, index in self.camera_choices.items() if index == previous),
                         next(iter(self.camera_choices), ""))
        self.camera_label.set(selection)
        self.camera_scanning = False
        self.refresh_button.configure(state="disabled" if self.is_running() else "normal")
        if error:
            self.camera_hint.set("Không thể tìm camera. Xem tab Thông báo.")
            self.write_log(f"Lỗi tìm camera: {error}")
        elif found:
            self.camera_hint.set(f"Tìm thấy {len(found)} camera. Chọn thiết bị muốn sử dụng.")
        else:
            self.camera_hint.set("Không tìm thấy camera. Kiểm tra kết nối, quyền camera rồi nhấn Tìm lại.")

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def choose_video(self):
        path = filedialog.askopenfilename(
            title="Chọn video bãi xe",
            filetypes=[
                ("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"),
                ("Tất cả tệp", "*.*"),
            ],
        )
        if path:
            self.video.set(path)
            self.source_type.set("video")
            self.update_source_ui()

    def choose_slots(self):
        path = filedialog.askopenfilename(
            title="Mở cấu hình ô đỗ",
            initialdir=str(BASE_DIR),
            filetypes=[("Cấu hình JSON", "*.json")],
        )
        if path:
            self.slots.set(path)

    def new_slots(self):
        path = filedialog.asksaveasfilename(
            title="Chọn nơi lưu cấu hình ô đỗ",
            initialdir=str(BASE_DIR),
            initialfile="parking_slots_moi.json",
            defaultextension=".json",
            filetypes=[("Cấu hình JSON", "*.json")],
        )
        if path:
            self.slots.set(path)

    def choose_model(self):
        path = filedialog.askopenfilename(
            title="Chọn mô hình YOLO",
            initialdir=str(BASE_DIR),
            filetypes=[
                ("Trọng số PyTorch", "*.pt"),
                ("Tất cả tệp", "*.*"),
            ],
        )
        if path:
            self.model.set(path)

    def get_source(self):
        if self.source_type.get() == "camera":
            if self.camera_scanning:
                raise ValueError("Đang tìm camera. Vui lòng chờ tìm xong.")
            index = self.camera_choices.get(self.camera_label.get())
            if index is None:
                raise ValueError("Chưa chọn camera. Hãy kết nối camera và nhấn Tìm lại.")
            return index

        value = self.video.get().strip()
        if not value:
            raise ValueError("Bạn chưa chọn video.")

        path = Path(value)
        if not path.is_file():
            raise ValueError("Không tìm thấy video đã chọn.")

        return str(path.resolve())

    def get_slots_path(self):
        value = self.slots.get().strip()
        if not value:
            raise ValueError("Bạn chưa chọn tệp cấu hình ô đỗ.")

        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path

        return path.resolve()

    def is_running(self):
        # Chờ cả thông báo hoàn tất trước khi cho chạy lần mới.
        return self.process is not None

    def start_editor(self):
        if self.is_running():
            return
        if self.camera_scanning:
            messagebox.showinfo("Đang tìm camera", "Vui lòng chờ tìm camera xong trước khi chạy.")
            return

        try:
            source = self.get_source()
            slots_path = self.get_slots_path()
        except ValueError as error:
            messagebox.showerror("Thiếu thông tin", str(error))
            return

        self.launch(
            "parking_draw.py",
            [source, "--output", str(slots_path)],
            "Đang vẽ ô đỗ",
        )

    def start_detection(self):
        if self.is_running():
            return
        if self.camera_scanning:
            messagebox.showinfo("Đang tìm camera", "Vui lòng chờ tìm camera xong trước khi chạy.")
            return

        try:
            source = self.get_source()
            slots_path = self.get_slots_path()

            if not slots_path.is_file():
                raise ValueError(
                    "Chưa có tệp cấu hình. "
                    "Hãy vẽ ô đỗ và nhấn S để lưu trước."
                )

            model = self.model.get().strip()
            if not model:
                raise ValueError("Bạn chưa chọn model.")

            try:
                confidence = float(self.confidence.get())
                overlap = float(self.overlap.get())
                occupied = float(self.occupied_delay.get())
                free = float(self.free_delay.get())
            except ValueError:
                raise ValueError(
                    "Các tham số phải là số. "
                    "Dùng dấu chấm cho phần thập phân."
                )

            if not 0 < confidence <= 1:
                raise ValueError(
                    "Ngưỡng tin cậy phải lớn hơn 0 và tối đa 1."
                )
            if not 0 < overlap <= 1:
                raise ValueError(
                    "Tỷ lệ phủ ô phải lớn hơn 0 và tối đa 1."
                )

            # Loại cả giá trị NaN và vô cực.
            import math
            if (
                not math.isfinite(occupied)
                or not math.isfinite(free)
                or occupied < 0
                or free < 0
            ):
                raise ValueError(
                    "Thời gian xác nhận phải là số hữu hạn không âm."
                )

        except ValueError as error:
            messagebox.showerror("Kiểm tra thông tin", str(error))
            return

        self.launch(
            "main.py",
            [
                "--source", source,
                "--slots", str(slots_path),
                "--model", model,
                "--confidence", str(confidence),
                "--overlap", str(overlap),
                "--occupied-delay", str(occupied),
                "--free-delay", str(free),
            ],
            "Đang nhận diện",
        )

    def launch(self, script_name, arguments, status):
        script = BASE_DIR / script_name
        if not script.is_file():
            messagebox.showerror(
                "Thiếu tệp",
                f"Không tìm thấy:\n{script}\n\n"
                "Đặt app.py cùng thư mục với các tệp Python.",
            )
            return

        # Dùng cùng Python đang chạy giao diện.
        python_exe = Path(sys.executable)
        if python_exe.name.lower() == "pythonw.exe":
            console_python = python_exe.with_name("python.exe")
            if console_python.exists():
                python_exe = console_python

        command = [
            str(python_exe), "-u", "-X", "utf8",
            str(script), *arguments,
        ]

        options = {}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **options,
            )
        except OSError as error:
            messagebox.showerror(
                "Không chạy được chương trình", str(error)
            )
            return

        self.process = process
        self.stop_requested = False
        self.status.set(status)
        self.draw_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.refresh_button.configure(state="disabled")
        self.write_log(f"\n--- {status} ---")

        threading.Thread(
            target=self.read_output,
            args=(process,),
            daemon=True,
        ).start()

    def read_output(self, process):
        # Luồng phụ chỉ gửi dữ liệu; không sửa giao diện Tkinter.
        try:
            for line in process.stdout:
                self.events.put(("log", line.rstrip()))
        finally:
            process.stdout.close()
            code = process.wait()
            self.events.put(("done", code))

    def poll_events(self):
        # Giới hạn mỗi lượt để cửa sổ vẫn phản hồi khi có nhiều log.
        for _ in range(150):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.write_log(value)
            elif kind == "cameras":
                self.apply_cameras(value)
            elif kind == "done":
                stopped = self.stop_requested
                self.process = None
                self.draw_button.configure(state="normal")
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.refresh_button.configure(state="normal")

                if stopped:
                    self.status.set("Đã dừng")
                    self.write_log("Đã dừng tác vụ.")
                elif value == 0:
                    self.status.set("Đã hoàn tất")
                    self.write_log("Tác vụ đã kết thúc.")
                else:
                    self.tabs.select(self.log_tab)
                    self.status.set("Có lỗi — xem thông báo")
                    self.write_log(
                        f"Chương trình kết thúc với mã {value}."
                    )

        if self.closing and self.process is None:
            self.root.destroy()
            return

        self.root.after(100, self.poll_events)

    def stop(self):
        process = self.process
        if process is None or process.poll() is not None:
            return

        self.stop_requested = True
        self.status.set("Đang dừng…")
        self.stop_button.configure(state="disabled")
        self.write_log(
            "Đang dừng tác vụ. Các ô vẽ chưa nhấn S sẽ không được lưu."
        )

        try:
            process.terminate()
        except OSError:
            return

        self.root.after(
            2000, lambda: self.kill_if_needed(process)
        )

    def kill_if_needed(self, process):
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def on_close(self):
        if self.is_running():
            if not messagebox.askyesno(
                "Đóng ứng dụng",
                "Tác vụ đang chạy sẽ bị dừng.\n"
                "Các ô vẽ chưa nhấn S sẽ không được lưu.\n\n"
                "Bạn muốn đóng ứng dụng?",
            ):
                return

            self.closing = True
            self.stop()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ParkingApp(root)
    root.mainloop()