import os
import sys

# Thiết lập môi trường kiểm thử để cô lập hoàn toàn cơ sở dữ liệu vật lý
os.environ["APP_ENV"] = "testing"

# Thêm thư mục hiện tại vào sys.path để pytest tìm thấy e16_app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

