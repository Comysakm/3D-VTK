# -*- coding: utf-8 -*-
"""
功能概述：
    基于 Flask 的 Web 服务接口，从本地 Saltf 格式文件生成点云数据，并以 PLY 格式返回给前端。
    提供按数值范围筛选点云的能力，适合与前端三维可视化（如 vtk.js）配合使用。

主要功能：
    1. 接收前端 POST 请求，包含 min_val / max_val（筛选阈值范围）。
    2. 读取 Saltf 文件（大端浮点数格式），重构为三维体数据。
    3. 生成对应的三维坐标网格，与体素值一一对应。
    4. 按阈值范围筛选符合条件的点，构建 PLY 格式点云。
    5. 将点云文件通过 HTTP 以附件形式返回给前端。
    6. 支持 CORS 跨域请求。

依赖：
    - Flask：Web 框架
    - flask_cors：跨域支持
    - numpy：数值运算
    - plyfile：生成 PLY 文件
    - Python 3.x

运行条件：
    - 本地必须存在 Saltf 文件（大端 float32 格式）。
    - Python 环境已安装上述依赖包。
    - 服务运行在 0.0.0.0:5000，默认开启 debug 模式。
"""

from flask import Flask, request, Response, send_file
from io import BytesIO
import numpy as np
from plyfile import PlyData, PlyElement
from flask_cors import CORS

# 初始化 Flask 应用，并开启 CORS（允许跨域请求）
app = Flask(__name__)
CORS(app)

@app.route('/generate-ply', methods=['POST'])
def generate_ply():
    """
    接口路径：/generate-ply
    请求方式：POST
    请求体格式：JSON
        {
            "min_val": <float>,  # 最小筛选值
            "max_val": <float>   # 最大筛选值
        }
    功能：
        - 从 Saltf 文件读取 3D 数据，根据 min_val 和 max_val 筛选出符合条件的点云。
        - 将点云转换为 PLY 二进制格式，并以附件形式返回。
    返回：
        - 成功：HTTP 200，Content-Type: application/octet-stream，文件名 pointcloud.ply
        - 失败：HTTP 400 或 500，返回错误描述。
    """
    # 获取并解析 JSON 请求参数
    data = request.get_json()
    min_val = data.get('min_val')
    max_val = data.get('max_val')

    # 调试输出请求参数
    print(f"max_val = {max_val}")
    print(f"min_val = {min_val}")

    # 参数校验：必须是数值类型，且 min_val < max_val
    if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
        return Response('无效的 min_val 或 max_val 参数，必须为数值', status=400)
    if min_val >= max_val:
        return Response('min_val 必须小于 max_val', status=400)

    # ===== 配置点云数据文件与维度信息 =====
    input_file = "Saltf"                # 输入文件路径
    n1, n2, n3 = 210, 676, 676          # 数据体素维度（X, Y, Z）
    spacing = (20.0, 20.0, 20.0)        # 各轴方向点间距 (mm)
    origin = (0.0, 0.0, 0.0)            # 原点坐标

    # ===== Step1: 读取 Saltf 文件 =====
    try:
        # 从文件读取大端浮点数 (>f4)，返回 1D 数组
        data = np.fromfile(input_file, dtype=">f4")
        expected_size = n1 * n2 * n3
        if len(data) != expected_size:
            return Response(f"预期数据点数 {expected_size}，实际得到 {len(data)}", status=500)
        # 重塑为 3D 数组 (Z, Y, X)，并转为小端 float32
        data = data.reshape((n3, n2, n1))
        data = data.byteswap().view(np.float32)
    except Exception as e:
        return Response(f"读取文件失败: {str(e)}", status=500)

    # ===== Step2: 生成 3D 坐标网格 =====
    # np.linspace 生成等间距坐标，长度等于对应轴上的点数
    x = np.linspace(origin[0], origin[0] + spacing[0] * (n1 - 1), n1)
    y = np.linspace(origin[1], origin[1] + spacing[1] * (n2 - 1), n2)
    z = np.linspace(origin[2], origin[2] + spacing[2] * (n3 - 1), n3)
    # meshgrid 生成坐标网格（indexing='ij' 确保 X/Y/Z 维度对应）
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # ===== Step3: 展平坐标和体素值 =====
    X_flat, Y_flat, Z_flat = X.flatten(), Y.flatten(), Z.flatten()
    values_flat = data.flatten()

    # ===== Step4: 按阈值范围筛选点 =====
    mask = (values_flat >= min_val) & (values_flat <= max_val)
    x_vals = X_flat[mask]
    y_vals = Y_flat[mask]
    z_vals = Z_flat[mask]
    values_vals = values_flat[mask]

    # ===== Step5: 构造 PLY 数据 =====
    # 顶点结构包含 x/y/z 三维坐标及 scalar 强度值
    vertices = np.zeros(
        len(x_vals),
        dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'), ('scalar', 'f4')]
    )
    vertices['x'] = x_vals
    vertices['y'] = y_vals
    vertices['z'] = z_vals
    vertices['scalar'] = values_vals

    # 描述顶点元素，并封装为 PLY 数据对象（小端二进制）
    element = PlyElement.describe(vertices, 'vertex')
    ply_data = PlyData([element], text=False, byte_order='<')

    # 调试输出：点数量
    print(f"筛选后的点数：{len(x_vals)}")
    # 调试输出：前 20 个点信息
    for i in range(min(20, len(x_vals))):
        print(f"点 {i}: x={x_vals[i]:.2f}, y={y_vals[i]:.2f}, z={z_vals[i]:.2f}, intensity={values_vals[i]:.2f}")

    # 若没有符合条件的点，直接返回错误
    if len(x_vals) == 0:
        return Response(f"在范围 [{min_val}, {max_val}] 内未找到点", status=400)

    # ===== Step6: 写入内存流并返回 =====
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
    """
    启动 Flask 服务
    host='0.0.0.0' 表示监听所有网络接口
    port=5000       默认端口
    debug=True      开启调试模式
    """
    app.run(host='0.0.0.0', port=5000, debug=True)
