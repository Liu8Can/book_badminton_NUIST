import requests
import json
import time
import argparse
from datetime import date, timedelta

# 示例例命令 # 预约 2025-04-15，下午 14:00 开始的时段，场地3，间隔 0.5 秒 python book_badminton.py --token "你的Token" --date "2025-04-15" --time "14:00" --court "场地3" --interval 0.5
# 本代码 token 值为必要参数

# --- 配置 ---
BASE_URL = "http://wechatmeeting.nuist.edu.cn"
# Event ID 通常是固定的，代表特定的预约项目
DEFAULT_EVENT_ID = "b8d2f7e00603f0f5af4de278c0b461b8"

# --- 动态计算默认日期 (明天) ---
DEFAULT_TARGET_DATE = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

def build_headers(token):
    """根据传入的 token 构建请求头"""
    return {
        'Host': 'wechatmeeting.nuist.edu.cn',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.51 PythonAutomationScript/1.0',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': BASE_URL,
        'X-Requested-With': 'com.tencent.mm',
        'Referer': f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={DEFAULT_EVENT_ID}', # Referer 通常用默认 Event ID
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': f'token={token}' # 关键认证 Cookie
    }

def get_slot_details(target_date, event_id, headers):
    """获取指定日期的场地时段信息"""
    search_url = f"{BASE_URL}/api/v2/appBookGeneral/date/slot/searchByDate"
    payload = {
        "date": target_date,
        "eventId": event_id
    }
    print(f"[*] 正在查询日期 {target_date} 的场地时段信息...")
    try:
        response = requests.post(search_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print(f"[+] 查询成功 (HTTP {response.status_code})")
        return response.json()
    except requests.exceptions.Timeout:
        print(f"[!] 查询时段信息超时。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[!] 查询时段信息失败: {e}")
        return None
    except json.JSONDecodeError:
        print(f"[!] 查询时段信息失败: 无法解析 JSON 响应 - {response.text[:200]}...")
        return None

def find_target_slot(slot_data, target_date, target_resource_name, target_slot_start_time):
    """在返回的数据中查找目标场地和时段"""
    if not slot_data or slot_data.get('status') != 0:
        print("[!] 获取到的时段数据无效或包含错误。")
        return None, None # 返回 None, None 表示查找失败

    resources = slot_data.get('data', {}).get('list', [])
    if not resources:
        print("[!] 未找到任何场地资源。")
        return None, None

    target_slot_display_time = f"{target_slot_start_time}-未知结束时间" # 初始显示

    print(f"[*] 开始查找 {target_resource_name} 的 {target_slot_start_time} 开始的时段...")
    for resource in resources:
        if resource.get('name') == target_resource_name:
            print(f"[*] 找到场地: {resource.get('name')} (ID: {resource.get('id')})")
            slot_info_list = resource.get('slotInfo', [])
            for slot in slot_info_list:
                if slot.get('startTime') == target_slot_start_time:
                    slot_end_time = slot.get('endTime', '未知')
                    target_slot_display_time = f"{slot.get('startTime')}-{slot_end_time}"
                    print(f"[*]   找到时段: {target_slot_display_time} (SlotID: {slot.get('slotId')})")
                    if slot.get('status') == 0:
                        print(f"[+]   该时段可预约!")
                        # 返回构造预约请求所需的信息和用于显示的具体时间段
                        slot_details_for_booking = {
                            "bookDate": target_date,
                            "bookSlotId": slot.get('slotId'),
                            "bookSlot": target_slot_display_time, # 使用找到的完整时间
                            "number": 1,
                            "price": "",
                            "resourceId": resource.get('id'),
                            "slotOrder": slot.get('slotOrder'),
                            "seatId": "",
                            "scheduleId": slot.get('scheduleId'),
                            "resourceName": resource.get('name')
                        }
                        return slot_details_for_booking, target_slot_display_time
                    else:
                        print(f"[-]   该时段状态为 {slot.get('status')} (bookedNums: {slot.get('bookedNums')})，不可预约。")
                        return None, target_slot_display_time # 找到了但不可预约
            print(f"[!] 未在 {target_resource_name} 找到 {target_slot_start_time} 开始的时段。")
            return None, None # 在这个场地没找到目标时段
    print(f"[!] 未找到名为 {target_resource_name} 的场地。")
    return None, None # 没找到目标场地

def book_court(slot_to_book, event_id, headers):
    """发送预约请求"""
    booking_url = f"{BASE_URL}/api/v2/appBookGeneral/book/afterConfirm"
    payload = {
        "eventId": event_id,
        "extAttr": "",
        "payAmount": 0,
        "records": [slot_to_book]
    }
    print(f"\n[*] 准备发送预约请求 (目标: {slot_to_book['resourceName']} {slot_to_book['bookSlot']})...")
    # print(f"[*] 请求体 (Payload):")
    # print(json.dumps(payload, indent=2, ensure_ascii=False)) # 调试时可以取消注释

    try:
        response = requests.post(booking_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        print(f"\n[*] 收到预约响应 (HTTP {response.status_code}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get('status') == 0:
            print("[+] 预约成功!")
            booking_id = result.get('extdata', {}).get('id')
            result_url = result.get('data')
            if booking_id:
                 print(f"[*] 预约记录 ID (bookMineId): {booking_id}")
            if result_url:
                 print(f"[*] 预约结果页面 URL: {result_url}")
            return True # 成功
        else:
            print(f"[-] 预约失败: {result.get('message', '无错误信息')}")
            if 'extdata' in result and result['extdata']:
                 print(f"[-] 附加错误数据: {result['extdata']}")
            return False # 失败

    except requests.exceptions.Timeout:
        print("[!] 预约请求超时。")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[!] 发送预约请求失败: {e}")
        # 如果是认证失败 (e.g., 401 Unauthorized or response indicates token error)
        if response and response.status_code in [401, 403]:
             print("[!] 认证失败，请检查 Token 是否有效或过期。")
        # 你可以根据实际的错误响应添加更具体的处理
        return False
    except json.JSONDecodeError:
        print(f"[!] 预约失败: 无法解析 JSON 响应 - {response.text[:200]}...")
        return False

# --- 主程序 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="羽毛球场馆自动预约脚本")
    parser.add_argument("-tk", "--token", required=True, help="[必需] 有效的认证 JWT Token")
    parser.add_argument("-d", "--date", default=DEFAULT_TARGET_DATE, help=f"目标预约日期 (格式: YYYY-MM-DD)，默认为明天 ({DEFAULT_TARGET_DATE})")
    parser.add_argument("-t", "--time", default="10:00", help="目标预约时段的开始时间 (格式: HH:MM)，默认为 '10:00'")
    parser.add_argument("-c", "--court", default="场地1", help="目标场地名称 (例如: '场地1'), 默认为 '场地1'")
    parser.add_argument("-e", "--event", default=DEFAULT_EVENT_ID, help=f"预约项目的 Event ID，默认为教职工羽毛球场 ({DEFAULT_EVENT_ID})")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="每次尝试预约的间隔时间（秒），默认为 1.0 秒")

    args = parser.parse_args()

    # 使用解析后的参数
    auth_token = args.token
    target_date = args.date
    target_slot_start_time = args.time
    target_resource_name = args.court
    event_id = args.event
    interval = args.interval

    # 构建固定的请求头
    headers = build_headers(auth_token)

    print(f"--- 开始预约脚本 ({date.today()}) ---")
    print(f"[*] 目标日期: {target_date}")
    print(f"[*] 目标场地: {target_resource_name}")
    print(f"[*] 目标开始时间: {target_slot_start_time}")
    print(f"[*] Event ID: {event_id}")
    print(f"[*] 尝试间隔: {interval} 秒")
    print(f"[*] 使用 Token: {auth_token[:15]}...{auth_token[-15:]}") # 仅显示部分 Token

    try:
        while True:
            print(f"\n--- 开始新一轮尝试 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
            # 1. 查询时段信息
            slot_details_data = get_slot_details(target_date, event_id, headers)

            if slot_details_data:
                # 2. 查找目标时段
                target_slot_for_booking, display_time = find_target_slot(
                    slot_details_data,
                    target_date,
                    target_resource_name,
                    target_slot_start_time
                )

                if target_slot_for_booking:
                    # 3. 尝试预约
                    if book_court(target_slot_for_booking, event_id, headers):
                        print("\n[***] 成功预约到目标场地和时段！脚本结束。 [***]")
                        break # 预约成功，跳出循环
                    else:
                        print("[-] 本次预约尝试失败，稍后重试...")
                elif display_time: # 找到了时段但不可预约
                     print(f"[-] 目标时段 ({display_time}) 当前不可预约，稍后重试...")
                else: # 未找到场地或时段
                     print("[!] 未找到目标场地或时段，请检查参数是否正确。稍后重试...")

            else:
                print("[!] 获取场地信息失败，稍后重试...")

            # 等待指定间隔时间
            print(f"[*] 等待 {interval} 秒后重试...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[!] 检测到 Ctrl+C，用户手动停止脚本。")
    except Exception as e:
        print(f"\n[!!!] 脚本遇到未处理的错误: {e}")
    finally:
        print(f"--- 预约脚本执行结束 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")