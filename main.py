"""Nhận diện xe và xác định trạng thái ô đỗ."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def occupied_slots(detections, slots, threshold=0.35):
    """Ô có xe khi khung nhận diện phủ đủ tỷ lệ diện tích ô đỗ."""
    boxes = list(detections)
    states = {}

    for slot in slots:
        polygon = np.asarray(slot["points"], dtype=np.float32)
        slot_area = abs(cv2.contourArea(polygon))
        busy = False

        if slot_area > 0:
            for box in boxes:
                x1, y1, x2, y2 = map(float, box[:4])

                if x2 <= x1 or y2 <= y1:
                    continue

                rectangle = np.array([
                    [x1, y1],
                    [x2, y1],
                    [x2, y2],
                    [x1, y2],
                ], dtype=np.float32)

                overlap, _ = cv2.intersectConvexConvex(
                    polygon, rectangle
                )

                if overlap / slot_area >= threshold:
                    busy = True
                    break

        states[slot["id"]] = busy

    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--source",
        default="0",
        help="Đường dẫn video hoặc số thứ tự camera, ví dụ: 0",
    )
    parser.add_argument(
        "--slots",
        default="parking_slots.json",
        help="Đường dẫn tệp chứa các ô đỗ đã vẽ",
    )
    parser.add_argument(
        "--model",
        default="yolo26n.pt",
        help="Đường dẫn hoặc tên mô hình YOLO",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.15,
        help="Ngưỡng tin cậy nhận diện, mặc định: 0.15",
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.35,
        help="Tỷ lệ diện tích ô bị khung xe phủ, mặc định: 0.35",
    )
    parser.add_argument(
        "--occupied-delay",
        type=float,
        default=3.0,
        help="Thời gian xác nhận có xe, mặc định: 3 giây",
    )
    parser.add_argument(
        "--free-delay",
        type=float,
        default=2.0,
        help="Thời gian xác nhận ô trống, mặc định: 2 giây",
    )

    args = parser.parse_args()

    if not 0 < args.confidence <= 1:
        parser.error(
            "--confidence phải lớn hơn 0 và không vượt quá 1."
        )

    if not 0 < args.overlap <= 1:
        parser.error(
            "--overlap phải lớn hơn 0 và không vượt quá 1."
        )

    if args.occupied_delay < 0 or args.free_delay < 0:
        parser.error("Thời gian xác nhận phải lớn hơn hoặc bằng 0.")

    slots_path = Path(args.slots)

    if not slots_path.exists():
        raise SystemExit(
            "Chưa có tệp cấu hình ô đỗ.\n"
            "Hãy vẽ và lưu ô đỗ trước bằng lệnh:\n"
            "python parking_draw.py baixe.mp4"
        )

    config = json.loads(
        slots_path.read_text(encoding="utf-8")
    )
    slots = config["slots"]

    if not slots:
        raise SystemExit(
            "Chưa có ô đỗ nào được lưu. "
            "Hãy vẽ ô đỗ và nhấn S để lưu."
        )

    print(f"Đã tải {len(slots)} ô đỗ.")
    print(f"Đang tải mô hình: {args.model}")

    model = YOLO(args.model)

    # Tên lớp của mô hình giữ nguyên để tìm đúng lớp ô tô.
    car_ids = [
        class_id
        for class_id, name in model.names.items()
        if name.lower() == "car"
    ]

    if not car_ids:
        raise SystemExit(
            "Mô hình không có lớp 'car' để nhận diện ô tô."
        )

    source = (
        int(args.source)
        if args.source.isdecimal()
        else args.source
    )
    is_camera = isinstance(source, int)
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        cap.release()
        raise SystemExit(
            "Không mở được video hoặc camera. "
            "Hãy kiểm tra giá trị --source."
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if not np.isfinite(fps) or fps <= 0:
        fps = 30.0

        if not is_camera:
            print(
                "Không đọc được FPS của video. "
                "Tạm dùng 30 FPS để tính thời gian."
            )

    # None: chưa xác định; True: có xe; False: ô trống.
    confirmed = {slot["id"]: None for slot in slots}

    # Kết quả đang được theo dõi và thời điểm bắt đầu xác nhận.
    candidate = {slot["id"]: None for slot in slots}
    candidate_since = {slot["id"]: None for slot in slots}

    frame_number = 0
    window = "Nhan dien o do xe - Nhan Q de thoat"

    print(f"Đang mở nguồn: {args.source}")
    print(f"Ngưỡng tin cậy: {args.confidence}")
    print(
        f"Xác nhận có xe: {args.occupied_delay:g} giây | "
        f"Xác nhận ô trống: {args.free_delay:g} giây"
    )
    print("Màu xanh: ô trống | Vàng: đang kiểm tra | Đỏ: có xe")
    print("Nhấn Q hoặc Esc trong cửa sổ video để thoát.")

    try:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 1280, 720)

        while True:
            ok, frame = cap.read()

            if not ok:
                print(
                    "Video đã kết thúc hoặc không nhận được "
                    "khung hình từ nguồn."
                )
                break

            # Camera dùng thời gian thực.
            # Video dùng số khung hình và FPS để tính thời gian.
            now = (
                time.monotonic()
                if is_camera
                else frame_number / fps
            )
            frame_number += 1

            height, width = frame.shape[:2]

            if [width, height] != config["image_size"]:
                raise SystemExit(
                    "Kích thước nguồn khác với cấu hình ô đỗ đã lưu. "
                    "Hãy vẽ lại ô đỗ cho nguồn này."
                )

            result = model.predict(
                frame,
                classes=car_ids,
                conf=args.confidence,
                imgsz=1280,
                verbose=False,
            )[0]

            boxes = result.boxes.xyxy.cpu().tolist()

            raw_states = occupied_slots(
                boxes,
                slots,
                threshold=args.overlap,
            )

            # Chỉ xác nhận khi kết quả duy trì đủ thời gian.
            for slot in slots:
                sid = slot["id"]
                detected = bool(raw_states[sid])

                if candidate[sid] != detected:
                    candidate[sid] = detected
                    candidate_since[sid] = now

                delay = (
                    args.occupied_delay
                    if detected
                    else args.free_delay
                )

                if now - candidate_since[sid] >= delay:
                    confirmed[sid] = detected

            # Vẽ khung nhận diện xe.
            for box in boxes:
                x1, y1, x2, y2 = map(int, box)

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (255, 178, 0),
                    2,
                )

            busy_count = 0
            free_count = 0
            pending_count = 0

            # Vẽ từng ô đỗ và trạng thái tương ứng.
            for slot in slots:
                sid = slot["id"]
                pending = (
                    confirmed[sid] is None
                    or candidate[sid] != confirmed[sid]
                )

                if pending:
                    color = (0, 255, 255)

                    delay = (
                        args.occupied_delay
                        if candidate[sid]
                        else args.free_delay
                    )

                    remaining = max(
                        0.0,
                        delay - (now - candidate_since[sid]),
                    )

                    label = f"DANG KIEM TRA {remaining:.1f}s"
                    pending_count += 1

                elif confirmed[sid]:
                    color = (0, 0, 255)
                    label = "CO XE"
                    busy_count += 1

                else:
                    color = (0, 220, 0)
                    label = "CON TRONG"
                    free_count += 1

                polygon = np.asarray(
                    slot["points"],
                    dtype=np.int32,
                )

                cv2.polylines(
                    frame,
                    [polygon],
                    True,
                    color,
                    2,
                )

                anchor = tuple(map(int, polygon[0]))

                cv2.putText(
                    frame,
                    f"{sid}: {label}",
                    anchor,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

            # Thanh thống kê.
            text = (
                f"Tong o: {len(slots)} | "
                f"Co xe: {busy_count} | "
                f"Con trong: {free_count} | "
                f"Dang kiem tra: {pending_count}"
            )

            cv2.rectangle(
                frame,
                (0, 0),
                (width, 42),
                (0, 0, 0),
                -1,
            )

            cv2.putText(
                frame,
                text,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow(window, frame)

            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                print("Đã dừng chương trình.")
                break

            if cv2.getWindowProperty(
                window,
                cv2.WND_PROP_VISIBLE,
            ) < 1:
                print("Đã đóng cửa sổ nhận diện.")
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()