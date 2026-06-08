import requests
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Tắt cảnh báo bảo mật khi bỏ qua kiểm tra SSL (để log hiển thị sạch đẹp)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.toonamiaftermath.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get_current_time_rfc3339(offset_hours=0):
    """Tạo chuỗi thời gian chuẩn RFC3339 để gửi lên API"""
    dt = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def to_xmltv_time(date_str, minutes_add=0):
    """Chuyển đổi thời gian từ API thành định dạng XMLTV (YYYYMMDDHHMMSS +0000)"""
    if not date_str:
        return ""
    try:
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(date_str)
        if minutes_add:
            dt += timedelta(minutes=minutes_add)
        return dt.strftime('%Y%m%d%H%M%S +0000')
    except:
        return ""

def get_channels():
    """Lấy danh sách các kênh"""
    start_date = get_current_time_rfc3339(offset_hours=-2)
    url = f"{BASE_URL}/channelsCurrentMedia"
    params = {"startDate": start_date}
    # Thêm verify=False để bỏ qua lỗi chứng chỉ SSL
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    return response.json() if response.status_code == 200 else []

def get_stream_url(slug, is_west=False):
    """Lấy link stream M3U8 trực tiếp"""
    url = f"{BASE_URL}/streamUrl"
    params = {"channelName": slug, "timezoneOffset": "5", "useHttps": "true"}
    if is_west:
        params["streamDelay"] = "180" 
    # Thêm verify=False để bỏ qua lỗi chứng chỉ SSL
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    return response.text.strip() if response.status_code == 200 else ""

def get_schedule(schedule_name, count=50):
    """Lấy lịch phát sóng"""
    sched_name = schedule_name.replace("East", "EST").replace("West", "EST")
    date_string = get_current_time_rfc3339(offset_hours=-3)
    url = f"{BASE_URL}/media"
    params = {"scheduleName": sched_name, "dateString": date_string, "count": count, "addBlockCard": "true"}
    # Thêm verify=False để bỏ qua lỗi chứng chỉ SSL
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    return response.json() if response.status_code == 200 else []

def main():
    print("🚀 Đang khởi tạo quá trình quét dữ liệu Toonami Aftermath...")
    channels = get_channels()
    if not channels:
        print("❌ Không lấy được danh sách kênh. Dừng tiến trình.")
        return

    # --- KHỞI TẠO CẤU TRÚC FILE ---
    m3u_lines = ["#EXTM3U x-tvg-url=\"schedule.xml\""]
    
    # Khởi tạo XMLTV gốc
    xml_root = ET.Element("tv", {"generator-info-name": "Toonami Aftermath Automated Scraper"})

    # Bước 1: Định nghĩa danh sách kênh
    for channel in channels:
        name = channel.get("Name", "Unknown")
        slug = channel.get("Slug")
        if not slug:
            continue
        
        is_west = channel.get("WestOffset", False)
        m3u_url = get_stream_url(slug, is_west)
        
        if not m3u_url.startswith("http"):
            continue

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}" group-title="Toonami Aftermath", {name}')
        m3u_lines.append(m3u_url)

        chan_el = ET.SubElement(xml_root, "channel", id=slug)
        display_name = ET.SubElement(chan_el, "display-name", lang="en")
        display_name.text = name

    # Bước 2: Quét lịch phát sóng
    for channel in channels:
        name = channel.get("Name", "Unknown")
        slug = channel.get("Slug")
        if not slug:
            continue

        print(f"📅 Đang tải lịch chiếu cho kênh: {name}...")
        schedule = get_schedule(name, count=50)
        
        for i, item in enumerate(schedule):
            title_text = item.get("Name") or item.get("BlockName") or "Unknown Show"
            episode_num = item.get("EpisodeNumber")
            is_block_card = item.get("IsBlockCard", False)
            
            if is_block_card:
                title_text = f"[Bumper] {title_text}"
                
            start_str = item.get("StartDate", "")
            start_time = to_xmltv_time(start_str)
            
            if i < len(schedule) - 1:
                stop_time = to_xmltv_time(schedule[i+1].get("StartDate", ""))
            else:
                stop_time = to_xmltv_time(start_str, minutes_add=30)
                
            prog_el = ET.Element("programme", channel=slug)
            if start_time: prog_el.set("start", start_time)
            if stop_time: prog_el.set("stop", stop_time)
            
            title_el = ET.SubElement(prog_el, "title", lang="en")
            title_el.text = title_text
            
            if episode_num:
                desc_el = ET.SubElement(prog_el, "desc", lang="en")
                desc_el.text = f"Tập {episode_num}"
                
            xml_root.append(prog_el)

    # --- GHI DỮ LIỆU RA FILE ---
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print("💾 Đã lưu file playlist.m3u")

    tree = ET.ElementTree(xml_root)
    try:
        ET.indent(tree, space="  ", level=0)
    except:
        pass
    tree.write("schedule.xml", encoding="utf-8", xml_declaration=True)
    print("💾 Đã lưu file schedule.xml")
    print("✨ Hoàn thành tất cả tác vụ!")

if __name__ == "__main__":
    main()
