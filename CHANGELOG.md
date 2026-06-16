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
