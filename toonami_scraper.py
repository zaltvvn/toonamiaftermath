import requests
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Tắt cảnh báo bảo mật SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.toonamiaftermath.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Bảng cấu hình cố định (Chống lỗi API thay đổi)
CHANNEL_MAPS = {
    "Toonami Aftermath East": {"slug": "est", "sched": "Toonami Aftermath EST", "west": False},
    "Toonami Aftermath West": {"slug": "pst", "sched": "Toonami Aftermath EST", "west": True},
    "Snickelodeon East": {"slug": "snickelodeon-east", "sched": "Snickelodeon EST", "west": False},
    "Snickelodeon West": {"slug": "snickelodeon-west", "sched": "Snickelodeon EST", "west": True},
    "MTV97": {"slug": "mtv97", "sched": "MTV97", "west": False},
    "Movies": {"slug": "movies", "sched": "Movies", "west": False},
    "Toonami Aftermath Radio": {"slug": "radio", "sched": "Radio", "west": False},
    "Live Code": {"slug": "live-code", "sched": "Live Code", "west": False}
}

def get_current_time_rfc3339(offset_hours=0):
    dt = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def to_xmltv_time(date_str, minutes_add=0):
    if not date_str: return ""
    try:
        if date_str.endswith('Z'): date_str = date_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(date_str)
        if minutes_add: dt += timedelta(minutes=minutes_add)
        return dt.strftime('%Y%m%d%H%M%S +0000')
    except:
        return ""

def get_channels():
    url = f"{BASE_URL}/channelsCurrentMedia"
    params = {"startDate": get_current_time_rfc3339(offset_hours=-2)}
    try:
        res = requests.get(url, headers=HEADERS, params=params, verify=False, timeout=10)
        if res.status_code == 200: return res.json()
    except Exception as e:
        print(f"Lỗi tải kênh: {e}")
    return []

def get_schedule(schedule_name):
    url = f"{BASE_URL}/media"
    params = {
        "scheduleName": schedule_name, 
        "dateString": get_current_time_rfc3339(offset_hours=-3), 
        "count": 50, 
        "addBlockCard": "true"
    }
    try:
        res = requests.get(url, headers=HEADERS, params=params, verify=False, timeout=10)
        if res.status_code == 200: return res.json()
    except: pass
    return []

def main():
    print("🚀 BẮT ĐẦU CHẠY SCRIPT V3...")
    raw_channels = get_channels()
    
    # Đảm bảo dữ liệu là danh sách
    if isinstance(raw_channels, dict):
        raw_channels = raw_channels.get("channels") or raw_channels.get("data") or []

    if not raw_channels:
        print("❌ API không trả về kênh nào. Dừng lại!")
        return

    m3u_lines = ["#EXTM3U x-tvg-url=\"schedule.xml\""]
    xml_root = ET.Element("tv", {"generator-info-name": "Toonami Aftermath Automated Scraper V3"})

    for chan in raw_channels:
        name = chan.get("name") or chan.get("Name", "Unknown")
        if name not in CHANNEL_MAPS:
            continue # Bỏ qua kênh rác
            
        cfg = CHANNEL_MAPS[name]
        slug = cfg["slug"]
        m3u_url = f"http://api.toonamiaftermath.com:3000/{slug}/playlist.m3u8"

        # 1. Ghi file M3U
        m3u_lines.append(f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}" group-title="Toonami Aftermath", {name}')
        m3u_lines.append(m3u_url)

        # 2. Tạo XML Channel
        chan_el = ET.SubElement(xml_root, "channel", id=slug)
        ET.SubElement(chan_el, "display-name", lang="en").text = name

        # 3. Quét lịch chiếu
        schedule = get_schedule(cfg["sched"])
        if not schedule and "media" in chan:
            schedule = chan["media"] # Dùng lịch dự phòng từ API tổng

        if not schedule:
            schedule = [{"name": "Đang phát sóng", "startDate": get_current_time_rfc3339()}]

        for i, item in enumerate(schedule):
            title_text = item.get("name") or item.get("blockName") or "Chương trình trực tiếp"
            ep_num = item.get("episodeNumber", "")
            if item.get("isBlockCard"): title_text = f"[Bumper] {title_text}"
            
            start_str = item.get("startDate", "")
            start_time = to_xmltv_time(start_str)
            
            if i < len(schedule) - 1:
                stop_time = to_xmltv_time(schedule[i+1].get("startDate", ""))
            else:
                stop_time = to_xmltv_time(start_str, minutes_add=30)
                
            prog_el = ET.Element("programme", channel=slug)
            if start_time: prog_el.set("start", start_time)
            if stop_time: prog_el.set("stop", stop_time)
            ET.SubElement(prog_el, "title", lang="en").text = str(title_text)
            if ep_num: ET.SubElement(prog_el, "desc", lang="en").text = f"Tập {ep_num}"
            xml_root.append(prog_el)

    # LƯU FILE
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    
    tree = ET.ElementTree(xml_root)
    try: ET.indent(tree, space="  ", level=0)
    except: pass
    tree.write("schedule.xml", encoding="utf-8", xml_declaration=True)
    print("✨ ĐÃ LƯU DỮ LIỆU THÀNH CÔNG!")

if __name__ == "__main__":
    main()
