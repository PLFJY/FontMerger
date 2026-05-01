# FontMerger

[English](#english)

`FontMerger` 是一个用于“字体补字融合”（fallback blending）的 Python CLI/TUI 工具。运行方式是 `python main.py`，不依赖 pip console script。

它不是普通字体合并器。Primary font（母字体）会被保留，Secondary font（并入字体）只用于补充母字体缺失的 Unicode 字符。

## 功能

- 支持单个 static font、static family 目录、variable font。
- 通过 `fvar` 表自动识别 variable font。
- 将 variable font 实例化为 static instance 后再安全融合。
- Primary 是已有 glyph 的唯一来源。
- Secondary 只补充 Primary cmap 中缺失的 Unicode。
- 保护 Primary 的 ASCII、Latin、Symbols、PUA/Nerd Font glyph、布局表、metrics 和命名行为。
- 重写输出字体的 Family/Subfamily/Full/PostScript 名称，避免系统和编辑器识别混乱。

## 环境要求

- Python 3.10+
- `fonttools`
- `prompt_toolkit`，用于更好看的 TUI 和灰色默认值占位
- `rich`，用于融合过程中的总体进度条和每个字重的阶段进度条

## 安装

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## CLI 用法

```bash
python main.py \
  --primary /path/to/PrimaryFontOrFamily \
  --secondary /path/to/SecondaryFontOrFamily \
  --name "Primary Secondary Blend" \
  --out-dir ./out
```

Windows 示例：

```powershell
.\.venv\Scripts\python.exe main.py `
  --primary "E:\Fonts\JetBrainsMonoNerdFontMono" `
  --secondary "E:\Fonts\NotoSansMonoCJKsc-VF.ttf" `
  --name "JetBrainsMonoNF NotoSansSC" `
  --out-dir ".\out"
```

如果不传 `--name`，默认 Family Name 是：

```text
PrimaryFamily SecondaryFamily
```

## TUI 用法

```bash
python main.py --tui
```

TUI 是全屏菜单式向导，启动时会优先使用系统语言。界面里有语言切换按钮，可以随时在中文和 English 之间切换。

流程：

1. Primary / Secondary 路径输入
2. 自动检测字体类型并进入命名与输出设置
3. 输出 Family Name、输出模式、Instance 模式、输出目录
4. 最终确认运行

操作方式：

- 正常状态下，方向键切换焦点
- 焦点在输入框时，直接开始输入会自动进入编辑
- 输入框内可用左右方向键移动光标，用 `Tab` 补全路径
- 输入框内按 `Enter` 保存内容并退出输入框
- 长路径会在输入框内自动换行显示
- 焦点在菜单项时，按 `Enter` 进入选择，再用上下方向键切换选项
- `Enter` 确认当前按钮或选项
- `Esc` 返回上一步
- `F9` 下一步，`F8` 上一步，`F2` 切换语言，`F10` 开始运行
- `Ctrl+C` 取消

路径输入支持路径补全。输出模式和实例模式使用可上下选择的菜单。最终确认前可以通过“上一步/Back”回到前面的页面修改配置。

## 输出模式

默认是 `--output auto`。

- 任一输入是 variable font 时，默认输出 static family。
- Static family 会按文件逐个融合。
- Variable font 会被当作“可实例化字体生成器”，而不是打包字体。
- Experimental variable output 目前会严格报错，不会静默降级生成不可靠结果。

`--output static` 会强制输出 static 字体。

`--output variable` 目前只做 Primary/Secondary 是否都是 VF、轴是否兼容的检查，然后明确提示实验模式尚未启用。

## 进度显示

运行融合时使用 `rich` 显示总体进度和当前实例进度。每个字重/Italic 实例都有自己的阶段进度：

1. Primary instance ready
2. Secondary instance ready
3. Missing Unicode mappings analyzed
4. Secondary fallback subset prepared
5. Fallback outlines and cmap merged
6. Primary glyphs, metrics, and layout restored
7. Output names and style flags applied
8. Output font saved

在支持交互刷新进度的终端里会显示动态进度条；在日志重定向或不支持动态刷新的环境里，Rich 会自动退回为可读的静态输出。

## Variable Font 处理规则

Primary 是 variable font 时：

- 优先使用 `fvar` named instances。
- 如果没有 named instances 且有 `wght` 轴，则在支持范围内生成标准权重 `100..900`。
- 其他轴固定在 default value。
- 不自动展开多轴笛卡尔积，避免实例数量爆炸。

Secondary 是 variable font 时：

- 针对每个 Primary instance 实例化 Secondary。
- 如果 Secondary 支持 `wght`，会按 Primary weight 匹配并裁剪到可用范围。
- 如果 Secondary 不支持对应轴，则使用 default value。

## Primary 保护规则

融合过程是保守的：

- 合并后恢复 Primary 的所有 Unicode 映射。
- 对 Primary cmap 中已有的 glyph，恢复 Primary 的 `glyf` 轮廓和 `hmtx` metrics。
- 合并后恢复 Primary 的 `GDEF`、`GSUB`、`GPOS` 等布局表。
- 保留 Primary 的水平/垂直 metrics。
- 使用可序列化 glyph name 的 `post` format 2，保留 PUA/Nerd Font glyph 名称。
- 丢弃 Secondary 的布局逻辑；Secondary 只提供缺字 fallback 轮廓和宽度。

## 实测案例

已用以下字体测试：

- Primary: `JetBrainsMonoNerdFontMono` static family，16 个文件
- Secondary: `NotoSansMonoCJKsc-VF.ttf`，带 `wght` 轴的 variable font

测试命令：

```powershell
.\.venv\Scripts\python.exe main.py `
  --primary "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\JetBrainsMonoNerdFontMono" `
  --secondary "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\NotoSansMonoCJKsc-VF.ttf" `
  --name "JetBrainsMonoNF NotoSansSC Test" `
  --out-dir "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\out-FontMerger-test"
```

结果：

- 生成文件数：16
- 每个实例新增 fallback Unicode mappings：44070
- Regular 输出 glyph 数：55708
- 已检查 Primary Regular cmap 条目：11756
- Primary cmap mismatch：0
- ASCII `A` 保持映射到 Primary 的 `A`
- PUA `U+E0B0` 保持映射到 `pl-left_hard_divider`
- PUA `U+F120` 保持映射到 `fa-terminal`
- 中文样本 `一`、`汉`、`字` 已补入

融合时可能重复看到：

```text
Dropped cmap subtable from font '0': format 6, platformID 1, platEncID 0
```

这是 fontTools 丢弃 legacy cmap 子表的提示。常用 Unicode cmap 子表仍然保留。

## Linux 字体安装

当前用户安装：

```bash
mkdir -p ~/.local/share/fonts/FontMerger
cp ./out/*.ttf ~/.local/share/fonts/FontMerger/
fc-cache -fv
fc-match "Your Family Name"
```

系统级安装：

```bash
sudo mkdir -p /usr/local/share/fonts/FontMerger
sudo cp ./out/*.ttf /usr/local/share/fonts/FontMerger/
sudo fc-cache -fv
```

代码按跨平台方式编写，但字体渲染仍取决于系统 font stack。Linux 下建议用 `fc-match`、终端和编辑器实际验证生成 family。

## 开发检查

Windows:

```powershell
.\.venv\Scripts\python.exe -m compileall font_merger main.py
.\.venv\Scripts\python.exe main.py --help
```

Linux/macOS:

```bash
./.venv/bin/python -m compileall font_merger main.py
./.venv/bin/python main.py --help
```

## 备注

大型 CJK 融合可能耗时数分钟，输出 family 也会比较大。可以用 `--tmp-dir` 指定临时实例文件目录。

---

## English

`FontMerger` is a Python CLI/TUI tool for fallback font blending. Run it with `python main.py`; no pip console-script entry point is required.

This is not a normal font merger. The primary font is preserved, and the secondary font is used only to fill Unicode codepoints that the primary font does not provide.

## Features

- Accepts a single static font, a static family directory, or a variable font.
- Detects variable fonts by checking the `fvar` table.
- Instantiates variable fonts into static instances before safe blending.
- Uses the primary font as the source of truth for existing glyphs.
- Adds only missing Unicode mappings from the secondary font.
- Preserves primary ASCII, Latin, symbols, PUA/Nerd Font glyphs, layout tables, metrics, and naming behavior.
- Rewrites output Family/Subfamily/Full/PostScript names so operating systems and editors identify the generated family correctly.

## Requirements

- Python 3.10+
- `fonttools`
- `prompt_toolkit` for the nicer TUI and gray default placeholders
- `rich` for overall progress bars and per-weight stage progress bars

## Setup

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## CLI Usage

```bash
python main.py \
  --primary /path/to/PrimaryFontOrFamily \
  --secondary /path/to/SecondaryFontOrFamily \
  --name "Primary Secondary Blend" \
  --out-dir ./out
```

Windows example:

```powershell
.\.venv\Scripts\python.exe main.py `
  --primary "E:\Fonts\JetBrainsMonoNerdFontMono" `
  --secondary "E:\Fonts\NotoSansMonoCJKsc-VF.ttf" `
  --name "JetBrainsMonoNF NotoSansSC" `
  --out-dir ".\out"
```

If `--name` is omitted, the default family name is:

```text
PrimaryFamily SecondaryFamily
```

## TUI Usage

```bash
python main.py --tui
```

The TUI is a full-screen menu wizard. It starts with the system language when possible, and the interface includes a language switch button so you can switch between English and Chinese at any time.

Flow:

1. Primary / Secondary path input
2. Automatic detection, then name/output settings
3. Output family name, output mode, instance mode, and output directory
4. Final confirmation

Controls:

- In normal mode, arrow keys move focus
- When an input is focused, typing automatically starts editing
- Inside an input, Left/Right moves the cursor and `Tab` completes paths
- Inside an input, press `Enter` to save and leave the input
- Long paths wrap inside the input field
- When a menu is focused, press `Enter` to select, then use Up/Down to change options
- `Enter` confirms the focused button or option
- `Esc` goes back
- `F9` goes next, `F8` goes back, `F2` switches language, `F10` runs
- `Ctrl+C` cancels

Path inputs support completion. Output mode and instance mode are selectable menus. Before running, you can use Back to return to previous pages and adjust the configuration.

## Output Modes

`--output auto` is the default.

- If either input is a variable font, output defaults to a static family.
- Static family inputs are blended file by file.
- Variable fonts are treated as instance generators, not as bundled finished fonts.
- Experimental variable output is intentionally gated and currently reports an error instead of silently producing an unsafe result.

`--output static` always generates static output.

`--output variable` currently validates that both inputs are variable fonts with compatible axes, then stops with an explicit experimental-mode error.

## Progress Display

During blending, FontMerger uses `rich` to show both overall progress and per-instance progress. Each weight/Italic instance has its own stages:

1. Primary instance ready
2. Secondary instance ready
3. Missing Unicode mappings analyzed
4. Secondary fallback subset prepared
5. Fallback outlines and cmap merged
6. Primary glyphs, metrics, and layout restored
7. Output names and style flags applied
8. Output font saved

Interactive terminals show live progress bars. When output is redirected or dynamic rendering is unavailable, Rich automatically falls back to readable static output.

## Variable Font Handling

For a primary variable font:

- Named instances from `fvar` are preferred.
- If no named instances exist and the font has a `wght` axis, standard weights `100..900` are generated within the supported axis range.
- Other axes stay at their default value.
- The tool does not generate a Cartesian product of all axes.

For a secondary variable font:

- Each primary instance gets a matching secondary instance.
- If the secondary supports `wght`, it is clamped to the closest compatible value.
- If the secondary does not support the axis, its default value is used.

## Primary Preservation Rules

The blend process is conservative:

- Primary Unicode mappings are restored after merging.
- Primary `glyf` outlines and `hmtx` metrics are restored for all primary cmap entries.
- Primary layout tables such as `GDEF`, `GSUB`, and `GPOS` are restored after merging.
- Primary horizontal and vertical metrics are kept.
- PUA/Nerd Font glyph names are preserved by keeping a serializable `post` format 2 table.
- Secondary layout logic is discarded; secondary contributes fallback outlines and widths only.

## Tested Case

This project was tested with:

- Primary: `JetBrainsMonoNerdFontMono` static family, 16 files
- Secondary: `NotoSansMonoCJKsc-VF.ttf`, variable font with `wght`

Command used:

```powershell
.\.venv\Scripts\python.exe main.py `
  --primary "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\JetBrainsMonoNerdFontMono" `
  --secondary "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\NotoSansMonoCJKsc-VF.ttf" `
  --name "JetBrainsMonoNF NotoSansSC Test" `
  --out-dir "E:\_PersonalStuff\else\Fonts\JetBrainsMonoNerdFont+NotoSansSC\out-FontMerger-test"
```

Observed result:

- Generated files: 16
- Added fallback Unicode mappings per instance: 44070
- Regular output glyph count: 55708
- Primary Regular cmap entries checked: 11756
- Primary cmap mismatches: 0
- ASCII `A` stayed mapped to the primary glyph `A`
- PUA `U+E0B0` stayed mapped to `pl-left_hard_divider`
- PUA `U+F120` stayed mapped to `fa-terminal`
- CJK samples such as `一`, `汉`, and `字` were added

The repeated message below can appear during merging:

```text
Dropped cmap subtable from font '0': format 6, platformID 1, platEncID 0
```

That is fontTools dropping a legacy cmap subtable. The normal Unicode cmap subtables remain available.

## Linux Font Installation

Install for the current user:

```bash
mkdir -p ~/.local/share/fonts/FontMerger
cp ./out/*.ttf ~/.local/share/fonts/FontMerger/
fc-cache -fv
fc-match "Your Family Name"
```

System-wide installation:

```bash
sudo mkdir -p /usr/local/share/fonts/FontMerger
sudo cp ./out/*.ttf /usr/local/share/fonts/FontMerger/
sudo fc-cache -fv
```

The code is designed to be cross-platform, but font rendering still depends on the platform font stack. On Linux, verify the generated family with `fc-match`, your terminal, and your editor.

## Development Checks

Windows:

```powershell
.\.venv\Scripts\python.exe -m compileall font_merger main.py
.\.venv\Scripts\python.exe main.py --help
```

Linux/macOS:

```bash
./.venv/bin/python -m compileall font_merger main.py
./.venv/bin/python main.py --help
```

## Notes

Large CJK blends can take several minutes and produce large output families. Use `--tmp-dir` if you want temporary variable-font instances to be written to a specific location.
