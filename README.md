# o_do_xe_YOLO

Đồ án kiểm tra trạng thái ô đỗ: YOLO phát hiện ô tô → lấy tâm khung bao → kiểm tra tâm có nằm trong đa giác ô đỗ đã vẽ hay không.

## 1. Cài đặt trên Windows

Cài Python 3.11 hoặc 3.12 và chọn Add Python to PATH. Giải nén project, mở Terminal trong thư mục o_do_xe_YOLO, chạy:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cần Internet để cài thư viện và tải trọng số YOLO lần đầu. Mặc định dùng mô hình COCO yolo11n.pt; Ultralytics tự tải khi chạy lần đầu. Có thể dùng --model để trỏ đến trọng số đã có. Máy không có GPU vẫn chạy được bằng CPU, tốc độ tùy cấu hình.

## 2. Vẽ ô đỗ bằng chuột

Đặt video bãi xe của bạn trong thư mục project, ví dụ bai_xe.mp4:

```powershell
.venv\Scripts\python.exe parking_draw.py "bai_xe.mp4"
```

Hoặc dùng webcam:

```powershell
.venv\Scripts\python.exe parking_draw.py 0
```

- Bấm chuột trái lần lượt vào 4 góc quanh mỗi ô đỗ, sau đó Enter để xác nhận. Ô được đặt tên P1, P2… Có thể dùng đa giác lồi từ 3 điểm trở lên.
- Chuột phải hoặc U: bỏ điểm vừa bấm.
- C: hủy ô đang vẽ; D: xóa ô đã xác nhận gần nhất.
- S: lưu vào parking_slots.json. Q hoặc Esc: thoát. Thoát không tự lưu.
- Vẽ các ô không chồng nhau. Có thể mở lại để tiếp tục chỉnh sửa các ô đã lưu.
- Dùng --frame 100 để lấy khung hình số 100 của video; dùng --output camera2.json để lưu cấu hình riêng.

## 3. Chạy kiểm tra trạng thái

Dùng đúng camera/video và góc nhìn đã vẽ:

```powershell
.venv\Scripts\python.exe main.py --source "bai_xe.mp4"
```

Webcam:

```powershell
.venv\Scripts\python.exe main.py --source 0
```

Cấu hình riêng:

```powershell
.venv\Scripts\python.exe main.py --source "bai_xe.mp4" --slots camera2.json --confidence 0.4 --model yolo11n.pt
```

- Khung xanh dương: ô tô được YOLO phát hiện; chấm tím: tâm xe.
- Viền đỏ / OCCUPIED: có tâm xe nằm trong ô.
- Viền xanh lá / FREE: không có tâm xe nằm trong ô.
- Thanh trên cùng: tổng số ô, số ô có xe, số ô trống.
- Q hoặc Esc: thoát.

## Cấu trúc và giới hạn

parking_draw.py chứa công cụ vẽ và hàm occupied_slots. main.py chạy YOLO và hiển thị trạng thái. requirements.txt chứa thư viện cần cài. parking_slots.json được tạo sau khi vẽ; trọng số được tải khi chạy. Project không kèm video bãi xe hoặc trọng số.

Tâm xe chỉ cần nằm trong ô, không cần trùng tâm ô đỗ. Điểm trên biên cũng được tính là có xe. Các tọa độ dùng kích thước ảnh gốc; nếu đổi camera, góc nhìn hoặc độ phân giải, cần vẽ lại. Nếu vẽ từ ảnh tĩnh, ảnh phải có cùng kích thước và góc nhìn với nguồn chạy.

Trạng thái được tính cho từng khung hình, nên có thể nhấp nháy khi YOLO bỏ sót xe. Chưa có cơ chế làm mượt theo thời gian hoặc theo dõi xe. Camera nhìn xiên hoặc xe che nhau có thể làm tâm khung bao rơi ra ngoài ô; hãy kiểm tra trực quan các chấm tâm khi chạy thử.

Bản này đã có đầy đủ luồng vẽ → lưu → phát hiện → xác định trạng thái, nhưng chưa được chạy kiểm thử thực tế trong môi trường tạo project vì chưa có Python và nguồn ảnh/video bãi xe.
