# NUIST 场馆预约自动化脚本 (book_badminton_NUIST) 🏸

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![GitHub stars](https://img.shields.io/github/stars/Liu8Can/book_badminton_NUIST?style=social)](https://github.com/Liu8Can/book_badminton_NUIST/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Liu8Can/book_badminton_NUIST?style=social)](https://github.com/Liu8Can/book_badminton_NUIST/network/members)

一个用于自动化预约南京信息工程大学（NUIST）场馆（默认为教职工活动中心羽毛球场）的 Python 脚本。脚本通过模拟微信 H5 页面的 API 请求，实现自动查询空闲时段并尝试预订。

**仓库地址:** [https://github.com/Liu8Can/book_badminton_NUIST](https://github.com/Liu8Can/book_badminton_NUIST)

## ✨ 功能特性

*   **自动化预约:** 循环查询指定日期、场地和时段的可用性，并在发现空闲时自动尝试预约。
*   **灵活的目标配置:** 支持通过命令行参数自定义预约的目标日期、场地列表、时段列表。
*   **多偏好支持:**
    *   **捡漏模式 (默认):** 按偏好顺序查找，预约找到的第一个可用时段后停止。
    *   **尝试全部模式 (`--book-all`):** 查找所有满足偏好的可用时段，并尝试逐个预约（受系统规则限制）。
*   **可配置尝试间隔:** 自定义每次查询尝试之间的时间间隔。
*   **基于 Token 认证:** 使用从微信 H5 页面获取的 JWT Token 进行身份验证。

## 🚀 快速开始

### 1. 环境准备

*   确保你安装了 Python 3.x。
*   安装所需的 `requests` 库：
    ```bash
    pip install requests
    ```

### 2. 获取代码

```bash
git clone https://github.com/Liu8Can/book_badminton_NUIST.git
cd book_badminton_NUIST
```

### 3. 获取认证 Token (❗极其重要❗)

此脚本需要一个有效的 JWT Token 来模拟登录状态并发送预约请求。**由于 Token 有效期较短（根据经验约 1 小时），你需要在每次运行脚本前获取一个新的 Token。**

**获取步骤:**

1.  **登录系统:** 在你的**微信**中，打开南京信息工程大学的场馆预约系统 (通常入口是 `wechatmeeting.nuist.edu.cn`)。
2.  **打开开发者工具/抓包工具:**
    *   **PC 端微信开发者工具:** 如果你能在这个工具里访问 H5 页面，可以使用它的 Network 面板。
    *   **手机抓包 App:** 如 ProxyPin (Android)、Stream (iOS) 等。
    *   **电脑代理抓包:** 如 Fiddler, Charles, mitmproxy, 或你使用的 ProxyPin。你需要配置手机代理指向电脑 IP 和抓包工具监听的端口，并信任抓包工具的证书以解密 HTTPS 流量（如果需要）。
3.  **触发 API 请求:** 在预约系统 H5 页面进行一些操作，例如刷新场地列表、查看“我的预约”等，目的是让页面向后端 API (`http://wechatmeeting.nuist.edu.cn/api/v2/...`) 发送请求。
4.  **查找并复制 Token:** 在抓包工具中，找到一个发往 `wechatmeeting.nuist.edu.cn` 的 API 请求（**不是** HTML 页面请求）。查看该请求的 **请求头 (Request Headers)**，找到 `Cookie` 字段。复制 `token=` 后面的那一长串字符（通常以 `eyJ...` 开头）。这就是你需要的 JWT Token。

    示例 `Cookie` 头：
    `Cookie: JSESSIONID=ABCDEF...; token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`
    你需要复制的部分是：`eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`

好的，根据你提供的最新代码，这里是更新后的、更详细的 `README.md` 文档中的 **“运行脚本”** 部分。这部分包含了各种参数的使用方法和示例，希望能帮助你（或其他用户）快速上手和回忆起如何使用。

## 🚀 运行脚本

在获取到有效的 Token（或者确认内置默认 Token 仍然有效）后，你可以在终端中通过 `python book_badmintonv3.py [参数]` 来运行脚本。

**核心参数:**

*   `-tk` 或 `--token`: **(可选)** 提供一个有效的 JWT Token。
    *   **如果省略此参数:** 脚本将使用内置的 `DEFAULT_AUTH_TOKEN`。 **请注意：内置 Token 会过期！** 如果遇到认证错误，你需要获取新的 Token 并通过此参数传入。
    *   **如果提供此参数:** 脚本将优先使用你提供的 Token。
*   `-d` 或 `--date`: **(可选)** 目标预约日期，格式为 `YYYY-MM-DD`。默认为脚本运行当天的**明天**。
*   `-t` 或 `--time`: **(可选)** 偏好的预约**时段开始时间**列表，格式为 `HH:MM`，多个时间用**空格**分隔。脚本会按列表顺序查找。默认为 `10:00`。
*   `-c` 或 `--court`: **(可选)** 偏好的**场地名称**列表，多个场地用**空格**分隔。如果场地名称包含空格，请使用**引号**括起来 (例如 `"场地 5"`)。脚本会按列表顺序查找。默认为 `场地1`。
*   `-e` 或 `--event`: **(可选)** 预约项目的 `eventId`。用于区分不同的场馆或服务。
    *   默认为**教职工活动中心羽毛球场**: `b8d2f7e00603f0f5af4de278c0b461b8`
    *   已知的**体育馆二楼羽毛球场**: `fc5379ac197b421940fffa4c99723e11`
    *   你可以通过抓包找到其他项目的 `eventId`。
*   `-i` 或 `--interval`: **(可选)** 每次查询循环之间的等待时间（秒）。可以是小数，例如 `0.5`。默认为 `1.0` 秒。**请勿设置过小的值，以免给服务器造成压力或被限制。**
*   `--book-all`: **(可选)** 这是一个开关标志。
    *   **如果包含此参数:** 脚本会尝试预约所有找到的满足偏好的可用时段（但仍受系统规则限制，如最大未使用预约数）。
    *   **如果省略此参数 (默认行为):** 脚本在成功预约找到的第一个可用偏好时段后，就会停止运行。

**示例:**

**脚本在不断优化中，v3或v4版本已经足够你使用，当前最新版本是v5，你可以使用 -h 命令来查看帮助文档** 
示例：`python .\book_badmintonv5.py -h   `

1.  **最简用法 (使用内置 Token，预约明天 10:00 的场地1):**
    ```bash
    python book_badmintonv3.py
    ```
    *注意：这依赖于内置 Token 有效。如果失败提示认证错误，请使用 `-tk` 提供新 Token。*

2.  **使用你获取的新 Token (预约明天 10:00 的场地1):**
    ```bash
    python book_badmintonv3.py -tk "你复制粘贴过来的新Token字符串"
    ```

3.  **指定日期和时间 (使用新 Token):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -d "2025-04-20" -t "15:00"
    ```

4.  **指定多个偏好时间 (预约场地1的 14:00 或 15:00，哪个先有约哪个):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -t 14:00 15:00
    ```

5.  **指定多个偏好场地 (预约 10:00 的场地2 或 场地3，哪个先有约哪个):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -c 场地2 场地3
    ```

6.  **指定多个场地和多个时间 (按顺序检查 场地1-09:00, 场地1-10:00, 场地2-09:00, 场地2-10:00，约到第一个可用的就停):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -c 场地1 场地2 -t 09:00 10:00
    ```

7.  **尝试预约所有找到的可用偏好 (例如，如果 15:00 和 16:00 的场地1都有空，尝试两个都预约):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -t 15:00 16:00 --book-all
    ```
    *请注意，由于系统规则，通常只能成功预约一个。*

8.  **加快查询频率 (例如 0.5 秒一次):**
    ```bash
    python book_badmintonv3.py -tk "新Token" -i 0.5
    ```

9.  **预约体育馆二楼的羽毛球场:**
    ```bash
    python book_badmintonv3.py -tk "新Token" -e "fc5379ac197b421940fffa4c99723e11" -t "19:00" -c "羽球场01" # 场地名称需要根据实际情况确认
    ```

**查看帮助:**

如果你忘记了参数的具体用法，可以随时运行：

```bash
python book_badmintonv3.py --help
```

**停止脚本:**

在脚本运行时，按 `Ctrl + C` 可以随时停止脚本。


## ⚙️ 关键概念

*   **`eventId`**: 用于标识不同的预约项目（如羽毛球场、篮球场等）。默认为教职工羽毛球场 (`b8d2f7e00603f0f5af4de278c0b461b8`)。你可以通过抓包工具在预约系统入口或列表页面找到其他项目的 `eventId`。
*   **`Token (JWT)`**: 用于身份验证。它由服务器在用户登录或授权后签发，具有**较短的有效期**。脚本的成功运行依赖于提供有效的 Token。
*   **预约模式 (`--book-all`)**:
    *   **默认 (不带 `--book-all`)**: 脚本找到第一个满足偏好的可用时段并成功预约后，就会停止。
    *   **启用 (`--book-all`)**: 脚本会查找所有满足偏好的可用时段，并尝试将它们全部预约（通常会因为系统规则限制，只能成功预约一个）。

## ⚠️ 重要提示与已知问题

1.  **❗ Token 有效期:** Token 的有效期非常短，根据经验通常在 **1 小时** 左右。这意味着：
    *   **你必须在运行脚本前不久获取一个新的、有效的 Token。**
    *   脚本无法实现完全无干预的长时间自动运行。
    *   如果在抢票关键时刻 Token 过期，将导致预约失败。

2.  **❗ 预约数量限制:** 南京信息工程大学的场馆预约系统存在预约规则限制，特别是 **“最大未使用预约个数”** 的限制（根据经验通常为 **1**）。这意味着：
    *   即使你使用 `--book-all` 模式且脚本找到了多个空闲的偏好时段，系统 **通常只允许你成功预约 1 个**。
    *   脚本会尝试预约所有找到的可用时段，但只有第一个符合系统规则的会成功，后续的尝试会因为超出限制而失败。

3.  **依赖外部系统:** 脚本的成功运行依赖于 `wechatmeeting.nuist.edu.cn` 服务的可用性和 API 的稳定性。如果后端服务或 API 发生变更，脚本可能需要更新。

## 🤝 贡献

欢迎提交 Pull Requests 或提出 Issues 来改进此项目。

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## ⚖️ 免责声明

*   请合理使用此脚本，并严格遵守南京信息工程大学场馆预约系统的相关规定。
*   请勿将此脚本用于恶意刷票、占用资源或其他违反规定的行为。
*   开发者不对任何因使用此脚本可能导致的后果负责，包括但不限于预约失败、账号异常、与校方规定的冲突等。 **使用风险自负。**

