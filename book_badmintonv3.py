import requests
import json
import time
import argparse
from datetime import date, timedelta
import traceback # 引入 traceback 模块

# --- 配置 (保持不变) ---
BASE_URL = "http://wechatmeeting.nuist.edu.cn"
DEFAULT_EVENT_ID = "b8d2f7e00603f0f5af4de278c0b461b8"
DEFAULT_AUTH_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJub3ciOjE3NDQzMjk4MjksImV4cCI6MTc0NDMzMzQyOSwidCI6IjIwMjExMzYzMDEyMyIsInR0Ijoid2VjaGF0X3F5In0.MoS7CEWA73dUTSgPzMTwPIaAGtm9dlYSxoPOR_XZEYI"
DEFAULT_TARGET_DATE = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

# --- 函数定义 (build_headers, get_slot_details, book_court 基本不变) ---
def build_headers(token):
    """根据传入的 token 构建请求头"""
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
        'Referer': f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={DEFAULT_EVENT_ID}',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': f'token={token}'
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
        response.raise_for_status() # 检查 HTTP 错误
        data = response.json()
        if data.get('status') != 0:
            print(f"[!] 查询API返回错误: status={data.get('status')}, message={data.get('message', '无消息')}")
            return None
        print(f"[+] 查询成功 (HTTP {response.status_code})")
        return data
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

# --- 修改查找函数以查找所有可用的偏好 ---
def find_all_available_preferred_slots(slot_data, target_date, preferred_courts, preferred_times):
    """
    在返回的数据中查找 *所有* 满足偏好列表（场地和时间）的可预约时段。
    Returns:
        list: 包含所有可预约时段的 slot_details 字典的列表，如果找不到则返回空列表。
    """
    available_slots = [] # 用于存储找到的可预约时段
    if not slot_data or slot_data.get('status') != 0:
        print("[!] 时段数据无效或包含错误，无法查找。")
        return available_slots # 返回空列表

    resources = slot_data.get('data', {}).get('list', [])
    if not resources:
        print("[!] 未找到任何场地资源。")
        return available_slots

    print(f"[*] 开始按偏好查找 *所有* 可预约时段...")
    print(f"[*]   偏好场地: {', '.join(preferred_courts)}")
    print(f"[*]   偏好时段 (开始时间): {', '.join(preferred_times)}")

    # 遍历偏好场地
    for court_name in preferred_courts:
        resource_found = False
        for resource in resources:
            if resource.get('name') == court_name:
                resource_found = True
                print(f"[*]   正在检查场地: {court_name} (ID: {resource.get('id')})")
                slot_info_list = resource.get('slotInfo', [])
                # 遍历偏好时间
                for start_time in preferred_times:
                    for slot in slot_info_list:
                        if slot.get('startTime') == start_time:
                            slot_end_time = slot.get('endTime', '未知')
                            display_time = f"{start_time}-{slot_end_time}"
                            # 检查状态是否可预约 (status == 0)
                            if slot.get('status') == 0:
                                print(f"[+++]     发现可预约偏好: {court_name} {display_time}!")
                                slot_details = {
                                    "bookDate": target_date,
                                    "bookSlotId": slot.get('slotId'),
                                    "bookSlot": display_time,
                                    "number": 1,
                                    "price": "",
                                    "resourceId": resource.get('id'),
                                    "slotOrder": slot.get('slotOrder'),
                                    "seatId": "",
                                    "scheduleId": slot.get('scheduleId'),
                                    "resourceName": court_name
                                }
                                available_slots.append(slot_details) # 添加到列表中
                            # else: # 不需要打印不可预约的信息，避免过多日志
                            #    print(f"[-]       时段 {display_time} 状态为 {slot.get('status')}，不可预约。")
                            # 找到匹配的时间后，不再检查该场地的其他 slot (因为 slotId 是唯一的)
                            break
                break # 找到当前 court_name 对应的 resource 后跳出 resource 循环
        if not resource_found:
             print(f"[!]   未在查询结果中找到场地: {court_name}")

    if not available_slots:
        print("[-] 未找到任何满足偏好的可预约时段。")

    return available_slots # 返回找到的所有可预约时段列表

def book_court(slot_to_book, event_id, headers):
    """发送单次预约请求 (基本不变)"""
    booking_url = f"{BASE_URL}/api/v2/appBookGeneral/book/afterConfirm"
    payload = {
        "eventId": event_id,
        "extAttr": "",
        "payAmount": 0,
        "records": [slot_to_book] # 只发送单个 record
    }
    target_info = f"{slot_to_book['resourceName']} {slot_to_book['bookSlot']}" # 提取目标信息
    print(f"\n[*] 准备发送预约请求 (目标: {target_info})...")
    try:
        response = requests.post(booking_url, headers=headers, json=payload, timeout=15)
        result = response.json()
        print(f"\n[*] 收到预约响应 (目标: {target_info}, HTTP {response.status_code}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get('status') == 0:
            print(f"[+++] 成功预约: {target_info}!")
            # ... (打印 booking_id 和 result_url 的代码) ...
            return True # 成功
        else:
            print(f"[-] 预约失败 ({target_info}): {result.get('message', '无错误信息')}")
            # ... (Token 失效等提示) ...
            return False # 失败
    except requests.exceptions.Timeout:
        print(f"[!] 预约请求超时 ({target_info})。")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[!] 发送预约请求失败 ({target_info}): {e}")
        if e.response is not None and e.response.status_code in [401, 403]:
             print("[!] 预约请求失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
        return False
    except json.JSONDecodeError:
        print(f"[!] 预约失败 ({target_info}): 无法解析 JSON 响应 - {response.text[:200]}...")
        return False

# --- 主程序 ---
if __name__ == "__main__":
    # --- 参数解析部分 (与上一版相同，支持多选 --time 和 --court) ---
    parser = argparse.ArgumentParser(description="羽毛球场馆自动预约脚本 (支持多偏好)", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-tk", "--token",
                        help="有效的认证 JWT Token。\n"
                             "如果未提供，将使用内置的默认 Token。\n"
                             f"内置默认 Token: {DEFAULT_AUTH_TOKEN[:15]}...{DEFAULT_AUTH_TOKEN[-15:]}\n")
    parser.add_argument("-d", "--date", default=DEFAULT_TARGET_DATE, help=f"目标预约日期 (格式: YYYY-MM-DD)，默认为明天 ({DEFAULT_TARGET_DATE})")
    parser.add_argument("-t", "--time", nargs='+', default=["10:00"],
                        help="偏好的预约时段开始时间列表 (格式: HH:MM)，用空格分隔。\n"
                             "例如: --time 10:00 11:00 14:00\n"
                             "默认为 '10:00'")
    parser.add_argument("-c", "--court", nargs='+', default=["场地1"],
                        help="偏好的场地名称列表，用空格分隔 (如果名称含空格需加引号)。\n"
                             "例如: --court 场地1 场地2 \"场地 5\"\n"
                             "默认为 '场地1'")
    parser.add_argument("-e", "--event", default=DEFAULT_EVENT_ID, 
                        help=f"预约项目的 Event ID，默认为默认为教职工羽毛球场 ({DEFAULT_EVENT_ID}) 常见值: \n"
                             "教职工羽毛球场 (b8d2f7e00603f0f5af4de278c0b461b8) \n"
                             "体育馆二楼羽毛球场 (fc5379ac197b421940fffa4c99723e11)"
                        )
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="每次查询循环的间隔时间（秒），默认为 1.0 秒")
    # 新增参数：控制是否只约一个就退出
    parser.add_argument("--book-all", action="store_true",
                        help="如果设置此标志，脚本会尝试预约找到的所有可用偏好时段，而不是只预约第一个。 \n"
                        "注意：这仍受限于系统的预约规则（如最大未使用数）。")

    args = parser.parse_args()

    # --- Token 决策逻辑 (与上一版相同) ---
    if args.token:
        auth_token = args.token
        token_source = "命令行提供"
    else:
        auth_token = DEFAULT_AUTH_TOKEN
        token_source = "内置默认"
        if not auth_token:
             print("[!] 错误：未通过命令行提供 Token，且内置的默认 Token 也为空！请必须提供一个有效的 Token。")
             exit(1)

    target_date = args.date
    preferred_times = args.time
    preferred_courts = args.court
    event_id = args.event
    interval = args.interval
    book_all_mode = args.book_all # 获取新参数的值

    # --- 打印启动信息 (与上一版相同，但加上 book_all 模式) ---
    print(f"--- 开始预约脚本 ({date.today()}) ---")
    print(f"[*] 目标日期: {target_date}")
    print(f"[*] 偏好场地: {', '.join(preferred_courts)}")
    print(f"[*] 偏好时段: {', '.join(preferred_times)}")
    print(f"[*] Event ID: {event_id}")
    print(f"[*] 查询间隔: {interval} 秒")
    print(f"[*] 预约模式: {'尝试预约所有找到的可用偏好' if book_all_mode else '预约找到的第一个可用偏好后停止'}")
    print(f"[*] 使用 Token 来源: {token_source}")
    print(f"[*] 使用 Token: {auth_token[:15]}...{auth_token[-15:]}")

    try:
        headers = build_headers(auth_token)
    except ValueError as e:
        print(f"[!] 错误: {e}")
        exit(1)

    # --- 开始循环尝试 ---
    successful_bookings = 0 # 记录成功预约的数量
    try:
        while True:
            print(f"\n--- 开始新一轮查询 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
            # 1. 查询时段信息
            slot_details_data = get_slot_details(target_date, event_id, headers)

            if slot_details_data:
                # 2. 查找 *所有* 可用的偏好时段
                available_preferred_slots = find_all_available_preferred_slots(
                    slot_details_data,
                    target_date,
                    preferred_courts,
                    preferred_times
                )

                if available_preferred_slots:
                    print(f"[***] 找到 {len(available_preferred_slots)} 个满足偏好的可预约时段，将尝试预约...")
                    booked_in_this_round = False # 标记本轮是否有成功预约
                    # 3. 遍历找到的可预约时段列表，尝试逐个预约
                    for slot_to_book in available_preferred_slots:
                        # 在尝试预约前短暂延时，避免太快被服务器拒绝 (可选)
                        # time.sleep(0.1)
                        if book_court(slot_to_book, event_id, headers):
                            successful_bookings += 1
                            booked_in_this_round = True
                            # 如果不是 book-all 模式，预约成功一个就退出脚本
                            if not book_all_mode:
                                print("\n[***] 已成功预约一个时段，脚本停止。 [***]")
                                exit(0) # 正常退出
                        # else: # 预约失败，继续尝试列表中的下一个 (如果还有)
                        #    pass

                    # 如果是 book-all 模式，并且本轮至少成功预约了一个，通常也意味着任务完成
                    if book_all_mode and booked_in_this_round:
                         print(f"\n[***] 已尝试预约所有找到的可用时段，本轮成功 {successful_bookings} 个。脚本停止。 [***]")
                         exit(0)
                    elif not booked_in_this_round:
                         print("[-] 本轮尝试预约找到的时段均失败，可能是瞬间被抢或规则限制。")

                # else: # find_all... 函数内部已打印未找到的消息
                #    pass

            else:
                print("[!] 获取场地信息失败，可能是网络或 Token 问题。")

            # 如果脚本因为没有成功预约而仍在运行，等待指定间隔时间
            print(f"[*] 等待 {interval} 秒后进行下一轮查询...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[!] 检测到 Ctrl+C，用户手动停止脚本。")
    except SystemExit: # 捕获 exit(0) 以正常结束
        pass
    except Exception as e:
        print(f"\n[!!!] 脚本遇到未处理的错误: {e}")
        traceback.print_exc()
    finally:
        print(f"--- 预约脚本执行结束 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
        print(f"[*] 总计成功预约 {successful_bookings} 个时段。")