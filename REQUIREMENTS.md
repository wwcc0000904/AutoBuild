## 当前已修复的关键架构问题

| 问题 | 状态 |
|---|---|
| `build_rule_registry()` 从 UI 层移到 `rules/rule_matcher.py` | ✓ |
| `PreinstallRule.enabled` 和 `app` 参数化 | ✓ |
| 服务依赖注入从按钮点击提升到 `main.py` 启动时 | ✓ |
| `config/logging_setup.py` — 文件+控制台双输出日志 | ✓ |
| 所有执行模块接入 `get_logger()` | ✓ |
| `requirements.txt` | ✓ |
| 无用代码 `config/settings.py` 清理 | ✓ |
| 切回 `PySide6` | ✓ |

## 第一阶段修改项清单（全部完成）

### build_config.txt
- 杜比、Miracast、HBG、TVcasting、ESHARE → 打开(y)/关闭(n)
- 电流 → `CTV_CFG_PANEL_BACKLIGHT_CURRENT` value_part 模式
- 客户名称 → `CTV_CFG_CUSTOMER` value 模式

### build_ctv_app.txt
- ESharePlus 预装(Y)/取消(n)

### ctvbuild.prop
- 上电模式：待机(secondary) / 开机(direct) / 记忆(memory)
- 开机模式：动画(0) / 视频(1)

### overlay/.../ctv_data.xml
- BootDesktop：安卓(0) / TV(1) / 记忆(2)
- MenuShowTime：一直显示(0) / 5秒(1) / 10秒(2) / 20秒(3) / 30秒(4) / 60秒(5)
- LanguageShowCountry：带国家(true) / 不带国家(false)
- FakeInfoEnsure：强制存在且为 true
- CountryList：默认国家移到第一项并去重

### etc/whiteList.conf
- 追加/删除包名（谷歌商城 com.android.vending 等）

### configs/db.ini
- 蓝屏开关：System_screencolor = 1(蓝屏) / 0(黑屏)
- 白平衡：所有 FacColorTemp_*_nature 行前3值
- NLA 非线性参数：brightness/contrast/saturation/sharpness/hue/backlight 中间值
- SatGain/HueGain/BriGain：每行前7值，保留后2位

### configs/CtvLanguage.ini
- 默认语言（第一有效行）

### configs/ctvsetting.xml
- 菜单项隐藏/显示（tv kernel / tv sdk / tv resolution 等）

## 对话中已确认跳过（第二阶段）

- 自定义开机视频（mp4替换 + bootanimation.type=1）
- PQ 文件替换（pq/PQ.b、pq/PQ_COMMON.b）
- 屏参文件替换（panel/panel.img）
- logo 替换
- overlay/defaults.xml
- keyconfig.xml、keylayout/、key_pad/、key/
- dtv/ db/
- etc/下除 whiteList.conf 外其他文件
- build_cus_app.txt
- customer_keymap.ini
- configs/下 ctvfactory.ini、cfg.ini（已确认不修改）
- 蓝牙相关（已明确不修改）

## 待办提醒

1. ✅ 语言列表已提供 → `config/language_map.json` 已生成（53种活跃语言）
2. ✅ ro.product.model 非 SMART_TV 时自动修正并显示警告
3. ✅ CountryList 动态数量已处理（运行时正则读取，不限数量）
