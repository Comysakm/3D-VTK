# -*- coding: utf-8 -*-
"""
功能概述：
    基于 Flask 的 Web 服务接口，从本地 Saltf 三维体数据生成带颜色的点云（PLY）。
    在基本点云生成功能基础上，新增对强度值进行归一化并映射为颜色（支持多种 matplotlib colormap）。

主要特性：
    - 接收前端 JSON 参数：min_val、max_val（数值筛选范围）、colormap（颜色映射名称）。
    - 读取 Saltf 文件（大端 float32），重构体数据并构建三维坐标网格。
    - 根据阈值范围筛选点，将体素值归一化后映射到颜色（RGB，uint8）。
    - 以 PLY（小端二进制）格式返回点云文件（包含 x/y/z + r/g/b）。

接口：
    POST /generate-ply
        Body(JSON): { "min_val": float, "max_val": float, "colormap": "grayscale" | "magma" | "coolwarm" | "plasma" | ... }
        Resp(File):  application/octet-stream（pointcloud.ply）

依赖：
    - Flask, flask_cors
    - numpy
    - plyfile
    - matplotlib（仅用于 colormap 取色）
    - Python 3.x

注意与限制：
    - Saltf 文件需与脚本同目录（或修改 input_file）。
    - 阈值范围若筛选不到任何点，当前代码会在归一化前对 values_vals.min()/max() 调用导致异常（空数组求 min/max）。
      *保持原逻辑*：本文件未调整执行顺序；生产中建议先判断筛选结果是否为空，再做归一化与配色。
    - brightness_factor 调低亮度，提升细节辨识度（可按需调整或暴露为参数）。
    - 大数据集（210×676×676）内存占用与计算量较大，部署时注意内存与响应时间。
"""

from flask import Flask, request, Response, send_file
from io import BytesIO
import numpy as np
from plyfile import PlyData, PlyElement
from flask_cors import CORS
import os
import matplotlib.pyplot as plt  # noqa: F401  # 仅用于确保 matplotlib 后端可用
from matplotlib import cm        # 用于获取 colormap

# ===== 路径与应用初始化 =====
# 获取当前脚本所在目录的绝对路径，便于定位同目录资源文件（Saltf）
current_dir = os.path.dirname(os.path.abspath(__file__))

# 初始化 Flask 应用并开启 CORS（允许跨域请求，便于前端在不同域访问）
app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    """健康检查与提示信息。"""
    return "点云服务已启动，可访问 /generate-ply 接口生成 PLY 文件", 200

@app.route('/generate-ply', methods=['POST'])
def generate_ply():
    """
    接口：/generate-ply（POST）
    功能：按阈值筛选体素点，并基于强度值映射颜色，导出带 RGB 的 PLY 点云。

    请求体(JSON)：
        {
            "min_val": <float>,           # 最小阈值（包含）
            "max_val": <float>,           # 最大阈值（包含）
            "colormap": "grayscale" | "magma" | "coolwarm" | "plasma" | ...  # 颜色映射名称，可选，默认 grayscale
        }

    返回：
        - 成功：application/octet-stream，附件名 pointcloud.ply
        - 失败：400/500 + 文本错误说明

    备注：
        - 颜色映射使用 matplotlib.cm；灰度模式为手动线性映射。
        - 亮度通过 brightness_factor 调整，避免过曝。
    """
    # ===== 1) 读取请求参数 =====
    data = request.get_json()
    min_val = data.get('min_val')
    max_val = data.get('max_val')
    colormap_name = data.get('colormap', 'grayscale')

    # 调试输出：便于在服务端日志中追踪调用参数
    print(f'max_val={max_val}, min_val={min_val}, colormap={colormap_name}')

    # 基本参数校验：检查数值类型与范围关系
    if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
        return Response('无效的 min_val 或 max_val 参数，必须为数值', status=400)
    if min_val >= max_val:
        return Response('min_val 必须小于 max_val', status=400)

    # ===== 2) 数据体维度与文件路径配置 =====
    input_file = os.path.join(current_dir, 'Saltf')  # Saltf 文件路径（与脚本同目录）
    n1, n2, n3 = 210, 676, 676                       # 体素维度（X, Y, Z）
    spacing = (20.0, 20.0, 20.0)                     # 各轴方向物理间距（单位：同源数据单位，示例 mm）
    origin = (0.0, 0.0, 0.0)                         # 原点坐标（用于生成物理坐标）

    # ===== 3) 读取并重构 Saltf 数据 =====
    try:
        # 按大端 float32（>f4）直接读取为一维数组
        data = np.fromfile(input_file, dtype=">f4")
        expected_size = n1 * n2 * n3
        if len(data) != expected_size:
            # 文件体素数与期望不一致，通常表示源数据尺寸或 dtype 配置错误
            return Response(f"预期数据点数 {expected_size}，实际得到 {len(data)}", status=500)

        # 重塑为三维数组并转为小端 float32（提升后续 numpy 操作兼容性/性能）
        data = data.reshape((n3, n2, n1))
        data = data.byteswap().view(np.float32)
    except Exception as e:
        # 捕获文件读取与 reshape 过程中的异常
        return Response(f"读取文件失败: {str(e)}", status=500)

    # ===== 4) 生成三维物理坐标网格 =====
    # np.linspace 生成等间隔物理坐标；长度等于对应轴体素数
    x = np.linspace(origin[0], origin[0] + spacing[0] * (n1 - 1), n1)
    y = np.linspace(origin[1], origin[1] + spacing[1] * (n2 - 1), n2)
    z = np.linspace(origin[2], origin[2] + spacing[2] * (n3 - 1), n3)
    # indexing='ij' 确保 X/Y/Z 轴顺序对应 (X->n1, Y->n2, Z->n3)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # 将坐标网格与体素值展平为一维，便于向量化筛选
    X_flat = X.flatten()
    Y_flat = Y.flatten()
    Z_flat = Z.flatten()
    values_flat = data.flatten()

    # ===== 5) 阈值筛选体素点 =====
    mask = (values_flat >= min_val) & (values_flat <= max_val)
    x_vals = X_flat[mask]
    y_vals = Y_flat[mask]
    z_vals = Z_flat[mask]
    values_vals = values_flat[mask]

    # ===== 6) 归一化与颜色映射 =====
    # 注意：若 values_vals 为空，values_vals.min()/max() 将报错。
    scalar_min = values_vals.min()
    scalar_max = values_vals.max()
    scalar_range = scalar_max - scalar_min
    if scalar_range == 0:
        normalized = np.zeros_like(values_vals)
    else:
        normalized = (values_vals - scalar_min) / scalar_range

    # 选择颜色映射方案：
    # - grayscale：手动将 normalized 映射到 [0,255] 的灰度，R=G=B
    # - 其他：使用 matplotlib.cm.get_cmap(colormap_name)，返回 RGBA（取前三通道）
    if colormap_name == 'grayscale':
        r = g = b = (normalized * 255).astype(np.uint8)
    else:
        try:
            colormap = cm.get_cmap(colormap_name)         # e.g. 'magma', 'coolwarm', 'plasma', ...
            rgba_colors = colormap(normalized)            # shape: (N, 4)
            r = (rgba_colors[:, 0] * 255).astype(np.uint8)
            g = (rgba_colors[:, 1] * 255).astype(np.uint8)
            b = (rgba_colors[:, 2] * 255).astype(np.uint8)
        except ValueError:
            # colormap 名称无效时给出提示
            return Response(
                f"无效的 colormap 参数: {colormap_name}，支持 'grayscale', 'magma', 'coolwarm', 'plasma' 等",
                status=400
            )

    # 亮度调整：整体乘以 brightness_factor，数值越小画面越暗，细节层次更明显
    brightness_factor = 0.8
    r = (r * brightness_factor).astype(np.uint8)
    g = (g * brightness_factor).astype(np.uint8)
    b = (b * brightness_factor).astype(np.uint8)

    # ===== 7) 组织 PLY 顶点数据（带 RGB） =====
    # 结构化 dtype：x/y/z 为 float32，颜色通道为 uint8
    vertices = np.zeros(
        len(x_vals),
        dtype=[
            ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')
        ]
    )
    vertices['x'] = x_vals
    vertices['y'] = y_vals
    vertices['z'] = z_vals
    vertices['red'] = r
    vertices['green'] = g
    vertices['blue'] = b

    # PLY 顶点元素与数据对象（text=False -> 二进制；byte_order='<' -> 小端）
    element = PlyElement.describe(vertices, 'vertex')
    ply_data = PlyData([element], text=False, byte_order='<')

    # 调试信息：元素数量与样例点打印
    print(f"PLY 数据元素数: {ply_data.__len__()}")
    print(f"筛选后的点数，范围 [{min_val}, {max_val}]: {len(x_vals)}")
    print("前 20 个点的坐标和强度值 (x, y, z, intensity):")
    for i in range(min(20, len(x_vals))):
        print(f"点 {i}: x={x_vals[i]:.2f}, y={y_vals[i]:.2f}, z={z_vals[i]:.2f}, intensity={values_vals[i]:.2f}")

    # 逻辑提示：此处才判断“无点”会晚于 min/max，若为空会在更早处抛错
    # *保持原逻辑*，不调整顺序
    if len(x_vals) == 0:
        print("在指定范围内未找到点。")
        return Response(f"在范围 [{min_val}, {max_val}] 内未找到点", status=400)

    # ===== 8) 写入内存并返回为附件下载 =====
    output = BytesIO()
    ply_data.write(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name='pointcloud.ply'
    )

if __name__ == '__main__':
    # 开发模式启动：监听 0.0.0.0:5000，并开启调试
    app.run(host='0.0.0.0', port=5000, debug=True)
