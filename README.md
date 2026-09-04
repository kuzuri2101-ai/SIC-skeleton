# Phát hiện hành vi ngã từ khung xương

Dự án xây dựng hệ thống nhận diện hành vi ngã từ chuỗi điểm khớp cơ thể. Hệ thống dự kiến nhận video, trích xuất khung xương theo từng frame và phân loại `0 — nofall` hoặc `1 — fall`.

Ứng dụng hướng tới giám sát an toàn, chăm sóc người cao tuổi và cảnh báo tai nạn trong nhà.

## 1. Tiến độ dự án

| Bước | Nội dung | Trạng thái |
|---:|---|---|
| 1 | Thu thập dữ liệu | Hoàn thành |
| 2 | Làm sạch và chuẩn hóa | Hoàn thành |
| 3 | Trực quan hóa dữ liệu | Hoàn thành |
| 4 | Lựa chọn mô hình AI | Đang chuẩn bị |
| 5 | Huấn luyện | Chưa thực hiện |
| 6 | Đánh giá | Chưa thực hiện |
| 7 | Hoàn thiện hệ thống | Chưa thực hiện |

Hiện tại dataset cung cấp **ảnh RGB, bounding box và nhãn hành vi**. Tọa độ khung xương chưa có sẵn và cần được trích xuất ở bước tiếp theo.

## 2. Tổng quan CAUCAFall

- 10 người tham gia (`Subject.1` đến `Subject.10`).
- Mỗi người thực hiện 10 hoạt động.
- 100 video và 20.001 frame PNG kích thước `720 × 480`.
- Có ánh sáng tự nhiên, nhân tạo và điều kiện 0 lux.

| Thư mục gốc | Tên chuẩn hóa | Ý nghĩa |
|---|---|---|
| `Fall backwards` | `fall_backward` | Ngã ra phía sau |
| `Fall forward` | `fall_forward` | Ngã về phía trước |
| `Fall left` | `fall_left` | Ngã sang trái |
| `Fall right` | `fall_right` | Ngã sang phải |
| `Fall sitting` | `fall_sitting` | Ngã từ tư thế ngồi |
| `Hop` | `hop` | Nhảy tại chỗ |
| `Kneel` | `kneel` | Quỳ xuống |
| `Pick up object` | `pick_up_object` | Cúi nhặt đồ |
| `Sit down` | `sit_down` | Ngồi xuống |
| `Walk` | `walk` | Đi bộ |

## 3. Cấu trúc dataset gốc

Dataset không lưu trên GitHub vì dung lượng lớn. Cấu trúc đầy đủ sau khi tải về:

```text
Dataset CAUCAFall/
└── Dataset CAUCAFall/
    ├── Dataset details.xlsx
    ├── Figure1 fall recognition based on feature extraction.jpeg
    ├── Figure2 fall recognition based on openpose.jpeg
    ├── Figure3 fall recognition based on yolo detectors.jpeg
    ├── Figure4 dimensions.jpeg
    ├── Figure5 folders for each subject and different activities of the dataset.jpeg
    ├── Figure6 content of the different txt files.jpeg
    ├── Figure7 camera-Fall Distance.jpeg
    ├── Figure8 angle of fall.jpeg
    └── CAUCAFall/
        ├── Subject.1/
        │   ├── Fall backwards/
        │   ├── Fall forward/
        │   ├── Fall left/
        │   ├── Fall right/
        │   ├── Fall sitting/
        │   ├── Hop/
        │   ├── Kneel/
        │   ├── Pick up object/
        │   ├── Sit down/
        │   └── Walk/
        ├── Subject.2/
        ├── ...
        └── Subject.10/
```

`Subject.N` chứa toàn bộ dữ liệu của người thứ `N`. Mỗi subject có đủ 10 thư mục hoạt động. Thông tin subject được giữ lại để chia dữ liệu theo người và tránh rò rỉ giữa train/test.

## 4. Các file trong thư mục hoạt động

Ví dụ:

```text
Subject.1/Fall backwards/
├── FallBackwardsS1.avi
├── cas100001.png
├── cas100001.txt
├── cas100002.png
├── cas100002.txt
├── ...
└── classes.txt
```

| Loại file | Công dụng |
|---|---|
| `.avi` | Video gốc của một người thực hiện một hoạt động; dùng để xem chuyển động hoặc tạo lại chuỗi frame. |
| `.png` | Một frame tách từ video; là ảnh đầu vào để phát hiện người và trích xuất khung xương. |
| `.txt` cùng tên PNG | Nhãn của đúng frame đó, gồm lớp hành vi và bounding box người. |
| `classes.txt` | Danh sách tên lớp và thứ tự class ID; không phải một mẫu huấn luyện. |

Quan hệ giữa các file:

```text
FallBackwardsS1.avi  →  cas100001.png  +  cas100001.txt
video gốc               frame ảnh         nhãn frame
```

### Prefix trong tên ảnh gốc

| Prefix | Hoạt động |
|---|---|
| `cas` | Fall backwards |
| `cfs` | Fall forward |
| `cis` | Fall left |
| `cds` | Fall right |
| `css` | Fall sitting |
| `sals` | Hop |
| `ars` | Kneel |
| `res` | Pick up object |
| `ses` | Sit down |
| `cams` | Walk |

Ví dụ `cams900140.png` thuộc hoạt động đi bộ của Subject 9. Do tên gốc chưa hoàn toàn đồng nhất, script sẽ đổi thành tên dễ đọc như `s09_walk_000140.png`.

## 5. Ý nghĩa file nhãn `.txt`

Ví dụ `cas100001.txt`:

```text
0 0.309028 0.526042 0.215278 0.489583
```

Định dạng:

```text
class_id x_center y_center box_width box_height
```

| Trường | Ý nghĩa |
|---|---|
| `class_id` | `0 = nofall`, `1 = fall` |
| `x_center` | Tọa độ ngang của tâm bounding box |
| `y_center` | Tọa độ dọc của tâm bounding box |
| `box_width` | Chiều rộng bounding box |
| `box_height` | Chiều cao bounding box |

Bốn tọa độ nằm trong `[0,1]`. Chuyển về pixel của ảnh `720 × 480` như sau:

```text
x_pixel      = x_center × 720
y_pixel      = y_center × 480
width_pixel  = box_width × 720
height_pixel = box_height × 480
```

Mỗi file chứa một dòng vì mỗi frame chỉ có một người cần nhận diện.

### `classes.txt`

Trong thư mục ngã, file thường chứa:

```text
nofall
fall
```

Dòng đầu tương ứng lớp `0`, dòng thứ hai tương ứng lớp `1`. Trong thư mục hoạt động bình thường, file chỉ có `nofall`. Data loader không đọc `classes.txt` như một mẫu huấn luyện.

### Lưu ý về nhãn Fall

Một video ngã gồm cả quá trình:

```text
đứng/chuẩn bị → mất thăng bằng → đang ngã → nằm trên sàn
```

Vì vậy một frame nằm trong thư mục `Fall forward` vẫn có thể mang nhãn `0 — nofall`. Khi huấn luyện phải đọc nhãn của từng frame, không suy ra nhãn chỉ từ tên thư mục.

## 6. File mô tả bên ngoài thư mục Subject

| File | Nội dung và công dụng |
|---|---|
| `Dataset details.xlsx` | Thống kê ánh sáng, số frame, khoảng cách camera–vị trí ngã, góc ngã và che khuất của từng subject. |
| `Figure1 ... feature extraction.jpeg` | Minh họa phát hiện ngã bằng đặc trưng hình học. |
| `Figure2 ... openpose.jpeg` | Minh họa phát hiện ngã bằng khung xương OpenPose. |
| `Figure3 ... yolo detectors.jpeg` | Minh họa phát hiện ngã bằng YOLO và bounding box. |
| `Figure4 dimensions.jpeg` | Kích thước phòng và vị trí/độ cao camera. |
| `Figure5 folders ... jpeg` | Cấu trúc thư mục Subject và Activity. |
| `Figure6 content ... txt files.jpeg` | Nội dung nhãn bounding box và `classes.txt`. |
| `Figure7 camera-Fall Distance.jpeg` | Cách đo khoảng cách từ camera tới vị trí ngã. |
| `Figure8 angle of fall.jpeg` | Cách xác định góc/hướng ngã so với camera. |

Các file này dùng để hiểu dataset và viết báo cáo, không đưa trực tiếp vào mô hình.

## 7. Kết quả làm sạch và chia dữ liệu

- 20.001 ảnh ban đầu.
- Sửa ánh xạ 4 cặp ảnh–nhãn bị lệch tên.
- Loại 2 ảnh không có nhãn.
- Còn 19.999 cặp ảnh–nhãn hợp lệ.
- Không có ID trùng, nhãn rỗng hoặc bounding box vượt ngoài ảnh.

Hai ảnh bị loại:

```text
Subject.5/Kneel/ars500236.png
Subject.6/Walk/cams600260.png
```

Dữ liệu được chia **theo người**, không chia ngẫu nhiên theo frame:

| Tập | Người tham gia | Nofall | Fall | Tổng |
|---|---|---:|---:|---:|
| Train | Subject 1–7 | 9.101 | 4.143 | 13.244 |
| Validation | Subject 8 | 1.421 | 704 | 2.125 |
| Test | Subject 9–10 | 3.088 | 1.542 | 4.630 |
| **Tổng** | **Subject 1–10** | **13.610** | **6.389** | **19.999** |

Các frame liên tiếp trong cùng video gần như giống nhau. Chia theo subject bảo đảm người trong test chưa xuất hiện trong train, giúp kết quả đánh giá thực tế hơn.

## 8. Cấu trúc sau chuẩn hóa

```text
caucafall_normalized/
├── images/
│   ├── train/
│   ├── validation/
│   └── test/
├── labels/
│   ├── train/
│   ├── validation/
│   └── test/
├── manifests/
│   ├── all.csv
│   ├── train.csv
│   ├── validation.csv
│   └── test.csv
├── reports/
│   ├── dataset_statistics.json
│   ├── filename_mapping.csv
│   └── invalid_files.csv
└── metadata.json
```

| Đường dẫn | Công dụng |
|---|---|
| `images/train/` | Ảnh dùng để cập nhật trọng số mô hình. |
| `images/validation/` | Ảnh dùng để chọn tham số và early stopping. |
| `images/test/` | Ảnh chỉ dùng để đánh giá cuối cùng. |
| `labels/<split>/` | Nhãn có cùng tên cơ sở với ảnh tương ứng. |
| `manifests/all.csv` | Danh sách và metadata của toàn bộ 19.999 mẫu. |
| `manifests/train.csv` | Danh sách mẫu dùng để huấn luyện. |
| `manifests/validation.csv` | Danh sách mẫu dùng để validation. |
| `manifests/test.csv` | Danh sách mẫu dùng để test. |
| `reports/dataset_statistics.json` | Tổng số mẫu, phân bố lớp, hoạt động, subject và quy tắc chuẩn hóa. |
| `reports/filename_mapping.csv` | Ánh xạ tên gốc sang tên chuẩn hóa để truy ngược nguồn. |
| `reports/invalid_files.csv` | File bị loại và lý do loại. |
| `metadata.json` | Phiên bản dataset, tên lớp, cách chia tập và mã kiểm tra manifest. |

Ảnh processed là **hard link** tới ảnh gốc để không nhân đôi hơn 8 GB. Không chỉnh sửa ảnh processed; data loader chỉ đọc và biến đổi trong bộ nhớ.

## 9. Các cột trong manifest

| Cột | Ý nghĩa |
|---|---|
| `sample_id` | ID duy nhất sau chuẩn hóa. |
| `image_path`, `label_path` | Đường dẫn ảnh và nhãn processed. |
| `subject_id` | Mã người tham gia. |
| `activity` | Tên hoạt động chuẩn hóa. |
| `video_id`, `frame_index` | Video nguồn và số thứ tự frame. |
| `class_id`, `class_name` | ID và tên lớp hành vi. |
| `lighting`, `lux` | Loại và cường độ ánh sáng. |
| `width`, `height` | Kích thước ảnh gốc. |
| `split` | `train`, `validation` hoặc `test`. |
| `source_image`, `source_label` | Đường dẫn gốc để truy vết mẫu. |

## 10. Tạo lại dataset chuẩn hóa

Yêu cầu Python 3; script không cần thư viện bổ sung.

```bash
python normalize_caucafall.py
```

Nếu dataset nằm ở vị trí khác:

```bash
python normalize_caucafall.py --raw-root "duong-dan/CAUCAFall" --output-root "caucafall_normalized"
```

Script kiểm tra ảnh/nhãn, chuẩn hóa tên, chia tập và tạo manifest/báo cáo.

## 11. Chuẩn hóa ảnh khi đọc

Data loader thực hiện trong bộ nhớ:

1. Resize giữ tỷ lệ `720 × 480` thành `320 × 213`.
2. Thêm padding RGB `(114, 114, 114)` thành `320 × 320`.
3. Chuyển pixel sang `float32` và chia `255.0`.
4. Biến đổi bounding box hoặc điểm khớp bằng cùng tỷ lệ và padding.
5. Chỉ augmentation trên tập train.

Không kéo giãn trực tiếp thành hình vuông vì sẽ làm biến dạng cơ thể.

## 12. Bước tiếp theo: dữ liệu khung xương

```text
Ảnh RGB
→ dùng bounding box lấy vùng người
→ trích xuất điểm khớp (x, y, confidence)
→ chuẩn hóa theo tâm hông và kích thước cơ thể
→ ghép 16 hoặc 32 frame thành sequence
→ đưa vào MLP/LSTM/ST-GCN
→ dự đoán fall hoặc nofall
```

Ngã là một quá trình chuyển động, vì vậy mô hình chính nên học chuỗi khung xương thay vì chỉ nhìn một frame độc lập.

## 13. Nội dung repository và làm việc nhóm

```text
.
├── README.md                 # Tài liệu dự án và dataset
├── normalize_caucafall.py    # Làm sạch, đổi tên và chia dữ liệu
└── .gitignore                # Ngăn dataset/checkpoint bị commit
```

Dataset gốc, dataset processed và checkpoint không lưu trên GitHub. Nhóm nên chia sẻ chúng qua Drive và dùng script để tạo cùng một phiên bản processed.

Mỗi thành viên làm trên branch riêng:

```bash
git switch main
git pull
git switch -c feature/ten-cong-viec
# chỉnh sửa
git add .
git commit -m "Mô tả ngắn công việc"
git push -u origin feature/ten-cong-viec
```

Sau đó tạo Pull Request để thành viên khác kiểm tra trước khi hợp nhất vào `main`.
