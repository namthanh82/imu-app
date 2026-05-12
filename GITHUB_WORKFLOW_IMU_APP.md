# Đưa code lên **imu-app** và gộp **main**

Repo đích (ứng dụng): **`namthanh82/imu-app`** — trong Git remote thường tên **`target`**.

```bash
git remote -v
# target  https://github.com/namthanh82/imu-app.git
# origin  https://github.com/namthanh82/imu-web-min.git
```

## Quy trình mặc định (sau khi commit)

1. Không đưa `.env`, API key, hay file model/binary quá lớn vào Git.
2. Đồng bộ `main` với `imu-app`:
   ```bash
   git checkout main
   git pull target main
   ```
3. Gộp nhánh của bạn vào `main`:
   ```bash
   git merge <ten-nhanh-cua-ban>
   ```
4. Đẩy `main` lên **imu-app**:
   ```bash
   git push target main
   ```
5. (Tuỳ chọn) Đẩy luôn nhánh feature:
   ```bash
   git push target <ten-nhanh-cua-ban>
   ```

## Thay bằng Pull Request

Trên GitHub mở PR vào **`main`** của **`imu-app`**, merge xong coi như đã cập nhật production branch của app.
