---
name: doctor
description: "环境检查与安装向导。检查数学建模工作流所需的全部依赖是否已安装，对缺失项提供安装命令，并在用户确认后执行安装。手动触发。"
whenToUse: "数模工作流报环境错误（python/typst/xelatex/drawio 缺失、编译失败、依赖报错）时手动触发。"
allowed-tools: Bash(*), Read, Write
---

# Doctor — 环境检查与安装向导

本 skill 检查完整数学建模工作流所需的所有工具是否已就绪，并帮助用户安装缺失项。**本 skill 只在用户显式触发时运行，不自动执行。**

## 检查项清单

### 核心工具

| 工具 | 用途 | 检测/调用（本机 Windows，pwsh 探测） |
| --- | --- | --- |
| `xelatex` | 论文编译（LaTeX 引擎，中文模板） | `Get-Command xelatex`（已入 PATH）；稳妥用全路径 `C:\Users\Administrator\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe` |
| `typst` | 论文编译（Typst 引擎，0.15.1 已装） | 全路径 `C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe\typst-x86_64-pc-windows-msvc\typst.exe`（PATH 待 DSH 进程重启） |
| `mmdc` | mermaid 流程图渲染 SVG/PNG（4drawio） | `Get-Command mmdc`（npm 全局已装，实测出图 ✓） |
| `inkscape` | SVG↔PDF 无损转换（图源路由） | 全路径 `C:\Program Files\Inkscape\bin\inkscape.exe`（已实测 ✓） |
| `python` | 数值计算与图表（3coding-visual） | `Get-Command python`（3.14.0） |
| Word / WPS | Word 引擎排版、docx 转 PDF（官方允许的提交格式） | COM 探测：`New-Object -ComObject Word.Application`（16.0 ✓ / KWPS ✓） |
| `mgs.exe` | PDF 转 PNG 视觉检查（MiKTeX 自带 Ghostscript） | MiKTeX bin 目录 |
| `drawio` | ❌ 本机无 CLI（4drawio 已改用 TikZ/mermaid 渲染） | — |

### Python 包

| 包 | 用途 |
| --- | --- |
| `numpy` / `scipy` / `pandas` / `matplotlib` | 数值计算与图表 |
| `scikit-learn` | 机器学习建模 |
| `openpyxl` | 读写 Excel 数据附件 |
| `scienceplots` | 学术图表样式（`mpl_paper_style.apply_science()`） |
| `python-docx` | Word 路线排版（1.2.0 已装） |
| `fitz`（PyMuPDF） | PDF 页面检查/渲染（layout_audit/style_audit 依赖） |

## 工作流程

### Step 1：检测当前平台

```bash
case "$(uname -s)" in
  Darwin) echo "PLATFORM=mac" ;;
  Linux)  echo "PLATFORM=linux" ;;
  MINGW*|MSYS*|CYGWIN*) echo "PLATFORM=windows" ;;
  *)      echo "PLATFORM=unknown" ;;
esac
```

Windows 下优先使用 winget，备用 scoop 或 choco。Linux 下优先使用 apt（Debian/Ubuntu），备用 dnf（Fedora/RHEL）或 pacman（Arch）。  
检测包管理器：

```bash
# Linux 发行版检测
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "DISTRO=$ID"
fi
# Windows 包管理器检测（在 Git Bash / PowerShell 中）
command -v winget >/dev/null 2>&1 && echo "PKG=winget"
command -v scoop  >/dev/null 2>&1 && echo "PKG=scoop"
command -v choco  >/dev/null 2>&1 && echo "PKG=choco"
```

### Step 2：检查所有工具

```bash
check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "OK  $1 ($(command -v "$1"))"
  else
    echo "MISS $1"
  fi
}

check_cmd typst
check_cmd xelatex
check_cmd python3 || check_cmd python   # Windows 上可能是 python
command -v drawio >/dev/null 2>&1 || command -v draw.io >/dev/null 2>&1 \
  && echo "OK  drawio" || echo "MISS drawio"
check_cmd pdftoppm
check_cmd mutool
check_cmd magick

python3 - <<'PYEOF'
import importlib
pkgs = ["numpy", "scipy", "pandas", "matplotlib", "sklearn", "openpyxl"]
for p in pkgs:
    try:
        importlib.import_module(p)
        import importlib.metadata as meta
        try:
            ver = meta.version(p if p != "sklearn" else "scikit-learn")
        except Exception:
            ver = "?"
        print(f"OK  {p} ({ver})")
    except ImportError:
        print(f"MISS {p}")
PYEOF
```

### Step 3：输出检查报告

将结果整理展示：

```
状态   工具/包              说明
----   --------             ----
✓      typst 0.13.0         论文编译
✗      drawio               DrawIO 导出 PDF（可选）
✓      python3 3.11.x       数值计算
✗      scipy                科学计算（可选）
...
```

**必须项：** typst 或 xelatex（至少一个论文编译器）、python3、numpy、pandas、matplotlib  
**可选项：** drawio、pdftoppm/mutool/magick 三选一、scipy、scikit-learn、openpyxl

### Step 4：提供安装命令（按平台）

仅对缺失项输出对应平台的命令。

#### typst

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install typst` |
| Linux (apt) | `snap install typst` 或从 GitHub Releases 下载二进制 |
| Linux (arch) | `pacman -S typst` |
| Windows (winget) | `winget install Typst.Typst` |
| Windows (scoop) | `scoop install typst` |
| 通用 | `cargo install --locked typst-cli`（需要 Rust） |

#### xelatex（TeX 发行版）

xelatex 包含在主流 TeX 发行版中（TeX Live / MiKTeX / MacTeX）。安装发行版即可获得 xelatex。

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install --cask mactex` 或 `brew install texlive` |
| Linux (apt) | `sudo apt install texlive-full` |
| Linux (dnf) | `sudo dnf install texlive-scheme-full` |
| Linux (arch) | `sudo pacman -S texlive` |
| Windows (winget) | `winget install MiKTeX.MiKTeX` 或 `winget install TeXLive` |
| Windows (scoop) | `scoop install latex`（需先添加 extras bucket） |

注意：`texlive-full` 体积较大（约 5GB），如需精简可只装 `texlive-xetex` + `texlive-lang-chinese`（中文支持）。

#### Python 3

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install python` |
| Linux (apt) | `sudo apt install python3 python3-pip` |
| Linux (dnf) | `sudo dnf install python3 python3-pip` |
| Windows | `winget install Python.Python.3` 或从 python.org 下载安装包 |

#### Python 包（批量安装缺失项）

```bash
pip3 install <缺失的包>
# Windows: pip install <缺失的包>
# 例如: pip3 install scipy scikit-learn openpyxl
```

#### drawio

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install --cask drawio` |
| Linux | 从 https://github.com/jgraph/drawio-desktop/releases 下载 AppImage 或 deb |
| Windows | `winget install JGraph.Draw` 或从上述页面下载安装包 |

#### pdftoppm（来自 poppler）

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install poppler` |
| Linux (apt) | `sudo apt install poppler-utils` |
| Linux (dnf) | `sudo dnf install poppler-utils` |
| Windows | `winget install oschwartz10612.poppler` 或 `scoop install poppler` |

#### mutool（来自 mupdf）

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install mupdf` |
| Linux (apt) | `sudo apt install mupdf-tools` |
| Windows | `scoop install mupdf` 或从 mupdf.com 下载 |

#### ImageMagick

| 平台 | 命令 |
| --- | --- |
| macOS | `brew install imagemagick` |
| Linux (apt) | `sudo apt install imagemagick` |
| Linux (dnf) | `sudo dnf install imagemagick` |
| Windows | `winget install ImageMagick.ImageMagick` 或 `choco install imagemagick` |

### Step 5：询问用户是否安装

列出所有缺失的**必须项**后，询问用户：

> 以上必须项缺失，是否现在安装？(y/N)

- 若用户确认，按检测到的平台依次执行安装命令，每步完成后打印结果。
- 若用户拒绝或只有可选项缺失，打印可手动执行的命令列表并退出。
- 安装完成后重新运行 Step 2，确认已生效。

### Step 6：最终摘要

```
Doctor 检查完成（macOS）
必须项：5/5 ✓
可选项：2/4（drawio、scipy 缺失）

工作流就绪状态：
  1start-mathmodel   ✓
  2analysis-modeling ✓
  3coding-visual     ✓
  4drawio            ✓（drawio 无 CLI → TikZ 模板 + mmdc 渲染）
  5writing           ✓（xelatex ✓ / typst ✓ / Word COM ✓）
  6verity            ✓（PDF 转 PNG 用 mgs.exe）
```

## 编译错误诊断决策树（吸收 latex-engineer 能力：现象→修法，不盲目重试）

论文编译失败时按此表对照；同一命令原样重试 ≤2 次，第 3 次必须换写法。

| 现象 | 原因 | 修法 |
| --- | --- | --- |
| `dvipdfmx:fatal: Unable to open main.pdf` | PDF 被查看器占用 | 关闭查看器；或 `-job-name=main2` 换输出名 |
| `Couldn't open 'OT:script=hani;language=dfl.cfg'` | ctex fontset 指向本机没有的字体（如 mac 字体族） | fontset=none + `\newCJKfontfamily` 按本机字体定义（cumcm-latex 模板已内置自动选择） |
| `miktex-makemf did not succeed` / `Men.cfg` | Menlo 等宽字体缺失的**无害回退** | 确认 PDF 已正常生成即可忽略 |
| `major issue: not checked for updates` | MiKTeX 更新提示 | 无害，忽略 |
| `Undefined control sequence` | 宏包缺失或拼写错误 | 补/改 `\usepackage` 包名；MiKTeX 按需装包 |
| `File xxx not found` | 路径/文件名不对 | `Test-Path` 核实；检查 `\graphicspath` 与相对路径 |
| Overfull hbox | 行内不可断 token 硬越界 | `\emergencystretch=2em`（模板已设）+ 长 token 插 `\allowbreak`；>15pt 会被 layout_audit FAIL |
| 中文豆腐块/乱码 | 字体缺失或引擎错 | 中文必须 xelatex；字体回退列表放本机字体（SimSun/SimHei/KaiTi） |
| 页码/引用显示 ?? | 编译遍数不够 | xelatex 跑两遍 |
| Typst `unclosed delimiter`/`unknown variable`/`expected content` | Typst 语法 | 四坑：函数名禁连字符（用下划线）、内容块内 `/*` 是块注释（写 `\*`）、先定义后使用、表格数字用字符串 |
| Typst `unknown font family` | 字体回退 | 无害警告；hei-font 首项已改 SimHei |

修完后必须重跑对应程序门（style_audit / layout_audit / trace）再宣布通过。

## 注意事项

- 执行安装前必须获得用户明确确认，不得静默安装。
- Windows 下建议在 PowerShell（管理员）或 Git Bash 中运行，部分命令需要管理员权限。
- Linux 的 `sudo` 命令会请求密码，执行前告知用户。
- drawio 已弃用（本机无 CLI）：4drawio 阶段用 TikZ 模板 + mermaid（mmdc）渲染；PDF 转 PNG 用 MiKTeX 自带的 `mgs.exe`。
- 如平台检测为 unknown，打印所有平台命令供用户手动选择。
