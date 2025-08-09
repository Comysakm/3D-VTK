# Flask VTK 数据服务

🧭 本项目提供基于 Flask 的 VTK 数据服务，包含点云和体数据的生成与处理，逐步优化以支持前端渲染需求。

## 🪜 演进路径

- **初始：PLY 点云渲染（pointcloud_ply_generate_service.py）**  
  输出顶点坐标（x,y,z）及 scalar 字段，但前端无法读取标量值，导致无法基于标量着色。  
  **改进**：引入 pointcloud_ply_generate_colormap_service.py，将标量映射为 RGB。

- **改进：PLY+RGB（pointcloud_ply_generate_colormap_service.py）**  
  后端完成标量归一化与颜色映射，输出带 RGB 的 PLY。属于临时方案，依旧无法解决前端无法读取标量值的问题。  
  **改进**：引入 pointcloud_vtp_generate_service.py，使用 VTP 并增加日志。

- **改进：VTP+标量（pointcloud_vtp_generate_service.py）**  
  弃用ply格式，采用 VTK PolyData（含标量），支持前端读取标量值，支持 gzip 压缩，提供耗时与压缩比日志，但点云数据量大时传输开销高。 
  **⚠️ 重要：由于项目要求使用点云格式，所以此版本为最终版本。为测试体素格式的性能，引入 voxel_vti_generate_service.py，转换为规则体数据用以测试。**

- **测试：VTI 体数据（voxel_vti_generate_service.py）**
  **⚠️ 重要：此版本为测试体素格式性能所用，不应用与项目中。输出 VTK ImageData，支持体渲染/切片/等值面，Numba 加速阈值处理，线程封装写出与压缩。**

## 🧩 各脚本功能

- **pointcloud_ply_generate_service.py（PLY · 几何渲染）**  
  **输入**：min_val/max_val  
  **处理**：筛选体素点，生成坐标网格  
  **输出**：二进制 PLY（x,y,z,scalar）  
  **用途**：验证点云渲染链路

- **pointcloud_ply_generate_colormap_service.py（PLY · 顶点颜色）**  
  **输入**：min_val/max_val、colormap  
  **处理**：标量归一化，映射 RGB  
  **输出**：二进制 PLY（x,y,z,RGB）  
  **用途**：前端彩色渲染

- **pointcloud_vtp_generate_service.py（VTP.gz · 标量+日志）**  
  **输入**：min_val/max_val  
  **处理**：缓存坐标与标量，组装 PolyData，gzip 压缩  
  **输出**：pointcloud.vtp.gz，/save-log  
  **用途**：散点渲染+数值读取

- **voxel_vti_generate_service.py（VTI.gz · 规则体数据）**  
  **输入**：min_val/max_val  
  **处理**：Numba 加速阈值处理，构建 ImageData  
  **输出**：pointcloud.vti.gz  
  **用途**：体渲染/切片/等值面

## 🗃️ 数据格式差异

| 格式 | 本质             | 典型内容                  | 前端场景            | 体量/性能             | 标量可读 |
|------|------------------|--------------------------|--------------------|----------------------|----------|
| PLY  | 纯点云           | 顶点坐标，选配 RGB       | 散点渲染（快速）   | 点数大体积大         | 不支持 |
| VTP  | VTK PolyData     | Points+ScalarValue+Verts | 散点+数值读取      | 二进制+gzip，带日志  | ✅       |
| VTI  | 规则体数据       | dims/spacing+ScalarValue | 体渲染/切片/等值面 | 二进制+gzip，适合体数据 | ✅       |

## 🔌 接口速览

```http
POST /generate-ply  # pointcloud_service.py (PLY: x,y,z,scalar)
POST /generate-ply  # pointcloud_colormap_service.py (PLY: x,y,z,RGB)
POST /generate-vtp  # vtp_verts_service.py (VTP.gz: Points+ScalarValue+Verts)
POST /save-log      # vtp_verts_service.py (保存日志)
POST /generate-vti  # vti_volume_service.py (VTI.gz: 规则体数据)



