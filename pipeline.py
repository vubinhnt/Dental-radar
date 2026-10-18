import os
import json
import time
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from typing import List, Optional
from google import genai
from google.genai import types

# -----------------------------
# 1. Định nghĩa Pydantic Schema cho Gemini ép kiểu Structured JSON
# -----------------------------
class CoreInsight(BaseModel):
    headline: str
    summary: str
    target_audience: List[str]

class EntitiesMentioned(BaseModel):
    brands_or_manufacturers: Optional[List[str]] = []
    materials_or_devices: Optional[List[str]] = []
    legal_references: Optional[List[str]] = []

class CommunitySentiment(BaseModel):
    overall_sentiment: str
    key_concerns_or_criticisms: Optional[List[str]] = []
    price_or_cost_hints: Optional[str] = None
    consensus_verdict: str

class DentalReport(BaseModel):
    is_relevant: bool
    rejection_reason: Optional[str] = None
    primary_category: str
    sub_specialty: List[str]
    core_insight: CoreInsight
    entities_mentioned: Optional[EntitiesMentioned] = None
    community_sentiment_and_discussion: CommunitySentiment
    actionable_takeaway: str

# -----------------------------
# 2. Bộ lọc 90% bằng Code thuần
# -----------------------------
DENTAL_KEYWORDS = [
    "implant", "zirconia", "phôi sứ", "máy scan", "cbct", "máng hướng dẫn",
    "cone morse", "vít", "khay trong suốt", "chỉnh nha", "nội nha", "bioceramic",
    "nghị định 98", "công bố tiêu chuẩn", "lưu hành", "bộ y tế", "cad/cam", "resin 3d"
]

SPAM_KEYWORDS = [
    "tuyển dụng", "tìm phụ tá", "lễ tân", "giảm giá 50%", "bọc răng sứ giá rẻ",
    "sale sốc", "nhượng lại phòng khám", "tuyển mẫu"
]

def is_worth_analyzing(post: dict) -> bool:
    content = (post.get("text", "") + " " + " ".join(post.get("comments", []))).lower()
    
    # 1. Loại bỏ bài spam B2C/tuyển dụng
    if any(spam in content for spam in SPAM_KEYWORDS):
        return False
        
    # 2. Bắt buộc có từ khóa kỹ thuật hoặc pháp lý ngành
    has_keyword = any(kw in content for kw in DENTAL_KEYWORDS)
    if not has_keyword:
        return False
        
    # 3. Phải có tương tác tối thiểu để phân tích thảo luận
    comments = post.get("comments", [])
    return len(comments) >= 1 or post.get("comment_count", 0) >= 1

# -----------------------------
# 3. Gọi Gemini Flash (10% tinh túy)
# -----------------------------
def analyze_with_gemini(client, post: dict) -> Optional[dict]:
    prompt = f"""
    Bạn là chuyên gia phân tích thị trường Trang thiết bị và Vật tư Nha khoa.
    Hãy phân tích bài đăng và các bình luận thực tế dưới đây để trích xuất insight:
    
    BÀI ĐĂNG GỐC:
    {post.get('text')}
    
    DANH SÁCH BÌNH LUẬN / THẢO LUẬN:
    {json.dumps(post.get('comments', []), ensure_ascii=False)}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DentalReport,
                temperature=0.1
            )
        )
        data = json.loads(response.text)
        if data.get("is_relevant"):
            return data
        return None
    except Exception as e:
        print(f"Lỗi khi xử lý qua Gemini: {e}")
        return None

# -----------------------------
# 4. Pipeline chạy tổng hợp & xuất HTML
# -----------------------------
def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Lỗi: Chưa thiết lập biến môi trường GEMINI_API_KEY!")
        return

    client = genai.Client(api_key=api_key)

    # Đọc dữ liệu đầu vào (cào từ scraper hoặc file json thô)
    # Nếu chưa có scraper ngoài, tạo file raw_sample.json để chạy thử
    raw_posts = []
    if os.path.exists("raw_posts.json"):
        with open("raw_posts.json", "r", encoding="utf-8") as f:
            raw_posts = json.load(f)
    else:
        # Dữ liệu mẫu kiểm thử
        raw_posts = [
            {
                "text": "Bác sĩ cho em hỏi dạo này nhập phôi Zirconia Upcera hay bị sai lệch màu với mẻ rìa cắn sau khi nung không? Em nung lò Zubler đúng biểu đồ nhiệt mà vẫn dính 2 cầu răng liên tiếp.",
                "comments": [
                    "Bác kiểm tra lại lô phôi mới nhập xem, đợt này hàng xách tay trôi nổi nhiệt độ kết thiêu không chuẩn đâu.",
                    "Đổi qua dùng Lava Plus hoặc Cercon HT đi bác, đắt hơn chút nhưng không đau đầu với khách."
                ],
                "comment_count": 2
            },
            {
                "text": "Cần tuyển gấp 2 phụ tá nha khoa làm việc tại Quận 1, lương 8-10tr, không yêu cầu kinh nghiệm, inbox ngay!",
                "comments": ["Em quan tâm ạ", "Check ib em"],
                "comment_count": 2
            }
        ]

    print(f"-> Tổng số bài thô thu thập được: {len(raw_posts)}")

    # Bước 1: 90% Code thuần lọc bài
    filtered_posts = [p for p in raw_posts if is_worth_analyzing(p)]
    print(f"-> Sau lọc code thuần (90%), còn lại: {len(filtered_posts)} bài đạt chuẩn.")

    # Bước 2: 10% gửi qua Gemini Flash
    results = []
    for idx, post in enumerate(filtered_posts):
        print(f"   Đang phân tích bài {idx + 1}/{len(filtered_posts)}...")
        report = analyze_with_gemini(client, post)
        if report:
            results.append(report)
        time.sleep(4)  # Nghỉ 4s để giữ RPM an toàn dưới 15

    # Bước 3: Tạo thư mục dist và render HTML
    os.makedirs("dist", exist_ok=True)
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("template.html")
    
    html_out = template.render(
        items=results,
        update_time=datetime.now().strftime("%d/%m/%Y %H:%M")
    )
    
    with open("dist/index.html", "w", encoding="utf-8") as f:
        f.write(html_out)
        
    print("-> Đã xuất bản file HTML thành công tại dist/index.html!")

if __name__ == "__main__":
    main()