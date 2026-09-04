# Phát hiện hành vi ngã từ khung xương

Dự án xây dựng hệ thống nhận diện hành vi ngã của con người từ chuỗi điểm khớp cơ thể. Hệ thống dự kiến nhận video, trích xuất khung xương qua từng frame và phân loại thành hai nhãn:

- `0 — nofall`: hoạt động bình thường.
- `1 — fall`: hành vi ngã.

Ứng dụng hướng tới giám sát an toàn, chăm sóc người cao tuổi và cảnh báo tai nạn trong nhà.

## Tiến độ

Quy trình dự án gồm bảy bước:

1. Thu thập dữ liệu — hoàn thành.
2. Làm sạch và chuẩn hóa — hoàn thành.
3. Trực quan hóa dữ liệu — hoàn thành.
4. Lựa chọn mô hình AI — đang chuẩn bị.
5. Huấn luyện — chưa thực hiện.
6. Đánh giá — chưa thực hiện.
7. Hoàn thiện hệ thống — chưa thực hiện.

Hiện tại dữ liệu đã sẵn sàng cho bước trích xuất khung xương và xây dựng mô hình. Dataset đang chứa ảnh RGB, bounding box và nhãn hành vi; tọa độ khung xương chưa được tạo.

## Dataset CAUCAFall

CAUCAFall là dataset hành vi trong nhà gồm:

- 10 người tham gia.
- 100 video, tương ứng 10 hoạt động cho mỗi người.
- 20.001 ảnh PNG, kích thước `720 × 480`.
- Nhiều điều kiện ánh sáng: tự nhiên, nhân tạo và 0 lux.

Năm tình huống ngã:

- Ngã về trước (`fall_forward`).
- Ngã ra sau (`fall_backward`).
- Ngã sang trái (`fall_left`).
- Ngã sang phải (`fall_right`).
- Ngã từ tư thế ngồi (`fall_sitting`).

Năm hoạt động bình thường:

- Đi bộ (`walk`).
- Ngồi xuống (`sit_down`).
- Quỳ xuống (`kneel`).
- Cúi nhặt đồ (`pick_up_object`).
- Nhảy tại chỗ (`hop`).

Mỗi nhãn bounding box có định dạng:

```text
class_id x_center y_center width height
```

Bốn tọa độ được chuẩn hóa trong `[0,1]`. Một frame thuộc video ngã không nhất thiết mang nhãn `fall`: các frame trước khi xảy ra ngã vẫn có thể là `nofall`.

## Kết quả làm sạch

- 20.001 ảnh ban đầu.
- Loại 2 ảnh không có nhãn.
- Còn 19.999 cặp ảnh–nhãn hợp lệ.
- Không có ID trùng hoặc bounding box vượt ngoài ảnh.
- Dữ liệu gốc không bị thay đổi.

Hai ảnh bị loại:

```text
Subject.5/Kneel/ars500236.png
Subject.6/Walk/cams600260.png
```

## Cách chia dữ liệu

Dữ liệu được chia theo người, không chia ngẫu nhiên theo frame. Cách này ngăn các frame gần giống nhau của cùng video xuất hiện ở cả train và test.

| Tập | Người tham gia | Nofall | Fall | Tổng |
|---|---|---:|---:|---:|
| Train | Subject 1–7 | 9.101 | 4.143 | 13.244 |
| Validation | Subject 8 | 1.421 | 704 | 2.125 |
| Test | Subject 9–10 | 3.088 | 1.542 | 4.630 |
| **Tổng** | **Subject 1–10** | **13.610** | **6.389** | **19.999** |

## Chuẩn hóa ảnh khi đọc dữ liệu

Ảnh processed vẫn được giữ nguyên ở `720 × 480`. Data loader cần thực hiện trong bộ nhớ:

1. Resize giữ tỷ lệ từ `720 × 480` thành `320 × 213`.
2. Thêm padding màu RGB `(114, 114, 114)` để được `320 × 320`.
3. Chuyển pixel sang `float32` và chia cho `255.0`.
4. Áp dụng đúng phép resize và padding lên bounding box hoặc điểm khớp.
5. Chỉ augmentation trên tập train.

## Tạo lại dữ liệu chuẩn hóa

Dataset không được lưu trên GitHub vì có dung lượng lớn. Sau khi tải CAUCAFall về máy, đặt dữ liệu theo cấu trúc:

```text
Dataset CAUCAFall/
└── Dataset CAUCAFall/
    └── CAUCAFall/
        ├── Subject.1/
        ├── ...
        └── Subject.10/
```

Sau đó chạy:

```bash
python normalize_caucafall.py
```

Kết quả được tạo trong `caucafall_normalized/`, gồm ảnh, nhãn, manifest và báo cáo thống kê. Thư mục này cũng không được commit lên GitHub.

## Các tệp được lưu trên GitHub

```text
.
├── README.md                 # Hướng dẫn và mô tả dự án
├── normalize_caucafall.py    # Làm sạch, đổi tên và chia dataset
└── .gitignore                # Ngăn dataset/checkpoint được commit
```

## Quy trình làm việc nhóm

Mỗi thành viên tạo branch riêng:

```bash
git switch main
git pull
git switch -c feature/ten-cong-viec
```

Sau khi hoàn thành:

```bash
git add .
git commit -m "Mô tả thay đổi"
git push -u origin feature/ten-cong-viec
```

Tạo Pull Request trên GitHub để kiểm tra trước khi hợp nhất vào `main`.

