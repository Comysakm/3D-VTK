# -*- coding: utf-8 -*-
"""
功能概述：
    基于 Flask 的 Web 服务，将本地 Saltf 三维体数据（大端 float32）按数值区间筛选为点云，
    生成包含：
        - 点坐标 Points（x, y, z）
        - 标量 ScalarValue（与体素值相同）
        - Verts（单点单元，便于 VTK 渲染为散点）
    的 vtkPolyData，并以 VTK XML PolyData（二进制 VTP）格式输出，再 gzip 压缩后通过 HTTP 返回。

特点与优化点：
    1) VTP 直接在内存中生成，不落盘，减少 IO。
    2) 使用 NumPy 一次性批量构造 Verts（[1, pointId] 重复数组），避免循环，提升性能。
    3) 全链路耗时统计：参数校验 / 数据筛选 / VTP 生成 / 压缩 / 总耗时。
    4) 文件大小统计：压缩前/压缩后大小与压缩率，便于观测体量。
    5) 启动阶段将体数据与坐标网格展平缓存到内存（X_FLAT/Y_FLAT/Z_FLAT/VALUES_FLAT），
       请求时仅做掩码筛选与拼装，响应更快。

依赖：
    - Flask, flask_cors
    - numpy
    - vtk (vtkPython)、vtkmodules.util.numpy_support
    - gzip
    - Python 3.x

输入/输出与数据流：
    启动时：
        Saltf(>f4) -> np.fromfile -> reshape(Z,Y,X) -> byteswap().view(float32)
        -> 生成 X/Y/Z 网格 -> flatten -> 缓存全局一维数组
    请求 /generate-vtp：
        JSON(min_val, max_val) -> 掩码筛选 (VALUES_FLAT)
        -> create_vtp_bytes_with_verts(...) 组装 vtkPolyData + 二进制写出 VTP
        -> gzip 压缩 -> HTTP 返回 application/gzip

注意事项：
    - dims / spacing / origin 要与真实数据一致，否则坐标与体素对应会错位。
    - VTK 的 CellArray 采用 [npts, id0, npts, id1, ...] 紧凑存储；此处 npts=1（Verts）。
    - 大数据集（210×676×676）非常大，内存与 CPU 压力较高；生产环境需考虑分块与缓存策略。
    - 若筛选后点数为 0，会直接 400 返回“范围内无数据”。

日志：
    - 启动日志写入 log/pointcloud_with_verts.log
    - 新增接口 /save-log 可保存前端渲染端的日志到 log/frontend_logs/
"""

from flask import Flask, request, Response
import datetime
from flask import jsonify
from flask_cors import CORS
import os
import time
import logging
import gzip
from io import BytesIO
import numpy as np
from vtk import vtkPolyData, vtkPoints, vtkXMLPolyDataWriter, vtkCellArray
from vtkmodules.util import numpy_support

# ----------------------------
# Flask 初始化与配置
# ----------------------------
app = Flask(__name__)
CORS(app)  # 允许跨域请求（不同来源前端可直接访问）

# 日志配置：输出到本地 log/ 目录，便于压测与问题定位
os.makedirs("log", exist_ok=True)
logging.basicConfig(
    filename="log/pointcloud_with_verts.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# ----------------------------
# 点云数据基础配置（需与实际数据匹配）
# ----------------------------
dims = (210, 676, 676)        # (X, Y, Z) 网格尺寸
spacing = (20.0, 20.0, 20.0)  # 每个方向物理间距（单位依数据而定，如 mm）
origin = (0.0, 0.0, 0.0)      # 坐标原点
input_file = "Saltf"          # 输入文件名（大端浮点数，>f4）

# ----------------------------
# 启动时加载点云数据到内存（一次性）
# ----------------------------
try:
    init_start = time.time()

    # 1) 读取大端浮点数；返回一维数组
    raw_data = np.fromfile(input_file, dtype=">f4")
    expected_size = np.prod(dims)
    if len(raw_data) != expected_size:
        # 维度不匹配通常表示 dims 配置或原始文件错误
        raise ValueError(f"预期数据量 {expected_size}，实际 {len(raw_data)}")

    # 2) 转小端 + reshape 为 (Z, Y, X)，与 vtk 常见坐标顺序保持一致
    raw_data = raw_data.reshape((dims[2], dims[1], dims[0])).byteswap().view(np.float32)

    # 3) 生成物理坐标网格（等间距）
    x = np.linspace(origin[0], origin[0] + spacing[0] * (dims[0] - 1), dims[0])
    y = np.linspace(origin[1], origin[1] + spacing[1] * (dims[1] - 1), dims[1])
    z = np.linspace(origin[2], origin[2] + spacing[2] * (dims[2] - 1), dims[2])
    # indexing="ij" 确保 (i->X, j->Y, k->Z) 的轴语义不被交换
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    # 4) 展平成一维数组，后续筛选直接用掩码（无需重复构造网格）
    X_FLAT = X.flatten()
    Y_FLAT = Y.flatten()
    Z_FLAT = Z.flatten()
    VALUES_FLAT = raw_data.flatten()

    logging.info(f"初始化完成，数据加载耗时 {time.time() - init_start:.3f} 秒")
except Exception as e:
    # 初始化失败立即抛出，避免服务在错误状态下对外提供接口
    logging.error(f"初始化失败: {e}", exc_info=True)
    raise

# ----------------------------
# 工具函数：生成带 Verts 的 VTP 二进制数据
# ----------------------------
def create_vtp_bytes_with_verts(x_vals, y_vals, z_vals, scalar_vals):
    """
    生成 VTP（二进制）字节串，包含：
      - Points：点坐标 (x, y, z)
      - PointData：标量 ScalarValue
      - Verts：单点单元（每个单元由一个点构成）

    参数：
        x_vals, y_vals, z_vals : 1D np.ndarray，点坐标（同长度）
        scalar_vals            : 1D np.ndarray，对应的标量值（同长度）

    返回：
        vtp_bytes : bytes，VTK XML PolyData（二进制）内容
    """

    # 1) 构造点坐标（N×3），并转为 VTK 数组
    # np.c_[...] 以零拷贝/视图方式拼列（视情况），deep=True 确保 VTK 拷贝数据到自身内存
    points = vtkPoints()
    points.SetData(numpy_support.numpy_to_vtk(np.c_[x_vals, y_vals, z_vals], deep=True))

    # 2) 标量（PointData 下的数组，命名为 ScalarValue，便于前端根据此名取用）
    scalars = numpy_support.numpy_to_vtk(scalar_vals, deep=True)
    scalars.SetName("ScalarValue")

    # 3) 批量创建 Verts（单点单元）
    # VTK CellArray 的紧凑存储格式为：
    #   [npts, id0, npts, id1, npts, id2, ...]
    # 其中 npts=1，id 为点索引。共 2*N 个整型。
    n_points = len(x_vals)
    verts_array = np.empty(n_points * 2, dtype=np.int64)
    verts_array[0::2] = 1  # 每个单元包含 1 个点
    verts_array[1::2] = np.arange(n_points, dtype=np.int64)

    vtk_verts_array = numpy_support.numpy_to_vtkIdTypeArray(verts_array, deep=True)
    verts = vtkCellArray()
    # SetCells(numCells, connectivity)
    verts.SetCells(n_points, vtk_verts_array)

    # 4) 组装 vtkPolyData
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().SetScalars(scalars)
    polydata.SetVerts(verts)

    # 5) 写出为 VTP（二进制）
    writer = vtkXMLPolyDataWriter()
    writer.SetInputData(polydata)
    writer.SetDataModeToBinary()        # 二进制写出，体积更小、解析更快
    writer.WriteToOutputStringOn()      # 写到内存字符串（不落盘）
    writer.Write()

    # 6) 提取为 bytes
    vtp_str = writer.GetOutputString()
    # 不同 VTK 版本返回类型可能不同：bytes/str，做兼容处理
    if isinstance(vtp_str, str):
        vtp_bytes = vtp_str.encode('utf-8', errors='ignore')
    else:
        vtp_bytes = bytes(vtp_str)

    return vtp_bytes

# ----------------------------
# 工具函数：gzip 压缩
# ----------------------------
def gzip_bytes(data_bytes):
    """对二进制数据进行 gzip 压缩并返回 bytes。"""
    buffer = BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as gz:
        gz.write(data_bytes)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------------------
# 接口：生成带 Verts 的 VTP.gz 文件
# ----------------------------
@app.route("/generate-vtp", methods=["POST"])
def generate_vtp():
    """按阈值筛选三维体数据，生成 vtkPolyData(VTP) 并 gzip 压缩后返回。"""
    req_start = time.time()

    # ===== A. 参数验证 =====
    t0 = time.time()
    data = request.get_json()
    min_val = data.get("min_val")
    max_val = data.get("max_val")
    if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
        return Response("参数错误：min_val 和 max_val 必须是数值", status=400)
    if min_val >= max_val:
        return Response("参数错误：min_val 必须小于 max_val", status=400)
    param_time = time.time() - t0

    # ===== B. 数据筛选（向量化掩码） =====
    t1 = time.time()
    mask = (VALUES_FLAT >= min_val) & (VALUES_FLAT <= max_val)
    x_vals, y_vals, z_vals, scalar_vals = (
        X_FLAT[mask],
        Y_FLAT[mask],
        Z_FLAT[mask],
        VALUES_FLAT[mask]
    )
    if len(x_vals) == 0:
        # 无数据直接返回；避免后续 VTK 构建开销
        return Response("范围内无数据", status=400)
    filter_time = time.time() - t1

    # ===== C. 生成 VTP（二进制） =====
    t2 = time.time()
    vtp_bytes = create_vtp_bytes_with_verts(x_vals, y_vals, z_vals, scalar_vals)
    vtp_time = time.time() - t2

    # ===== D. gzip 压缩 =====
    t3 = time.time()
    gz_data = gzip_bytes(vtp_bytes)
    compress_time = time.time() - t3

    # ===== E. 体量与耗时统计 =====
    original_size = len(vtp_bytes)
    compressed_size = len(gz_data)
    compression_ratio = 100 * (1 - compressed_size / original_size)
    total_time = time.time() - req_start

    # 记录详细流水信息，方便线上观测
    logging.info(
        f"请求完成: 范围=({min_val},{max_val}) "
        f"点数={len(x_vals)} "
        f"参数验证={param_time:.3f}s "
        f"筛选={filter_time:.3f}s "
        f"VTP生成={vtp_time:.3f}s "
        f"压缩={compress_time:.3f}s "
        f"原始大小={original_size/1024/1024:.2f}MB "
        f"压缩后={compressed_size/1024/1024:.2f}MB "
        f"压缩率={compression_ratio:.1f}% "
        f"总耗时={total_time:.3f}s"
    )

    # ===== F. 返回 gzip 压缩的 VTP 文件 =====
    return Response(
        gz_data,
        mimetype="application/gzip",
        headers={
            "Content-Disposition": "attachment; filename=pointcloud.vtp.gz"
        }
    )

# ===============================
# 新增接口：保存前端渲染日志到磁盘
# ===============================
@app.route("/save-log", methods=["POST"])
def save_log():
    """
    接收前端上报的渲染日志（数组），以时间戳命名写入 log/frontend_logs/。
    便于问题回溯与端到端性能排查。
    """
    try:
        data = request.get_json()
        logs = data.get("logs", [])
        if not isinstance(logs, list):
            return jsonify({"status": "error", "msg": "logs 必须是列表"}), 400

        # 生成文件名（按时间戳区分），目录不存在则创建
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"frontend_render_log_{now_str}.txt"
        log_dir = "log/frontend_logs"
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_filename)

        # 保存文件（追加也可，这里按单请求独立成文件）
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs))

        logging.info(f"前端日志已保存: {log_path}")
        return jsonify({"status": "ok", "path": log_path})
    except Exception as e:
        logging.error(f"保存前端日志失败: {e}", exc_info=True)
        return jsonify({"status": "error", "msg": str(e)}), 500

# ----------------------------
# 启动服务（开发模式）
# ----------------------------
if __name__ == "__main__":
    # 对外监听所有网卡，默认 5000 端口，debug=True 便于开发
    app.run(host="0.0.0.0", port=5000, debug=True)
