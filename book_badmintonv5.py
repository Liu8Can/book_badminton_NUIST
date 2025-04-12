import requests
import json
import time
import argparse
from datetime import date, timedelta, datetime, timezone
import traceback
import schedule
import re
import sys # 引入 sys 模块

# --- 配置 (保持不变) ---
BASE_URL = "http://wechatmeeting.nuist.edu.cn"
DEFAULT_EVENT_ID = "b8d2f7e00603f0f5af4de278c0b461b8"
DEFAULT_AUTH_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJub3ciOjE3NDQzMjk4MjksImV4cCI6MTc0NDMzMzQyOSwidCI6IjIwMjExMzYzMDEyMyIsInR0Ijoid2VjaGF0X3F5In0.MoS7CEWA73dUTSgPzMTwPIaAGtm9dlYSxoPOR_XZEYI" # 注意：Token 会过期
DEFAULT_TARGET_DATE = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
# 不再需要 DEFAULT_SCHEDULE_TIME

# --- 函数定义 (build_headers, get_slot_details, find_all_available_preferred_slots, book_court, validate_time_format 保持不变) ---
def build_headers(token):
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
        'Referer': f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={DEFAULT_EVENT_ID}', # 会在需要时被覆盖
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': f'token={token}'
    }

def get_slot_details(target_date, event_id, headers):
    search_url = f"{BASE_URL}/api/v2/appBookGeneral/date/slot/searchByDate"
    payload = {"date": target_date, "eventId": event_id}
    print(f"[*] 正在查询日期 {target_date} 的场地时段信息 (Event ID: {event_id})...")
    try:
        headers['Referer'] = f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={event_id}'
        response = requests.post(search_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
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

def find_all_available_preferred_slots(slot_data, target_date, preferred_courts, preferred_times):
    available_slots = []
    if not slot_data or slot_data.get('status') != 0:
        print("[!] 时段数据无效或包含错误，无法查找。")
        return available_slots
    resources = slot_data.get('data', {}).get('list', [])
    if not resources:
        print("[!] 未找到任何场地资源。")
        return available_slots
    print(f"[*] 开始按偏好查找 *所有* 可预约时段...")
    print(f"[*]   偏好场地: {', '.join(preferred_courts)}")
    print(f"[*]   偏好时段 (开始时间): {', '.join(preferred_times)}")
    for court_name in preferred_courts:
        resource_found = False
        for resource in resources:
            if resource.get('name') == court_name:
                resource_found = True
                print(f"[*]   正在检查场地: {court_name} (ID: {resource.get('id')})")
                slot_info_list = resource.get('slotInfo', [])
                for start_time in preferred_times:
                    for slot in slot_info_list:
                        if slot.get('startTime') == start_time:
                            slot_end_time = slot.get('endTime', '未知')
                            display_time = f"{start_time}-{slot_end_time}"
                            if slot.get('status') == 0:
                                print(f"[+++]     发现可预约偏好: {court_name} {display_time}!")
                                slot_details = {
                                    "bookDate": target_date, "bookSlotId": slot.get('slotId'),
                                    "bookSlot": display_time, "number": 1, "price": "",
                                    "resourceId": resource.get('id'), "slotOrder": slot.get('slotOrder'),
                                    "seatId": "", "scheduleId": slot.get('scheduleId'),
                                    "resourceName": court_name
                                }
                                available_slots.append(slot_details)
                            break
                break
        if not resource_found:
             print(f"[!]   未在查询结果中找到场地: {court_name}")
    if not available_slots:
        print("[-] 未找到任何满足偏好的可预约时段。")
    return available_slots

def book_court(slot_to_book, event_id, headers):
    booking_url = f"{BASE_URL}/api/v2/appBookGeneral/book/afterConfirm"
    payload = {"eventId": event_id, "extAttr": "", "payAmount": 0, "records": [slot_to_book]}
    target_info = f"{slot_to_book['resourceName']} {slot_to_book['bookSlot']}"
    print(f"\n[*] 准备发送预约请求 (目标: {target_info})...")
    try:
        headers['Referer'] = f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={event_id}'
        response = requests.post(booking_url, headers=headers, json=payload, timeout=15)
        result = response.json()
        print(f"\n[*] 收到预约响应 (目标: {target_info}, HTTP {response.status_code}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get('status') == 0:
            print(f"[+++] 成功预约: {target_info}!")
            return True
        else:
            print(f"[-] 预约失败 ({target_info}): {result.get('message', '无错误信息')}")
            if "认证失败" in result.get('message', '') or response.status_code in [401, 403]:
                print("[!] Token 可能已失效或无权限，请检查 Token。")
            return False
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

def validate_time_format(time_str):
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
        raise argparse.ArgumentTypeError(f"无效的时间格式: '{time_str}'. 请使用 HH:MM 格式 (例如: 08:04, 15:30)。")
    return time_str

# --- 主程序 ---
if __name__ == "__main__":
    # --- 参数解析部分 (修改 --schedule-time) ---
    parser = argparse.ArgumentParser(description="羽毛球场馆自动预约脚本 (支持定时执行和多偏好)", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-tk", "--token",
                        help="有效的认证 JWT Token。\n"
                             "如果未提供，将使用内置的默认 Token。\n"
                             f"内置默认 Token: {DEFAULT_AUTH_TOKEN[:15]}...{DEFAULT_AUTH_TOKEN[-15:]} (注意: Token 会过期)\n")
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
                        help=f"预约项目的 Event ID，默认为教职工羽毛球场 ({DEFAULT_EVENT_ID}) 常见值: \n"
                             "教职工羽毛球场 (b8d2f7e00603f0f5af4de278c0b461b8) \n"
                             "体育馆二楼羽毛球场 (fc5379ac197b421940fffa4c99723e11)")
    parser.add_argument("--book-all", action="store_true",
                        help="如果设置此标志，脚本会尝试预约找到的所有可用偏好时段，而不是只预约第一个。\n"
                             "注意：这仍受限于系统的预约规则（如最大未使用数）。")
    # 修改：--schedule-time 参数，default=None，help 文本更新
    parser.add_argument("-st", "--schedule-time", type=validate_time_format, default=None, # default 改为 None
                        help="脚本每天自动执行预约逻辑的时间 (北京时间, HH:MM 格式)。\n"
                             "例如: --schedule-time 09:00\n"
                             "如果省略此参数，脚本将立即执行一次预约尝试。") # 更新 help 说明

    args = parser.parse_args()

    # --- Token 决策逻辑 ---
    if args.token:
        auth_token = args.token
        token_source = "命令行提供"
    else:
        auth_token = DEFAULT_AUTH_TOKEN
        token_source = "内置默认"
        if not auth_token:
             print("[!] 错误：未通过命令行提供 Token，且内置的默认 Token 也为空！请必须提供一个有效的 Token。")
             exit(1) # 使用 exit 而不是 sys.exit 也可以

    target_date = args.date
    preferred_times = args.time
    preferred_courts = args.court
    event_id = args.event
    book_all_mode = args.book_all
    schedule_time = args.schedule_time # 获取定时执行时间, 可能为 None

    # --- 打印启动信息 (根据是否有 schedule_time 调整模式显示) ---
    print(f"--- 预约脚本 ({date.today()}) ---")
    print(f"[*] 目标日期: {target_date}")
    print(f"[*] 偏好场地: {', '.join(preferred_courts)}")
    print(f"[*] 偏好时段: {', '.join(preferred_times)}")
    print(f"[*] Event ID: {event_id}")
    if schedule_time:
        print(f"[*] 模式: 定时执行 (每天北京时间 {schedule_time})")
    else:
        print("[*] 模式: 立即执行一次")
    print(f"[*] 预约模式: {'尝试预约所有找到的可用偏好' if book_all_mode else '预约找到的第一个可用偏好后停止'}")
    print(f"[*] 使用 Token 来源: {token_source}")
    print(f"[*] 使用 Token: {auth_token[:15]}...{auth_token[-15:]}")

    # --- 实际执行预约的函数 (run_booking) ---
    # 将 headers 构建移到函数内部，确保每次执行都使用最新的配置
    def run_booking():
        successful_bookings_count = 0 # 重命名变量以示区分
        beijing_time_start = datetime.now(timezone(timedelta(hours=8)))
        print(f"\n--- 开始执行预约逻辑 ({beijing_time_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')}) ---")
        try:
            # 每次执行时构建最新的 headers
            local_headers = build_headers(auth_token)

            # 1. 查询时段信息
            slot_details_data = get_slot_details(target_date, event_id, local_headers)

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
                    booked_this_run = False # 重命名变量
                    for slot_to_book in available_preferred_slots:
                        time.sleep(0.1) # 短暂延时
                        # 再次构建 headers (理论上不需要，但确保隔离性)
                        booking_headers = build_headers(auth_token)
                        if book_court(slot_to_book, event_id, booking_headers):
                            successful_bookings_count += 1
                            booked_this_run = True
                            if not book_all_mode:
                                print("\n*** 已成功预约一个时段，本次执行结束 (非 book-all 模式)。 ***")
                                break # 跳出 for 循环，结束本次预约尝试
                        # else: 预约失败，继续尝试列表中的下一个

                    if book_all_mode and booked_this_run:
                        print(f"\n*** 已尝试预约所有找到的可用时段 (book-all 模式)，本次成功 {successful_bookings_count} 个。 ***")
                    elif not booked_this_run:
                        print("[-] 本次尝试预约找到的时段均失败或未找到满足条件的可预约时段。")

                # else: 未找到可用偏好时段，函数内部已打印信息
                #     pass
            else:
                print("[!] 获取场地信息失败，可能是网络或 Token 问题。")

        except ValueError as e: # 捕获 build_headers 可能的错误
            print(f"[!] 构建请求头时出错: {e}")
        except Exception as e:
            print(f"\n!!! 执行预约逻辑时遇到未处理的错误: {e}")
            traceback.print_exc()
        finally:
            beijing_time_end = datetime.now(timezone(timedelta(hours=8)))
            print(f"--- 本次预约逻辑执行结束 ({beijing_time_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')}) ---")
            # run_booking 函数不再需要 return，除非你想返回状态
            # return successful_bookings_count # 可以选择返回成功数量

    # --- 根据 schedule_time 决定执行方式 ---
    if schedule_time:
        # 定时执行模式
        print(f"\n[*] 配置定时任务：每天北京时间 {schedule_time} 执行。")
        schedule.every().day.at(schedule_time).do(run_booking)

        print(f"[*] 脚本进入等待状态，按 Ctrl+C 停止。")
        last_minute = -1

        try:
            while True:
                schedule.run_pending()
                now = datetime.now(timezone(timedelta(hours=8)))
                current_minute = now.minute
                # 每分钟打印一次状态信息
                if current_minute != last_minute:
                    print(f"[*] 当前时间 (北京时间): {now.strftime('%Y-%m-%d %H:%M')}, 等待目标时间 {schedule_time}...")
                    last_minute = current_minute
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[!] 检测到 Ctrl+C，用户手动停止脚本。")
        finally:
            print(f"--- 定时预约脚本结束 ({datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S %Z%z')}) ---")

    else:
        # 立即执行模式
        print("\n[*] 未指定执行时间 (--schedule-time)，将立即执行一次预约尝试...")
        run_booking() # 直接调用执行函数
        print(f"\n--- 立即执行模式完成 ---")
        # 脚本在此处自然结束