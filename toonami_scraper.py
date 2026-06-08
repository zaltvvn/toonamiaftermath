import requests
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Tắt cảnh báo bảo mật khi bỏ qua kiểm tra SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.toonamiaftermath.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get_val(d, *keys, default=None):
    """Hàm hỗ trợ lấy giá trị từ JSON không phân biệt chữ hoa/chữ thường của key"""
    for k in keys:
        if k in d and d[k] is not None:
            if isinstance(d[k], str) and not d[k]: # Bỏ qua nếu là chuỗi rỗng
                continue
            return d[k]
    return default

def get_current_time_rfc3339(offset_hours=0):
    dt = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def to_xmltv_time(date_str, minutes_add=0):
    if not date_str: return ""
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
    url = f"{BASE_URL}/channelsCurrentMedia"
    params = {"startDate": get_current_time_rfc3339(offset_hours=-2)}
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Đã tải được {len(data)} kênh từ API.")
        return data
    print(f"❌ Lỗi tải kênh: HTTP {response.status_code}")
    return []

def get_stream_url(slug, is_west=False):
    url = f"{BASE_URL}/streamUrl"
    params = {"channelName": slug, "timezoneOffset": "5", "useHttps": "true"}
    if is_west:
        params["streamDelay"] = "180" 
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    if response.status_code == 200:
        # Xóa dấu khoảng trắng và dấu ngoặc kép (nếu có) bị thừa từ API
        return response.text.strip().strip('"')
    return ""

def get_schedule(schedule_name, count=50):
    sched_name = schedule_name.replace("East", "EST").replace("West", "EST")
    url = f"{BASE_URL}/media"
    params = {
        "scheduleName": sched_name, 
        "dateString": get_current_time_rfc3339(offset_hours=-3), 
        "count": count, 
        "addBlockCard": "true"
    }
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    return response.json() if response.status_code == 200 else []

def main():
    print("🚀 Đang khởi tạo quá trình quét dữ liệu Toonami Aftermath...")
    channels = get_channels()
    if not channels:
        print("❌ Không lấy được danh sách kênh. Dừng tiến trình.")
        return

    m3u_lines = ["#EXTM3U x-tvg-url=\"schedule.xml\""]
    xml_root = ET.Element("tv", {"generator-info-name": "Toonami Aftermath Automated Scraper"})

    # Bước 1: Quét danh sách kênh
    for channel in channels:
        name = get_val(channel, "name", "Name", default="Unknown")
        slug = get_val(channel, "slug", "Slug")
        is_west = get_val(channel, "westOffset", "WestOffset", default=False)
        
        if not slug:
            print(f"⚠️ Bỏ qua kênh '{name}' vì không tìm thấy mã Slug.")
            continue
        
        m3u_url = get_stream_url(slug, is_west)
        if not m3u_url.startswith("http"):
            print(f"⚠️ Bỏ qua kênh '{name}' vì link stream không hợp lệ: {m3u_url}")
            continue

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}" group-title="Toonami Aftermath", {name}')
        m3u_lines.append(m3u_url)

        chan_el = ET.SubElement(xml_root, "channel", id=slug)
        display_name = ET.SubElement(chan_el, "display-name", lang="en")
        display_name.text = name

    # Bước 2: Quét lịch phát sóng
    for channel in channels:
        name = get_val(channel, "name", "Name", default="Unknown")
        slug = get_val(channel, "slug", "Slug")
        if not slug:
            continue

        print(f"📅 Đang tải lịch chiếu cho kênh: {name}...")
        schedule = get_schedule(name, count=50)
        
        for i, item in enumerate(schedule):
            title_text = get_val(item, "name", "Name", "blockName", "BlockName", default="Unknown Show")
            episode_num = get_val(item, "episodeNumber", "EpisodeNumber")
            is_block_card = get_val(item, "isBlockCard", "IsBlockCard", default=False)
            start_str = get_val(item, "startDate", "StartDate", default="")
            
            if is_block_card:
                title_text = f"[Bumper] {title_text}"
                
            start_time = to_xmltv_time(start_str)
            
            if i < len(schedule) - 1:
                next_start_str = get_val(schedule[i+1], "startDate", "StartDate", default="")
                stop_time = to_xmltv_time(next_start_str)
            else:
                stop_time = to_xmltv_time(start_str, minutes_add=30)
                
            prog_el = ET.Element("programme", channel=slug)
            if start_time: prog_el.set("start", start_time)
            if stop_time: prog_el.set("stop", stop_time)
            
            title_el = ET.SubElement(prog_el, "title", lang="en")
            title_el.text = str(title_text)
            
            if episode_num:
                desc_el = ET.SubElement(prog_el, "desc", lang="en")
                desc_el.text = f"Tập {episode_num}"
                
            xml_root.append(prog_el)

    # Ghi file
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
