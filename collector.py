import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

OUTPUT_FILE = "raw_posts.json"

# -------------------------------------------------------------
# NGUỒN 1: Tạp chí Công nghệ Nha khoa & Nghiên cứu Khoa học (RSS)
# -------------------------------------------------------------
RSS_FEEDS = [
    # Tin tức công nghệ, vật liệu nha khoa quốc tế
    "https://www.dental-tribune.com/feed/",
    # Nghiên cứu mới về Nha khoa & Implant trên BioMed Central / Springer Nature
    "https://bmcoralhealth.biomedcentral.com/articles/most-recent/rss.xml",
    # Tin tức thiết bị y tế & nha khoa Medgadget
    "https://www.medgadget.com/category/dentistry/feed"
]

def fetch_rss_feeds():
    posts = []
    print("-> Đang cào dữ liệu từ các tạp chí nha khoa quốc tế (RSS)...")
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:  # Lấy 5 bài mới nhất mỗi nguồn
                # Tẩy thẻ HTML trong phần summary
                soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
                clean_text = soup.get_text(separator=" ").strip()
                
                content = f"Tiêu đề: {entry.title}\nNội dung tóm tắt: {clean_text}\nLink gốc: {entry.link}"
                posts.append({
                    "source": feed_url,
                    "text": content,
                    "comments": [], # RSS không có comment, LLM sẽ tóm tắt phần công nghệ
                    "comment_count": 0,
                    "published_at": entry.get("published", "")
                })
        except Exception as e:
            print(f"Lỗi khi cào RSS {feed_url}: {e}")
    return posts

# -------------------------------------------------------------
# NGUỒN 2: Nghiên cứu PubMed (API chính thống - Miễn phí)
# -------------------------------------------------------------
def fetch_pubmed_dental_research():
    print("-> Đang quét bài báo khoa học mới trên PubMed (Implant, Zirconia, CBCT)...")
    posts = []
    query = "(dental implant OR zirconia OR intraoral scanner OR 3d printing dentistry) AND 2026[pdat]"
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax=5"
    
    try:
        res = requests.get(url, timeout=10).json()
        id_list = res.get("esearchresult", {}).get("idlist", [])
        
        if id_list:
            fetch_details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={','.join(id_list)}&retmode=json"
            detail_res = requests.get(fetch_details_url, timeout=10).json()
            
            for pmid in id_list:
                item = detail_res.get("result", {}).get(pmid, {})
                title = item.get("title", "")
                source = item.get("source", "")
                
                posts.append({
                    "source": f"PubMed (PMID: {pmid})",
                    "text": f"Nghiên cứu lâm sàng: {title}. Tạp chí: {source}. Link: https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "comments": [],
                    "comment_count": 0
                })
    except Exception as e:
        print(f"Lỗi khi quét PubMed: {e}")
        
    return posts

# -------------------------------------------------------------
# NGUỒN 3: Facebook Groups & TikTok qua Apify API (Tùy chọn)
# -------------------------------------------------------------
def fetch_social_via_apify():
    apify_token = os.environ.get("APIFY_TOKEN")
    if not apify_token:
        print("-> Không có APIFY_TOKEN: Bỏ qua bước cào Facebook/TikTok.")
        return []
        
    print("-> Đang lấy dữ liệu thảo luận từ Facebook Groups / TikTok qua Apify...")
    posts = []
    # Ví dụ: Gọi Apify Actor "facebook-groups-scraper" đã cấu hình sẵn
    # payload = { "groupUrls": ["https://www.facebook.com/groups/..."], "maxPosts": 10 }
    # try:
    #     res = requests.post(f"https://api.apify.com/v2/acts/apify~facebook-groups-scraper/run-sync-get-dataset-items?token={apify_token}", json=payload)
    #     for item in res.json():
    #         posts.append({
    #             "source": "Facebook Group",
    #             "text": item.get("text", ""),
    #             "comments": [c.get("text") for c in item.get("comments", []) if c.get("text")],
    #             "comment_count": item.get("commentsCount", 0)
    #         })
    # except Exception as e:
    #     print(f"Lỗi Apify: {e}")
    return posts

# -------------------------------------------------------------
# Hàm gom và xuất ra file raw_posts.json
# -------------------------------------------------------------
def main():
    all_posts = []
    
    # 1. Thu thập từ RSS quốc tế
    all_posts.extend(fetch_rss_feeds())
    
    # 2. Thu thập nghiên cứu mới PubMed
    all_posts.extend(fetch_pubmed_dental_research())
    
    # 3. Thu thập Facebook/TikTok (nếu có cấu hình)
    all_posts.extend(fetch_social_via_apify())
    
    # Nếu tất cả các nguồn cào trên đều rỗng (ví dụ rớt mạng), nạp dữ liệu dự phòng
    if not all_posts:
        print("-> Không lấy được dữ liệu động, nạp danh sách dự phòng...")
        all_posts = [
            {
                "text": "Bác sĩ cho em hỏi dạo này nhập phôi Zirconia Upcera hay bị sai lệch màu với mẻ rìa cắn sau khi nung không? Em nung lò Zubler đúng biểu đồ nhiệt mà vẫn dính 2 cầu răng liên tiếp.",
                "comments": [
                    "Bác kiểm tra lại lô phôi mới nhập xem, đợt này hàng trôi nổi nhiệt độ kết thiêu không chuẩn đâu.",
                    "Đổi qua dùng Lava Plus hoặc Cercon HT đi bác, đắt hơn chút nhưng an tâm hơn."
                ],
                "comment_count": 2
            }
        ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    print(f"-> Thu thập thành công {len(all_posts)} bài viết! Đã lưu vào {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
