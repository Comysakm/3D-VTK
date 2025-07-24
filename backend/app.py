# -*- coding: utf-8 -*-
"""
功能说明：
这是一个基于 Flask 的 Web 服务，用于从 Saltf 文件生成点云数据并返回 PLY 格式文件。
主要功能：
1. 接收前端发送的 POST 请求，包含 min_val 和 max_val 参数，用于筛选点云数据。
2. 读取 Saltf 文件，生成 3D 坐标网格。
3. 根据 min_val 和 max_val 筛选点云数据，生成 PLY 文件。
4. 将生成的 PLY 文件以二进制流形式返回给前端。
5. 支持跨域请求（CORS），便于前端访问。

逻辑流程：
1. 初始化 Flask 应用，启用 CORS 支持。
2. 验证请求参数（min_val, max_val）的有效性。
3. 读取 Saltf 文件并验证数据完整性。
4. 生成 3D 坐标网格，展平为 1D 数组。
5. 根据参数筛选点云数据，构造 PLY 文件格式。
6. 将 PLY 文件写入内存流并返回。
7. 记录筛选点数和部分点信息，便于调试。

运行环境：
- 需要安装 Flask、numpy、plyfile 和 flask_cors 库。
- Saltf 文件需位于正确路径，且格式为大端浮点数（>f4）。
- 服务运行在 0.0.0.0:5000，支持调试模式。
"""

from flask import Flask, request, Response, send_file
from io import BytesIO
import numpy as np
from plyfile import PlyData, PlyElement
from flask_cors import CORS
import os

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)  # 启用 CORS，支持跨域请求，允许前端从不同域名访问服务

@app.route('/generate-ply', methods=['POST'])
def generate_ply():
    """
    处理点云生成请求，生成并返回 PLY 文件。
    功能：
    - 接收 JSON 格式的 POST 请求，包含 min_val 和 max_val 参数。
    - 从 Saltf 文件生成点云数据，筛选符合范围的点。
    - 将筛选后的点云数据转换为 PLY 格式，返回给前端。
    返回：
    - 成功：包含点云数据的 PLY 文件（pointcloud.ply）。
    - 失败：HTTP 状态码和错误信息。
    """
    # 获取前端发送的 JSON 数据
    data = request.get_json()
    min_val = data.get('min_val')  # 获取最小值参数
    max_val = data.get('max_val')  # 获取最大值参数

    # 调试：打印输入参数
    print('max_val=', max_val)
    print('min_val=', min_val)

    # 验证参数有效性
    if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
        # 如果 min_val 或 max_val 不是数值类型，返回 400 错误
        return Response('无效的 min_val 或 max_val 参数，必须为数值', status=400)
    if min_val >= max_val:
        # 如果 min_val 大于或等于 max_val，返回 400 错误
        return Response('min_val 必须小于 max_val', status=400)

    # 配置参数
    input_file = "Saltf"  # 输入文件路径（Saltf 文件）
    n1, n2, n3 = 210, 676, 676  # 点云数据的维度（X, Y, Z 方向的点数）
    spacing = (20.0, 20.0, 20.0)  # 点云网格的间距（X, Y, Z 方向）
    origin = (0.0, 0.0, 0.0)  # 点云网格的原点坐标

    # 读取 Saltf 文件
    try:
        # 从文件读取大端浮点数（>f4）数据
        data = np.fromfile(input_file, dtype=">f4")
        expected_size = n1 * n2 * n3  # 计算预期的数据点总数
        if len(data) != expected_size:
            # 如果文件大小不符合预期，返回 500 错误
            return Response(f"预期数据点数 {expected_size}，实际得到 {len(data)}", status=500)
        # 重塑数据为 3D 数组，并转换为小端浮点数格式
        data = data.reshape((n3, n2, n1))
        data = data.byteswap().view(np.float32)
    except Exception as e:
        # 捕获文件读取错误，返回 500 错误并包含错误信息
        return Response(f"读取文件失败: {str(e)}", status=500)

    # 生成坐标网格
    # 使用 np.linspace 生成 X, Y, Z 方向的等间距坐标
    x = np.linspace(origin[0], origin[0] + spacing[0] * (n1 - 1), n1)
    y = np.linspace(origin[1], origin[1] + spacing[1] * (n2 - 1), n2)
    z = np.linspace(origin[2], origin[2] + spacing[2] * (n3 - 1), n3)
    # 生成 3D 网格坐标，indexing='ij' 确保轴顺序正确
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # 展平网格坐标和数据为 1D 数组，便于筛选
    X_flat = X.flatten()
    Y_flat = Y.flatten()
    Z_flat = Z.flatten()
    values_flat = data.flatten()

    # 筛选点云数据
    # 根据 min_val 和 max_val 创建布尔掩码，筛选符合范围的点
    mask = (values_flat >= min_val) & (values_flat <= max_val)
    x_vals = X_flat[mask]  # 筛选后的 X 坐标
    y_vals = Y_flat[mask]  # 筛选后的 Y 坐标
    z_vals = Z_flat[mask]  # 筛选后的 Z 坐标
    values_vals = values_flat[mask]  # 筛选后的强度值

    # 创建 PLY 数据
    # 定义结构化数组，包含 x, y, z 和 scalar 四个浮点数属性
    vertices = np.zeros(
        len(x_vals),
        dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'), ('scalar', 'f4')]
    )
    vertices['x'] = x_vals  # 填充 X 坐标
    vertices['y'] = y_vals  # 填充 Y 坐标
    vertices['z'] = z_vals  # 填充 Z 坐标
    vertices['scalar'] = values_vals  # 填充强度值

    # 创建 PLY 元素，描述顶点数据
    element = PlyElement.describe(vertices, 'vertex')
    # 创建 PLY 数据对象，使用二进制小端格式
    ply_data = PlyData([element], text=False, byte_order='<')

    # 调试：打印 PLY 数据中的元素数
    print(ply_data.__len__())

    # 将 PLY 数据写入内存流
    output = BytesIO()  # 创建内存缓冲区
    ply_data.write(output)  # 写入 PLY 数据
    output.seek(0)  # 将指针重置到缓冲区开头

    # 调试：打印筛选后的点数
    print(f"筛选后的点数，范围 [{min_val}, {max_val}]: {len(x_vals)}")

    # 调试：打印前 20 个点的坐标和强度值
    print("前 20 个点的坐标和强度值 (x, y, z, intensity):")
    for i in range(min(20, len(x_vals))):
        print(f"点 {i}: x={x_vals[i]:.2f}, y={y_vals[i]:.2f}, z={z_vals[i]:.2f}, intensity={values_vals[i]:.2f}")

    # 如果没有筛选到点，返回 400 错误
    if len(x_vals) == 0:
        print("在指定范围内未找到点。")
        return Response(f"在范围 [{min_val}, {max_val}] 内未找到点", status=400)

    # 返回 PLY 文件
    return send_file(
        output,  # 内存中的 PLY 文件流
        mimetype='application/octet-stream',  # 二进制文件类型
        as_attachment=True,  # 作为附件下载
        download_name='pointcloud.ply'  # 下载文件名
    )

if __name__ == '__main__':
    """
    主程序入口，启动 Flask 服务。
    - 监听地址：0.0.0.0（所有网络接口）
    - 端口：5000
    - 调试模式：开启（debug=True），便于开发时查看错误信息
    """
    app.run(host='0.0.0.0', port=5000, debug=True)