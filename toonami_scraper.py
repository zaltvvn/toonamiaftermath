import requests
import urllib3
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.toonamiaftermath.com"
# Bổ sung thêm nhiều Header để giả dạng trình duyệt thật giống nhất có thể
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.toonamiaftermath.com",
    "Referer": "https://www.toonamiaftermath.com/"
}

def get_val(d, *keys, default=None):
    if not isinstance(d, dict): return default
    for k in keys:
        if k in d and d[k] is not None:
            if isinstance(d[k], str) and not d[k]: continue
            return d[k]
    return default

def get_current_time_rfc3339(offset_hours=0):
    dt = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def get_channels():
    url = f"{BASE_URL}/channelsCurrentMedia"
    params = {"startDate": get_current_time_rfc3339(offset_hours=-2)}
    
    print(f"🔍 Đang gọi API lấy kênh: {url}")
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    
    print(f"HTTP Status: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print("✅ DỮ LIỆU TRẢ VỀ TỪ API:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000]) # In ra 1000 ký tự đầu để xem
            return data
        except Exception as e:
            print(f"❌ Lỗi đọc JSON: {e}")
            print(f"Nội dung thô: {response.text}")
    else:
        print(f"❌ Lỗi máy chủ từ chối: {response.text}")
    return []

def get_stream_url(slug, is_west=False):
    url = f"{BASE_URL}/streamUrl"
    params = {"channelName": slug, "timezoneOffset": "5", "useHttps": "true"}
    if is_west: params["streamDelay"] = "180" 
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    
    if response.status_code == 200:
        return response.text.strip().strip('"')
    else:
        print(f"❌ Lỗi lấy stream cho {slug}: HTTP {response.status_code}")
    return ""

def main():
    print("🚀 BẮT ĐẦU CHẠY SCRIPT...")
    channels = get_channels()
    
    # Xử lý trường hợp API trả về thông báo lỗi dạng Dictionary thay vì List kênh
    if isinstance(channels, dict):
        if "channels" in channels:
            channels = channels["channels"]
        elif "data" in channels:
            channels = channels["data"]
        else:
            print("❌ API trả về một Object không chứa kênh. Dừng lại.")
            return

    if not channels or not isinstance(channels, list):
        print("❌ Không có danh sách kênh hợp lệ. Dừng tiến trình.")
        return

    m3u_lines = ["#EXTM3U x-tvg-url=\"schedule.xml\""]
    xml_root = ET.Element("tv", {"generator-info-name": "Toonami Aftermath Automated Scraper"})

    # Quét danh sách kênh
    for channel in channels:
        name = get_val(channel, "name", "Name", default="Unknown")
        slug = get_val(channel, "slug", "Slug")
        is_west = get_val(channel, "westOffset", "WestOffset", default=False)
        
        if not slug:
            print(f"⚠️ Bỏ qua kênh '{name}' vì không có Slug.")
            continue
        
        m3u_url = get_stream_url(slug, is_west)
        print(f"🔗 Kênh {name} -> URL: {m3u_url}")
        
        if not m3u_url.startswith("http"):
            print(f"⚠️ Bỏ qua kênh '{name}' vì link stream không hợp lệ!")
            continue

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}" group-title="Toonami Aftermath", {name}')
        m3u_lines.append(m3u_url)

        chan_el = ET.SubElement(xml_root, "channel", id=slug)
        ET.SubElement(chan_el, "display-name", lang="en").text = name

        # Tạo thẻ programme trống để đảm bảo file XML không bị trắng
        prog_el = ET.Element("programme", channel=slug)
        prog_el.set("start", "20260101000000 +0000")
        prog_el.set("stop", "20260101003000 +0000")
        ET.SubElement(prog_el, "title", lang="en").text = "Lịch chiếu đang cập nhật..."
        xml_root.append(prog_el)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    tree = ET.ElementTree(xml_root)
    try: ET.indent(tree, space="  ", level=0)
    except: pass
    tree.write("schedule.xml", encoding="utf-8", xml_declaration=True)
    print("✨ TẠO FILE THÀNH CÔNG!")

if __name__ == "__main__":
    main()
