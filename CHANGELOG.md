# 项目备忘录 / CHANGELOG

## 2026-06-16

### 编译命令 EXACT_MATCH 精确匹配

**问题**：`ctvbuild all -o 352 atv ...` 中 `atv` 会模糊匹配到 `atv_ntsc`，导致弹出手动选择菜单。

**解决**：
1. 服务器 `ask_select.sh` 支持 `EXACT_MATCH=1` 环境变量
2. 编译命令自动加前缀：`cd {code_dir} && EXACT_MATCH=1 ctvbuild all -o {args}`

**影响的服务器脚本**（均已修改并备份 `.bak`）：
- `/home/user/352_AN12_MP3/code/cultraview/script/ask_select.sh`
- `/home/user/352_AN14_MP2/code/cultraview/script/ask_select.sh`
- `/home/user/560_AN14_MP4/code/cultraview/script/ask_select.sh`
- `/home/user/950S_MP3/code/cultraview/script/ask_select.sh`
- `/home/user/962D4_MP3/code/cultraview/script/ask_select.sh`

**改动内容**：
```bash
# 原来（模糊匹配）
grep -i "${findStr}"

# 现在（支持精确匹配）
$(if [ "${EXACT_MATCH}" = "1" ]; then grep -iw "${findStr}"; else grep -i "${findStr}"; fi)
```

**注意**：新增项目时需要同步修改对应的 `ask_select.sh`。

---

### 编译命令最后一个参数

**规则**：`ctvbuild all -o` 最后一个参数用**目标目录名**（用户填写），不是源客户目录名。

示例：
- 源目录：`cusConfig/352/atv/Aipuda/AN12_CV352_A42_680MA_TZ`
- 目标目录：`HONGYUAN_TP202403-0021_CV352_A55_60Hz_260403`
- 编译命令：`ctvbuild all -o 352 atv Aipuda HONGYUAN_TP202403-0021_CV352_A55_60Hz_260403`

---

### 已知 Bug 修复清单

1. **线程安全**：Tab 补全 UI 操作改用 Signal 跨线程通信
2. **pyte 竞争**：`_term_screen` 加 `threading.Lock`
3. **命令注入**：`build_service` 改用 base64 脚本文件执行
4. **密码存储**：优先 `keyring` 钥匙串，回退 QSettings
5. **硬编码路径**：`/home/user/...` 改为相对路径
6. **资源泄漏**：SSH channel 加 `finally` 关闭
7. **日志溢出**：超 2MB 自动截断
8. **tmux 残留**：异常退出时清理 session

---

## 项目架构备忘

### 远程服务器路径结构

```
/home/user/
├── {项目名}/                    # 如 352_AN12_MP3, 560_AN14_MP4
│   └── code/
│       └── cultraview/
│           ├── cusConfig/       # 客户配置根目录
│           │   ├── {板型}/      # 如 352, 560
│           │   │   ├── {区域}/  # 如 atv, atv_ntsc, dvb
│           │   │   │   ├── {客户}/    # 如 Aipuda, DASHI
│           │   │   │   │   └── {订单目录}/  # 如 AN12_CV352_A42_680MA_TZ
│           ├── script/
│           │   ├── select_dialog.sh   # 目录选择对话框
│           │   └── ask_select.sh      # 选择交互脚本
│           └── buildctv.sh     # 编译入口（ctvbuild 软链接指向此脚本）
```

### 编译命令格式

```bash
cd /home/user/{项目名}/code && EXACT_MATCH=1 ctvbuild all -o {板型} {区域} {客户} {订单目录}
```

示例：
```bash
cd /home/user/560_AN14_MP4/code && EXACT_MATCH=1 ctvbuild all -o 352 atv DASHI HONGYUAN_TP202403-0021_CV352_A55_60Hz_260403
```

- 最后一个参数用**目标目录名**，不是源客户目录名
- `EXACT_MATCH=1` 防止 `atv` 模糊匹配到 `atv_ntsc`

### 编译 tmux 会话

- 会话名：`ctvbuild-{task_id}`（如 `ctvbuild-build-001`）
- 日志文件：`/tmp/ctvbuild-{task_id}.log`
- 完成标记：`CTV_BUILD_DONE_{task_id}:{exit_code}`
- 用户可在服务器执行 `tmux attach -t ctvbuild-build-001` 查看

### 自动应答选单

`ctvbuild` 运行中可能弹出选择菜单（如选区域），默认发送按键 `1`（第一项）。
可在编译页面的"选单自动选择"下拉框修改。

### UI 页面导航

| 索引 | 页面 | 说明 |
|------|------|------|
| 0 | AI 模式 | 输入需求 → AI 分析 → 审核 → 执行 → 编译 |
| 1 | 手动模式 | 手动选择目录、执行规则 |
| 2 | 审核面板 | AI 分析结果审核 |
| 3 | 执行结果 | 显示修改 diff、校验结果 |
| 4 | 编译构建 | 持久化 shell 终端 + 编译命令 + tmux 快捷按钮 |
| 5 | 规则管理 | 规则配置 |

### 编译构建页面终端快捷键

| 按键 | 功能 |
|------|------|
| Enter | 执行命令 |
| Tab | 远程补全（SSH compgen） |
| ↑/↓ | 命令历史 |
| Ctrl+C | 中断当前命令 |
| Escape | 发送 ESC |

### 密码存储

- 优先使用 macOS 钥匙串（`keyring` 库）
- 回退到 `QSettings` 明文 plist（不推荐）
- 服务名：`CtvAuto`，账户名：SSH 用户名

### 新增项目注意事项

1. 确保服务器上 `{项目}/code/cultraview/script/ask_select.sh` 已同步 `EXACT_MATCH` 修改
2. 项目目录结构需符合 `cusConfig/{板型}/{区域}/{客户}/{订单}` 格式
3. `ctvbuild` 命令需在 `/usr/bin/` 或 PATH 中可用

### macOS 特殊处理

- 标题栏透明：通过 `static/libmac_titlebar.dylib` 实现
- 毛玻璃效果：`ui/mac_blur.py` 使用 PyObjC 调用 NSVisualEffectView
- 字体：避免使用 Consolas（macOS 无此字体），用 Menlo 替代
