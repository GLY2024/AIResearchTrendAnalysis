# ARTA

ARTA 是一个面向学术调研场景的桌面应用，用来把“选题讨论”逐步推进到“检索计划、文献库、趋势分析和报告导出”。项目采用 `Vue 3 + Vite + Tauri` 构建桌面端，后端为 `FastAPI + SQLite + WebSocket`，当前已经支持安装版和 portable 版。

## 适合做什么

- 用聊天方式梳理题目、缩小范围、形成检索计划
- 审批、修改并执行 Search Plan
- 汇总 OpenAlex、arXiv、Scopus 等来源的文献
- 在 Library 中分页筛选、纳入/排除和管理语料
- 运行趋势、关键词、主题等分析任务
- 生成报告，并导出 `.bib` / `.ris`
- 以基础检索语料为主语料，避免历史扩展数据把结果污染

## 当前版本的关键改动

- 当前版本只基于基础检索结果进入 Library、Analysis 和 Report
- Chat 现在可以看到搜索、分析、报告的阶段性进展
- Library 改成真正分页，支持 `10 / 20 / 50` 每页和翻页访问全量数据
- 失败的聊天消息会显示具体错误信息，并支持重试和删除
- 报告和分析解释支持默认输出语言配置，当前可选中文或英文
- 导出按钮已接通后端，支持 `.bib` 和 `.ris`
- 数据库默认固定到 `backend/data/research.db`，避免不同启动方式写到不同库

## 项目结构

```text
ARTA/
├─ backend/                  FastAPI 后端、数据库、agents、数据源接入
│  ├─ app/
│  │  ├─ agents/             planner / executor / analyst / publisher
│  │  ├─ api/                REST API 与 WebSocket
│  │  ├─ db/                 SQLAlchemy 模型与数据库初始化
│  │  ├─ services/           AI、导出、业务服务
│  │  └─ sources/            OpenAlex / arXiv / Scopus 等数据源
│  └─ data/                  默认数据库目录
├─ frontend/                 Vue 3 + Tauri 前端
│  ├─ src/
│  │  ├─ views/              Chat / Search Plan / Library / Analysis / Report / Settings
│  │  ├─ components/         通用卡片、聊天组件、图表组件
│  │  ├─ composables/        API、WebSocket、后端状态、图表逻辑
│  │  └─ stores/             会话状态
│  └─ src-tauri/             Tauri 打包配置与 sidecar 集成
├─ run_backend.py            从仓库根目录启动后端
├─ build.py                  一键构建 backend sidecar + Tauri
└─ pack_portable.py          组装 portable 分发目录
```

## 运行环境

- `Python 3.11+`
- `Node.js 20+`
- Windows 打包需要：
  - Rust toolchain
  - Tauri 依赖
  - Visual Studio C++ Build Tools

## 本地开发

### 1. 安装依赖

后端推荐使用 `uv`：

```powershell
cd backend
uv sync
```

前端：

```powershell
cd frontend
npm install
```

### 2. 启动后端

从仓库根目录启动最稳妥，默认监听 `127.0.0.1:8721`：

```powershell
uv run python run_backend.py
```

如果你已经在本地激活了 Python 环境，也可以直接：

```powershell
python run_backend.py
```

### 3. 启动前端

```powershell
cd frontend
npm run dev
```

开发模式下，前端默认运行在 `http://localhost:5173`，通过 HTTP + WebSocket 与后端通信。

## 打包与分发

### 构建安装版

Windows 下可以直接使用项目里现成脚本：

```powershell
frontend\build_tauri.bat
```

默认产物位置：

- `frontend/src-tauri/target/release/bundle/msi/`
- `frontend/src-tauri/target/release/bundle/nsis/`

### 构建 portable 版

先确保安装版主程序和 backend sidecar 已经构建完成，再执行：

```powershell
uv run python pack_portable.py
```

默认产物位置：

- `dist/ARTA-portable/`

### 一键构建

如果你希望直接从根目录完成 backend sidecar + Tauri 构建：

```powershell
uv run python build.py
```

## 配置与数据

- 默认数据库位置：`backend/data/research.db`
- 可以通过环境变量 `ARTA_DATA_DIR` 覆盖数据目录
- LLM Provider、模型分配、Scopus key、默认输出语言都在 `Settings` 页面配置
- portable 版本会在分发目录下维护自己的 `data/` 子目录

## 典型工作流

1. 在 `Chat` 页面明确调研主题，必要时直接生成 Search Plan。
2. 在 `Search Plan` 页面审批、编辑或拒绝计划，再执行检索。
3. 在 `Library` 页面筛选和确认纳入文献。
4. 在 `Analysis` 页面运行趋势、关键词、网络等分析。
5. 在 `Report` 页面生成汇总报告，并导出引用文件。
6. 如需扩大语料，建议先回到 Search Plan 补充检索词，而不是直接混入额外扩展结果。

## 已知注意点

- `Scopus` 依赖额外 API key，没有配置时不会返回有效结果。
- Tauri 当前 `identifier` 仍是 `com.arta.app`，虽然不影响 Windows 打包，但后续可进一步规范。
- 大规模语料会显著拉长部分图表和网络分析时间，演示时建议先用经过筛选的语料集。
