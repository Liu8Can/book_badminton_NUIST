import requests
import json
import time
import argparse
from datetime import date, timedelta

# 示例命令 python book_badmintonv2.py --date "2025-04-11" --time "08:00" --court "场地2" --interval 0.5
# 本代码 token 值为可选参数

# --- 配置 ---
BASE_URL = "http://wechatmeeting.nuist.edu.cn"
# Event ID 通常是固定的，代表特定的预约项目
DEFAULT_EVENT_ID = "b8d2f7e00603f0f5af4de278c0b461b8"

# --- 添加默认 Token ---
# !!! 注意：这个默认 Token 仍然会过期，如果脚本运行失败提示认证错误，你需要更新这个值，或者通过命令行传入新 Token !!!
DEFAULT_AUTH_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJub3ciOjE3NDQzMjk4MjksImV4cCI6MTc0NDMzMzQyOSwidCI6IjIwMjExMzYzMDEyMyIsInR0Ijoid2VjaGF0X3F5In0.MoS7CEWA73dUTSgPzMTwPIaAGtm9dlYSxoPOR_XZEYI" # <--- 使用你之前提供的 Token 作为默认值

# --- 动态计算默认日期 (明天) ---
DEFAULT_TARGET_DATE = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

def build_headers(token):
    """根据传入的 token 构建请求头"""
    # 确保传入的 token 非空
    if not token:
        raise ValueError("Token 不能为空！")
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
        if e.response is not None and e.response.status_code in [401, 403]:
             print("[!] 查询失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
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
            # 检查是否是 Token 失效的特定错误消息（需要根据实际情况调整）
            if "token" in result.get('message', '').lower() or "登录" in result.get('message', ''):
                 print("[!] 预约失败：错误消息提示 Token 失效或需要登录。")
            return False # 失败

    except requests.exceptions.Timeout:
        print("[!] 预约请求超时。")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[!] 发送预约请求失败: {e}")
        if e.response is not None and e.response.status_code in [401, 403]:
             print("[!] 预约请求失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
        return False
    except json.JSONDecodeError:
        print(f"[!] 预约失败: 无法解析 JSON 响应 - {response.text[:200]}...")
        return False

# --- 主程序 ---
if __name__ == "__main__":
    # 使用 RawTextHelpFormatter 可以在 help 文本中保留换行符
    parser = argparse.ArgumentParser(description="羽毛球场馆自动预约脚本", formatter_class=argparse.RawTextHelpFormatter)
    # 修改 token 参数，不再强制要求，并在 help 中说明默认行为
    parser.add_argument("-tk", "--token",
                        help="有效的认证 JWT Token。\n"
                             "如果未提供此参数，脚本将使用内置的默认 Token。\n"
                             f"内置默认 Token: {DEFAULT_AUTH_TOKEN[:15]}...{DEFAULT_AUTH_TOKEN[-15:]}\n"
                             "如果默认 Token 失效，请务必通过此参数提供新的有效 Token。")
    parser.add_argument("-d", "--date", default=DEFAULT_TARGET_DATE, help=f"目标预约日期 (格式: YYYY-MM-DD)，默认为明天 ({DEFAULT_TARGET_DATE})")
    parser.add_argument("-t", "--time", default="10:00", help="目标预约时段的开始时间 (格式: HH:MM)，默认为 '10:00'")
    parser.add_argument("-c", "--court", default="场地1", help="目标场地名称 (例如: '场地1'), 默认为 '场地1'")
    parser.add_argument("-e", "--event", default=DEFAULT_EVENT_ID, help=f"预约项目的 Event ID，默认为教职工羽毛球场 ({DEFAULT_EVENT_ID})")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="每次尝试预约的间隔时间（秒），默认为 1.0 秒")

    args = parser.parse_args()

    # --- 决定使用哪个 Token ---
    if args.token:
        auth_token = args.token
        token_source = "命令行提供"
    else:
        auth_token = DEFAULT_AUTH_TOKEN
        token_source = "内置默认"
        # 检查默认 Token 是否为空（虽然我们已经硬编码了，但做个检查更健壮）
        if not auth_token:
             print("[!] 错误：未通过命令行提供 Token，且内置的默认 Token 也为空！请必须提供一个有效的 Token。")
             exit(1) # 没有 Token 无法继续，退出

    # 获取其他参数
    target_date = args.date
    target_slot_start_time = args.time
    target_resource_name = args.court
    event_id = args.event
    interval = args.interval

    # 打印启动信息
    print(f"--- 开始预约脚本 ({date.today()}) ---")
    print(f"[*] 目标日期: {target_date}")
    print(f"[*] 目标场地: {target_resource_name}")
    print(f"[*] 目标开始时间: {target_slot_start_time}")
    print(f"[*] Event ID: {event_id}")
    print(f"[*] 尝试间隔: {interval} 秒")
    print(f"[*] 使用 Token 来源: {token_source}")
    print(f"[*] 使用 Token: {auth_token[:15]}...{auth_token[-15:]}") # 仅显示部分 Token

    # 构建请求头 (必须在确定 auth_token 之后)
    try:
        headers = build_headers(auth_token)
    except ValueError as e:
        print(f"[!] 错误: {e}")
        exit(1)

    # --- 开始循环尝试 ---
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
                        # 预约失败，继续循环前稍作等待
                        print("[-] 本次预约尝试失败，稍后重试...")
                        # 这里可以根据失败原因决定是否继续循环，例如 Token 失效就应该停止
                        # 目前的逻辑是无论什么失败都继续尝试
                elif display_time: # 找到了时段但不可预约
                     print(f"[-] 目标时段 ({display_time}) 当前不可预约，稍后重试...")
                else: # 未找到场地或时段
                     print("[!] 未找到目标场地或时段，请检查参数是否正确。稍后重试...")

            else:
                # 获取场地信息失败，也可能是 Token 问题
                print("[!] 获取场地信息失败，稍后重试...")

            # 等待指定间隔时间
            print(f"[*] 等待 {interval} 秒后重试...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[!] 检测到 Ctrl+C，用户手动停止脚本。")
    except Exception as e:
        print(f"\n[!!!] 脚本遇到未处理的错误: {e}")
        import traceback
        traceback.print_exc() # 打印详细的错误堆栈信息
    finally:
        print(f"--- 预约脚本执行结束 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")