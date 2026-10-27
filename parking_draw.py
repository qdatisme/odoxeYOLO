"""Vẽ các ô đỗ trên ảnh hoặc khung hình video bằng OpenCV."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def occupied_slots(detections, slots, threshold=0.35):
    """Có xe nếu khung xe phủ đủ tỷ lệ diện tích ô đỗ."""
    boxes = list(detections)
    states = {}

    for slot in slots:
        polygon = np.asarray(slot["points"], dtype=np.float32)
        slot_area = abs(cv2.contourArea(polygon))
        busy = False

        if slot_area > 0:
            for box in boxes:
                x1, y1, x2, y2 = map(float, box[:4])

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
        "source",
        help="Đường dẫn ảnh/video hoặc số thứ tự camera, ví dụ: 0",
    )
    parser.add_argument(
        "--output",
        default="parking_slots.json",
        help="Tệp lưu các ô đỗ, mặc định: parking_slots.json",
    )
    parser.add_argument(
        "--frame",
        type=int,
        default=0,
        help="Số thứ tự khung hình video dùng để vẽ, bắt đầu từ 0",
    )
    args = parser.parse_args()

    # Thử đọc nguồn dưới dạng ảnh.
    frame = (
        cv2.imread(args.source)
        if Path(args.source).is_file()
        else None
    )

    # Nếu không phải ảnh, thử mở video hoặc camera.
    if frame is None:
        source = (
            int(args.source)
            if args.source.isdecimal()
            else args.source
        )
        cap = cv2.VideoCapture(source)

        if args.frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)

        ok, frame = cap.read()
        cap.release()

        if not ok:
            raise SystemExit(
                "Không đọc được nguồn. "
                "Hãy kiểm tra đường dẫn hoặc số thứ tự camera."
            )

    height, width = frame.shape[:2]
    slots, points = [], []
    output = Path(args.output)

    # Nạp các ô đỗ đã lưu trước đó.
    if output.exists():
        data = json.loads(output.read_text(encoding="utf-8"))

        if data["image_size"] != [width, height]:
            raise SystemExit(
                "Kích thước ảnh khác với cấu hình đã lưu. "
                "Hãy dùng --output để chọn tệp lưu mới."
            )

        slots = data["slots"]
        print(f"Đã tải {len(slots)} ô đỗ từ: {output.resolve()}")

    # Thu nhỏ ảnh hiển thị và quy đổi tọa độ chuột về ảnh gốc.
    scale = min(1.0, 1280 / width, 800 / height)
    display_width = round(width * scale)
    display_height = round(height * scale)
    sx = display_width / width
    sy = display_height / height

    window = "Ve o do xe"
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

    def mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([
                min(width - 1, round(x / sx)),
                min(height - 1, round(y / sy)),
            ])
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    def screen(poly):
        """Quy đổi tọa độ ảnh gốc sang ảnh hiển thị."""
        return np.round(
            np.asarray(poly) * [sx, sy]
        ).astype(np.int32)

    cv2.setMouseCallback(window, mouse)

    message = "Bam cac goc theo thu tu quanh o; ENTER de them o"

    print("Hướng dẫn vẽ ô đỗ:")
    print("- Chuột trái: thêm điểm.")
    print("- Chuột phải hoặc U: xóa điểm vừa chọn.")
    print("- Enter: thêm ô đỗ.")
    print("- D: xóa ô đỗ cuối cùng.")
    print("- C: hủy các điểm đang vẽ.")
    print("- S: lưu tất cả ô đã thêm.")
    print("- Q hoặc Esc: thoát.")

    while True:
        canvas = cv2.resize(
            frame, (display_width, display_height)
        )

        # Vẽ các ô đã thêm bằng màu xanh.
        for slot in slots:
            polygon = screen(slot["points"])
            cv2.polylines(
                canvas, [polygon], True, (0, 255, 0), 2
            )
            cv2.putText(
                canvas,
                slot["id"],
                tuple(polygon[0]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        # Vẽ các điểm đang chọn bằng màu vàng.
        if points:
            polygon = screen(points)
            cv2.polylines(
                canvas, [polygon], False, (0, 255, 255), 2
            )

            for point in polygon:
                cv2.circle(
                    canvas,
                    tuple(point),
                    4,
                    (0, 255, 255),
                    -1,
                )

        # Thanh hướng dẫn thao tác.
        cv2.rectangle(
            canvas,
            (0, 0),
            (display_width, 58),
            (0, 0, 0),
            -1,
        )
        cv2.putText(
            canvas,
            "ENTER:them o  U:xoa diem  D:xoa o cuoi  "
            "C:huy ve  S:luu  Q:thoat",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
        )
        cv2.putText(
            canvas,
            message,
            (8, 46),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
        )

        cv2.imshow(window, canvas)
        key = cv2.waitKey(20) & 0xFF

        if key in (10, 13):
            if (
                len(points) >= 3
                and cv2.isContourConvex(
                    np.asarray(points, dtype=np.int32)
                )
            ):
                slots.append({
                    "id": f"P{len(slots) + 1}",
                    "points": points.copy(),
                })
                points.clear()
                message = "Da them o. Nhan S de luu."
            else:
                message = (
                    "Can >= 3 goc theo thu tu quanh o; "
                    "khong ve lom hoac cat cheo."
                )

        elif key == ord("u") and points:
            points.pop()

        elif key == ord("d") and slots:
            slots.pop()
            message = "Da xoa o cuoi. Nhan S de luu."

        elif key == ord("c"):
            points.clear()
            message = "Da huy cac diem dang ve. Co the ve lai."

        elif key == ord("s"):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "image_size": [width, height],
                        "slots": slots,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            message = (
                f"Da luu {len(slots)} o. "
                "O dang ve chua nhan ENTER se khong duoc luu."
            )
            print(f"Đã lưu {len(slots)} ô đỗ: {output.resolve()}")

        elif (
            key in (ord("q"), 27)
            or cv2.getWindowProperty(
                window, cv2.WND_PROP_VISIBLE
            ) < 1
        ):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()