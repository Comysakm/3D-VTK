# 3D-VTK

一个基于 VTK.js 的前后端三维可视化项目，用于展示和交互式操作 3D 体素/点云数据。项目通过前端（Vue3 + Vite）提供交互界面，后端（Flask）处理点云数据生成，支持高效的 3D 可视化和用户交互。

## 📖 项目概述

3D-VTK 是一个前后端分离的 Web 应用，旨在从体视显微镜数据（如 Saltf 文件）生成点云，并通过 VTK.js 在浏览器中进行三维渲染。用户可以通过前端界面输入参数（如最小值和最大值），筛选点云数据，并以 PLY 格式获取和可视化结果。项目支持跨域请求、鼠标交互显示坐标，并计划优化性能（如 gzip 压缩、Numba 加速）。

### 功能特性
- **点云生成**：后端从 Saltf 文件生成 PLY 格式点云，支持范围筛选。
- **3D 可视化**：前端使用 VTK.js 渲染点云，支持颜色映射和鼠标交互。
- **交互式界面**：Vue3 提供用户友好的控制面板，用于输入参数和显示加载进度。
- **跨域支持**：后端启用 CORS，方便前端跨域访问。
- **性能优化**（可选）：支持 gzip 压缩、Numba 加速和数据缓存（在优化版本中）。

## 📁 项目结构

```
3D-VTK/
├── frontend/                # 前端代码目录
│   ├── src/                # Vue3 源代码
│   ├── package.json        # 前端依赖配置
│   └── vite.config.js      # Vite 配置文件
├── backend/                # 后端代码目录
│   ├── app.py             # Flask 主应用
│   ├── requirements.txt    # 后端依赖列表
│   └── Saltf               # 输入数据文件（需自行提供）
├── README.md               # 项目文档
└── .gitignore              # Git 忽略文件配置
```

## 🧰 技术栈

| 组件       | 技术         | 用途                           |
|------------|--------------|--------------------------------|
| **前端**   | Vue3         | 构建响应式用户界面             |
|            | Vite         | 快速构建和热重载工具           |
|            | VTK.js       | 3D 点云渲染和交互             |
|            | Axios        | HTTP 请求处理                 |
|            | Pako         | 解压后端返回的 gzip 文件       |
| **后端**   | Flask        | 轻量级 Web 框架               |
|            | NumPy        | 数据处理和网格生成             |
|            | Plyfile      | 生成 PLY 格式点云文件         |
|            | Flask-CORS   | 支持跨域请求                  |

## 🚀 快速开始

### 前提条件
- **Node.js**：版本 16.x 或以上（推荐 18.x）。
- **Python**：版本 3.8 或以上。
- **Conda**（可选）：用于管理 Python 虚拟环境。
- **Saltf 文件**：后端需要一个有效的 Saltf 文件（大端浮点数格式，尺寸为 210×676×676）。

### 1. 安装和运行前端

1. **进入前端目录**：
   ```bash
   cd frontend
   ```

2. **安装依赖**：
   ```bash
   npm install
   ```
   确保安装以下关键依赖：
   - `@kitware/vtk.js`
   - `axios`
   - `pako`（用于解压 `.ply.gz` 文件）

3. **启动开发服务器**：
   ```bash
   npm run dev
   ```

4. **访问前端**：
   打开浏览器，访问 `http://localhost:5173`（端口可能因 Vite 配置而异）。

### 2. 安装和运行后端

1. **进入后端目录**：
   ```bash
   cd backend
   ```

2. **创建并激活 Conda 环境**（可选，推荐）：
   ```bash
   conda create -n vtk_env python=3.8
   conda activate vtk_env
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```
   `requirements.txt` 示例内容：
   ```
   flask==2.0.1
   numpy==1.21.0
   plyfile==0.7.4
   flask-cors==3.0.10
   ```

4. **准备 Saltf 文件**：
   - 确保 `Saltf` 文件位于 `backend/` 目录下，或修改 `app.py` 中的 `input_file` 路径。
   - 文件应为大端浮点数（`>f4`）格式，尺寸为 `210×676×676`。

5. **启动后端服务**：
   ```bash
   python app.py
   ```
   服务默认运行在 `http://localhost:5000`。

### 3. 使用应用
1. 打开前端页面（`http://localhost:5173`）。
2. 在控制面板输入 `Minimum Value` 和 `Maximum Value`（例如，1500 和 4500）。
3. 点击 `Generate and Render` 按钮，触发点云生成和渲染。


