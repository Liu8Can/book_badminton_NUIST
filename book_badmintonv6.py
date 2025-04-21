import requests
import json
import time
import argparse
from datetime import date, timedelta, datetime, timezone # 移除重复的 timedelta 导入
import traceback # 引入 traceback 模块
import schedule # 导入 schedule 库
import re # 导入 re 模块用于时间格式验证

# --- 配置 (保持不变) ---
BASE_URL = "http://wechatmeeting.nuist.edu.cn"
DEFAULT_EVENT_ID = "b8d2f7e00603f0f5af4de278c0b461b8"
# 注意：Token 会过期，运行时请替换或确保命令行提供
DEFAULT_AUTH_TOKEN = "" # 建议默认留空，强制命令行提供或提示
DEFAULT_TARGET_DATE = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
DEFAULT_SCHEDULE_TIME = "08:04" # 默认执行时间，根据实际调整
DEFAULT_MAX_RETRIES = 100        # 新增：默认最大重试次数
DEFAULT_RETRY_DELAY = 0.1        # 新增：默认重试间隔（秒）

# --- 函数定义 (保持不变) ---
def build_headers(token):
    """根据传入的 token 构建请求头"""
    if not token:
        raise ValueError("Token 不能为空！")
    return {
        'Host': 'wechatmeeting.nuist.edu.cn',
        'Connection': 'keep-alive',
        # 'Content-Length': '...', # 通常由 requests 自动处理
        'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.51 PythonAutomationScript/1.0',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': BASE_URL,
        'X-Requested-With': 'com.tencent.mm',
        # 'Sec-Fetch-Site': 'same-origin', # 可选
        # 'Sec-Fetch-Mode': 'cors', # 可选
        # 'Sec-Fetch-Dest': 'empty', # 可选
        'Referer': f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={DEFAULT_EVENT_ID}', # 会在需要时被覆盖
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': f'token={token}' # 注意：实际应用中 Cookie 可能更复杂
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
        # 确保 Referer 使用当前的 event_id
        current_headers = headers.copy()
        current_headers['Referer'] = f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={event_id}'
        response = requests.post(search_url, headers=current_headers, json=payload, timeout=10)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if data.get('status') != 0:
            print(f"[!] 查询API返回错误: status={data.get('status')}, message={data.get('message', '无消息')}")
            # 特别处理 Token 失效常见的 status code (根据实际 API 情况调整)
            if data.get('status') == 9999 or data.get('status') == 4011: # 假设 9999 或 4011 表示 Token 问题
                 print("[!] 查询失败：API 返回认证错误，请检查 Token 是否有效或过期。")
            return None
        print(f"[+] 查询成功 (HTTP {response.status_code})")
        return data
    except requests.exceptions.Timeout:
        print(f"[!] 查询时段信息超时。")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[!] 查询时段信息失败 (HTTP {e.response.status_code}): {e}")
        if e.response.status_code in [401, 403]:
             print("[!] 查询失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
        # 可以根据需要处理其他状态码
        return None
    except requests.exceptions.RequestException as e:
        print(f"[!] 查询时段信息失败: {e}")
        return None
    except json.JSONDecodeError:
        print(f"[!] 查询时段信息失败: 无法解析 JSON 响应 - {response.text[:200]}...")
        return None

def find_all_available_preferred_slots(slot_data, target_date, preferred_courts, preferred_times):
    """
    在返回的数据中查找 *所有* 满足偏好列表（场地和时间）的可预约时段。
    Returns:
        list: 包含所有可预约时段的 slot_details 字典的列表，如果找不到则返回空列表。
    """
    available_slots = []
    if not slot_data or slot_data.get('status') != 0:
        # get_slot_details 已经打印了错误，这里可以不重复打印
        # print("[!] 时段数据无效或包含错误，无法查找。")
        return available_slots

    resources = slot_data.get('data', {}).get('list', [])
    if not resources:
        print("[!] 未找到任何场地资源。")
        return available_slots

    print(f"[*] 开始按偏好查找 *所有* 可预约时段...")
    print(f"[*]   偏好场地: {', '.join(preferred_courts)}")
    print(f"[*]   偏好时段 (开始时间): {', '.join(preferred_times)}")

    preferred_courts_set = set(preferred_courts)
    preferred_times_set = set(preferred_times)
    found_courts = set()

    for resource in resources:
        resource_name = resource.get('name')
        resource_id = resource.get('id')
        if resource_name in preferred_courts_set:
            found_courts.add(resource_name)
            print(f"[*]   正在检查场地: {resource_name} (ID: {resource_id})")
            slot_info_list = resource.get('slotInfo', [])
            for slot in slot_info_list:
                start_time = slot.get('startTime')
                if start_time in preferred_times_set:
                    slot_end_time = slot.get('endTime', '未知')
                    display_time = f"{start_time}-{slot_end_time}"
                    # 检查状态是否可预约 (status == 0)
                    if slot.get('status') == 0:
                        print(f"[+++]     发现可预约偏好: {resource_name} {display_time}!")
                        slot_details = {
                            "bookDate": target_date,
                            "bookSlotId": slot.get('slotId'),
                            "bookSlot": display_time, # 用于显示，实际接口可能不需要
                            "number": 1,
                            "price": "", # 价格可能需要从 API 获取或确认是否需要
                            "resourceId": resource_id,
                            "slotOrder": slot.get('slotOrder'),
                            "seatId": "", # 如果需要座位 ID，需处理
                            "scheduleId": slot.get('scheduleId'),
                            "resourceName": resource_name # 用于日志记录
                        }
                        available_slots.append(slot_details)
                    # else: # 减少不必要的日志
                    #     print(f"[-]       时段 {display_time} 状态为 {slot.get('status')}，不可预约。")

    # 检查是否有偏好的场地未在结果中找到
    missing_courts = preferred_courts_set - found_courts
    if missing_courts:
        print(f"[!]   未在查询结果中找到以下偏好场地: {', '.join(missing_courts)}")

    if not available_slots:
        print("[-] 未找到任何满足偏好的可预约时段。")

    return available_slots

def book_court(slot_to_book, event_id, headers):
    """发送单次预约请求"""
    booking_url = f"{BASE_URL}/api/v2/appBookGeneral/book/afterConfirm"

    # 构建实际发送的 record，确保包含 API 需要的所有字段
    record = {
        "bookDate": slot_to_book['bookDate'],
        "bookSlotId": slot_to_book['bookSlotId'],
        "bookSlot": slot_to_book['bookSlot'], # <<<--- 修正：取消注释/添加回来
        "number": slot_to_book['number'],
        "price": slot_to_book.get('price', ""), # 使用 .get 以防万一 price 缺失，并提供默认值
        "resourceId": slot_to_book['resourceId'],
        "slotOrder": slot_to_book['slotOrder'],
        "seatId": slot_to_book.get('seatId', ""), # 使用 .get 提供默认值
        "scheduleId": slot_to_book['scheduleId']
        # "resourceName" 是我们自己添加用于日志的，API 不需要，所以不包含在这里
    }

    payload = {
        "eventId": event_id,
        "extAttr": "",
        "payAmount": 0, # 确认支付金额是否总是 0
        "records": [record] # API 需要一个记录列表
    }
    target_info = f"{slot_to_book.get('resourceName', '未知场地')} {slot_to_book.get('bookSlot', '未知时段')}" # 使用 .get 增加健壮性
    print(f"\n[*] 准备发送预约请求 (目标: {target_info})...")
    # print(f"[*] Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}") # 取消注释以调试 payload

    try:
        # 确保 Referer 使用当前的 event_id
        current_headers = headers.copy()
        current_headers['Referer'] = f'{BASE_URL}/wechat/book3/book.html?type=eventInfo?eventId={event_id}'

        response = requests.post(booking_url, headers=current_headers, json=payload, timeout=15)

        try:
            result = response.json()
            print(f"\n[*] 收到预约响应 (目标: {target_info}, HTTP {response.status_code}):")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(f"[!] 预约失败 ({target_info}): 无法解析 JSON 响应 (HTTP {response.status_code}) - {response.text[:200]}...")
            if response.status_code in [401, 403]:
                 print("[!] 预约请求失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
            return False

        if result.get('status') == 0:
            print(f"[+++] 成功预约: {target_info}!")
            return True
        else:
            error_message = result.get('message', '无错误信息')
            print(f"[-] 预约失败 ({target_info}): {error_message}")
            # 特别注意：如果错误信息是 '预约时间段不能为空'，说明 payload 仍有问题
            if "预约时间段不能为空" in error_message:
                 print("[!!!] Payload 构造可能仍有问题，请检查 book_court 函数中的 record 字典！")
            if "认证失败" in error_message or result.get('status') == 9999 or result.get('status') == 4011:
                print("[!] Token 可能已失效或无权限，请检查 Token。")
            # 如果是之前的 "不在开放日期范围内！" 错误，这次重试仍然可能失败
            if "不在开放日期范围内" in error_message:
                print("[!] 注意：服务器提示不在开放日期范围内，可能需要精确掐点或日期选择有误。")
            return False

    except requests.exceptions.Timeout:
        print(f"[!] 预约请求超时 ({target_info})。")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[!] 发送预约请求失败 ({target_info}): {e}")
        if hasattr(e, 'response') and e.response is not None and e.response.status_code in [401, 403]:
             print("[!] 预约请求失败：认证错误 (401/403)，请检查 Token 是否有效或过期。")
        return False
# --- 时间格式验证函数 (保持不变) ---
def validate_time_format(time_str):
    """验证时间字符串是否为 HH:MM 格式"""
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
        raise argparse.ArgumentTypeError(f"无效的时间格式: '{time_str}'. 请使用 HH:MM 格式 (例如: 08:04, 15:30)。")
    return time_str

# --- 主程序 ---
if __name__ == "__main__":
    # --- 参数解析部分 (增加重试相关参数) ---
    parser = argparse.ArgumentParser(description="羽毛球场馆自动预约脚本 (支持定时执行、多偏好和失败重试)", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-tk", "--token",
                        help="有效的认证 JWT Token。\n"
                             "如果未提供，脚本将尝试使用内置默认 Token (如果设置了)。\n"
                             "强烈建议通过命令行提供最新的 Token。")
    parser.add_argument("-d", "--date", default=DEFAULT_TARGET_DATE, help=f"目标预约日期 (格式: YYYY-MM-DD)，默认为明天 ({DEFAULT_TARGET_DATE})")
    parser.add_argument("-t", "--time", nargs='+', default=["10:00"],
                        help="偏好的预约时段开始时间列表 (格式: HH:MM)，用空格分隔。\n"
                             "例如: --time 10:00 15:00\n"
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
    parser.add_argument("-st", "--schedule-time", type=validate_time_format, default=DEFAULT_SCHEDULE_TIME,
                        help="脚本每天自动执行预约逻辑的时间 (北京时间, HH:MM 格式)。\n"
                             f"例如: --schedule-time 07:59\n"
                             f"默认为 '{DEFAULT_SCHEDULE_TIME}'")
    # 新增：重试参数
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help="在预约失败时，最大尝试次数（包括首次尝试）。\n"
                             f"默认为 {DEFAULT_MAX_RETRIES} 次。设为 1 则不重试。")
    parser.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY,
                        help="每次重试之间的等待时间（秒）。\n"
                             f"默认为 {DEFAULT_RETRY_DELAY} 秒。")

    args = parser.parse_args()

    # --- Token 决策逻辑 ---
    if args.token:
        auth_token = args.token
        token_source = "命令行提供"
    elif DEFAULT_AUTH_TOKEN:
        auth_token = DEFAULT_AUTH_TOKEN
        token_source = "内置默认"
        print("[!] 警告: 正在使用内置的默认 Token，它可能已过期或无效。")
    else:
        print("[!] 错误：必须通过 --token 参数提供一个有效的认证 Token！")
        exit(1)

    target_date = args.date
    preferred_times = args.time
    preferred_courts = args.court
    event_id = args.event
    book_all_mode = args.book_all
    schedule_time = args.schedule_time
    max_retries = args.max_retries
    retry_delay = args.retry_delay

    # --- 打印启动信息 (更新，加入重试信息) ---
    print(f"--- 预约脚本 ({date.today()}) ---")
    print(f"[*] 目标日期: {target_date}")
    print(f"[*] 偏好场地: {', '.join(preferred_courts)}")
    print(f"[*] 偏好时段: {', '.join(preferred_times)}")
    print(f"[*] Event ID: {event_id}")
    print(f"[*] 计划执行时间 (北京时间): {schedule_time}")
    print(f"[*] 预约模式: {'尝试预约所有找到的可用偏好' if book_all_mode else '预约找到的第一个可用偏好后停止'}")
    print(f"[*] 失败重试: 最多 {max_retries} 次尝试, 间隔 {retry_delay} 秒") # 显示重试配置
    print(f"[*] 使用 Token 来源: {token_source}")
    print(f"[*] 使用 Token: {auth_token[:15]}...{auth_token[-15:]}")

    # 验证 max_retries
    if max_retries < 1:
        print("[!] 警告: max_retries 小于 1，将至少执行 1 次尝试。")
        max_retries = 1

    # --- 实际执行预约的函数 (引入重试逻辑) ---
    def run_booking():
        # 获取北京时间 (UTC+8)
        beijing_time_start = datetime.now(timezone(timedelta(hours=8)))
        print(f"\n--- 开始执行预约逻辑 ({beijing_time_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')}) ---")

        attempts = 0
        booking_successful_overall = False # 标记在所有重试中是否至少成功了一次

        # 在每次执行时构建初始 headers，避免 token 陈旧问题（虽然 token 是外部传入的）
        try:
            base_headers = build_headers(auth_token)
        except ValueError as e:
            print(f"[!] 错误: {e}")
            print(f"--- 本次预约逻辑执行因 Token 错误而中止 ---")
            return # 无法构建 headers，直接中止

        while attempts < max_retries and not booking_successful_overall:
            attempts += 1
            if attempts > 1:
                print(f"\n--- 第 {attempts}/{max_retries} 次尝试 ---")
            else:
                 print(f"\n--- 第 {attempts}/{max_retries} 次尝试 ---") # 首次尝试也打印计数

            successful_bookings_this_attempt = 0
            try:
                # 1. 查询时段信息 (每次重试都重新查询)
                slot_details_data = get_slot_details(target_date, event_id, base_headers)

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
                        booked_in_this_round = False # 特指在当前找到的这批 slots 中是否成功
                        for slot_to_book in available_preferred_slots:
                            # 短暂延时，减少 API 压力，或模拟手速间隔
                            time.sleep(0.2) # 稍微增加一点延时

                            # 每次 book 都用最新的 headers (虽然在此循环内变化不大)
                            booking_headers = build_headers(auth_token)
                            if book_court(slot_to_book, event_id, booking_headers):
                                successful_bookings_this_attempt += 1
                                booking_successful_overall = True # 标记全局成功
                                booked_in_this_round = True
                                if not book_all_mode:
                                    print("\n*** 已成功预约一个时段，停止本次尝试。 ***")
                                    break # 成功预约一个，跳出当前 slots 列表的循环
                            # else: # 预约失败，继续尝试列表中的下一个
                            #     pass

                        if book_all_mode and booked_in_this_round:
                            print(f"\n*** 本轮尝试预约所有找到的可用时段，成功 {successful_bookings_this_attempt} 个。***")
                            # 在 book_all 模式下，只要有成功，也算整体成功了
                        elif not booked_in_this_round and available_preferred_slots:
                             print("[-] 本轮尝试预约找到的时段均失败。")

                        # 如果是非 book_all 模式且已成功预约，则跳出重试循环
                        if not book_all_mode and booking_successful_overall:
                             break # 跳出 while attempts < max_retries 循环

                    # else: # 未找到可用偏好时段，函数内部已打印信息
                    #     print("[-] 未找到满足偏好的可预约时段。") # 可以在这里加一句总结
                        pass
                else:
                    print("[!] 获取场地信息失败，可能是网络或 Token 问题。")
                    # 如果查询失败是因为 Token 问题，可能后续重试也无效
                    # 可以考虑在这里增加逻辑，如果检测到是 Token 问题就不再重试
                    # if "Token" in last_error_message: # 伪代码
                    #    break

            except Exception as e:
                print(f"\n!!! 第 {attempts} 次尝试执行时遇到意外错误: {e}")
                traceback.print_exc()
                # 发生未知异常，也计为一次失败尝试

            # --- 重试判断与延时 ---
            if not booking_successful_overall and attempts < max_retries:
                print(f"[*] 第 {attempts} 次尝试未完全成功，将在 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            elif booking_successful_overall:
                 print("\n[***] 预约成功！停止重试。 ***")
                 # 不需要 break，因为 while 条件 `not booking_successful_overall` 会变为 false
            elif attempts == max_retries:
                 print(f"\n[---] 已达到最大重试次数 ({max_retries})，仍未预约成功。 ---")


        # --- 单次调度任务的最终收尾 ---
        beijing_time_end = datetime.now(timezone(timedelta(hours=8)))
        print(f"--- 本次预约逻辑执行结束 ({beijing_time_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')}) ---")
        # run_booking 函数自然结束，等待 schedule 下次调用

    # --- 使用 schedule 库定时执行 run_booking 函数 ---
    # schedule.every().day.at(schedule_time).do(run_booking) # 这是正确的用法
    # 为了方便测试，可以取消下面的注释，立即执行一次
    # print("[DEV] 立即执行一次 run_booking 进行测试...")
    # run_booking()
    # print("[DEV] 测试执行完成。现在设置定时任务...")

    # 设置每日定时任务
    schedule.every().day.at(schedule_time).do(run_booking)
    print(f"[*] 脚本已启动，将等待每天北京时间 {schedule_time} 执行预约...")

    # 运行调度器
    last_check_minute = -1
    while True:
        schedule.run_pending()
        now = datetime.now(timezone(timedelta(hours=8)))
        current_minute = now.minute
        # 每分钟打印一次等待信息，避免刷屏
        if current_minute != last_check_minute:
            print(f"[*] 当前时间 (北京时间): {now.strftime('%Y-%m-%d %H:%M')}, 等待目标时间 {schedule_time} (检查周期: 1秒钟)...")
            last_check_minute = current_minute
        time.sleep(1) # 每 60 秒检查一次任务，减少 CPU 占用