# 3D‑VTK

一个基于 [VTK.js (Visualization Toolkit)](https://kitware.github.io/vtk-js/) 的前后端三维可视化工程，用于展示和交互式操作 3D 体素/点云数据。

## 📁 项目结构

3D‑VTK/
├── frontend/ # 前端代码（例如 Vue3 + Vite）
├── backend/ # 后端代码（例如 Flask/FastAPI 等）
├── README.md # 本文档
└── .gitignore # 忽略文件配置


## 🧰 技术栈

- **前端**：Vue3 + Vite 
- **后端**：Python Flask
- **3D 可视化**：VTK.js

## 🚀 快速开始

### 前端运行

cd frontend
npm install
npm run dev
然后浏览器打开 http://localhost:5173

### 后端运行

cd backend
conda activate your_env
pip install -r requirements.txt
python app.py
