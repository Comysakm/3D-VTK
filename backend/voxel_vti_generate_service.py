# -*- coding: utf-8 -*-
"""
功能概述：
    基于 Flask 的点云/体数据处理服务，按给定阈值区间(min_val, max_val)对三维体素数据进行筛选：
      - 将不在范围内的体素标量值置 0（保留拓扑与坐标不变）
      - 使用 VTK 生成 VTI（VTK ImageData 的 XML）二进制数据
      - 使用 gzip 压缩后通过 HTTP 直接返回（不落盘）

主要优化点：
    1) 使用 VTK 生成 VTI（体素结构，规则网格），包含点坐标与标量值（ScalarValue）。
    2) 日志明确 UTF-8 编码，便于中文日志收集。
    3) 记录各阶段耗时：参数校验 / Numba 加速筛选 / VTI 生成 / 压缩 / 总耗时。
    4) 使用 Numba(@jit, nopython=True) 加速阈值处理（将不在范围内的值置 0）。
    5) 使用线程池对写出与压缩过程进行封装（注意：当前实现立即 .result()，非完全异步，仅在线程中执行）。
    6) 启动时预加载并缓存原始数据（VALUES_FLAT），避免每次请求重复 IO 与重排。

输入/输出与数据流：
    启动阶段：
        Saltf(>f4) -> np.fromfile -> reshape(Z,Y,X) -> byteswap().view(float32) -> flatten -> VALUES_FLAT
    请求 /generate-vti：
        JSON(min_val, max_val) -> 参数校验
        -> Numba filter_values(VALUES_FLAT, min_val, max_val) 将越界值置 0
        -> 构建 vtkImageData(dims, spacing, origin) + 设置标量 ScalarValue
        -> vtkXMLImageDataWriter 二进制写出 -> gzip 压缩 -> send_file 返回 .vti.gz

注意事项与潜在风险：
    - dims/spacing/origin 必须与真实数据一致，否则坐标解读错误。
    - Saltf 为大端 float32（>f4），读入后需 byteswap 转为本机小端 float32。
    - 线程池当前通过 future.result() 阻塞等待结果，属于“异步封装”而非并发流水；若希望真正异步，应改为后台任务/队列。
    - VTK 写出字符串在不同版本中类型可能不同（bytes/str），本实现按 str->encode 处理；如返回本就是 bytes，需分支判断。
    - Numba @jit 首次调用存在编译开销；生产环境可通过预热一次调用降低首次请求延迟。
    - 该服务对大规模体数据（210×676×676）内存与 CPU 压力较大，建议结合分块/阈值预计算/缓存策略。
"""

from flask import Flask, request, Response, send_file
from io import BytesIO
import numpy as np
import vtk
from vtk import vtkXMLImageDataWriter, vtkImageData, vtkFloatArray
from vtkmodules.util import numpy_support
from flask_cors import CORS
import os
import time
import logging
import gzip
from concurrent.futures import ThreadPoolExecutor
from numba import jit

# =========================
# Flask 初始化与跨域设置
# =========================
app = Flask(__name__)
CORS(app)  # 允许跨域请求，便于前端（不同源）直接访问接口

# =========================
# 日志配置（UTF-8 编码）
# =========================
os.makedirs("log", exist_ok=True)
logging.basicConfig(
    filename="log/pointcloud_optimized.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)

# =========================
# 数据维度/几何设置（需与真实数据一致）
# =========================
dims = (210, 676, 676)           # 三维体素维度 (X, Y, Z)
spacing = (20.0, 20.0, 20.0)     # 各轴体素间距（单位依源数据，如 mm）
origin = (0.0, 0.0, 0.0)         # 原点坐标
input_file = "Saltf"             # 源数据文件名（大端 float32, >f4）

# =========================
# 全局缓存：展平后的标量数组
# =========================
VALUES_FLAT = None

@jit(nopython=True)
def filter_values(values_flat, min_val, max_val):
    """
    使用 Numba 加速的阈值过滤函数：将不在 [min_val, max_val] 范围内的值置 0。
    说明：
        - 采用拷贝后原地修改，避免污染全局缓存（values_flat）。
        - 返回与输入等长的一维数组，可直接写入 VTK 标量。

    Args:
        values_flat (np.ndarray): 展平的标量数组（float32）
        min_val (float): 最小阈值（含）
        max_val (float): 最大阈值（含）
    Returns:
        np.ndarray: 处理后的标量数组（不在范围的项被置 0）
    """
    result = np.copy(values_flat)
    for i in range(len(result)):
        if result[i] < min_val or result[i] > max_val:
            result[i] = 0.0
    return result

# =========================
# 启动时加载与缓存体数据
# =========================
try:
    init_start = time.time()
    # 1) 从大端 float32 文件读取一维数组
    raw_data = np.fromfile(input_file, dtype=">f4")
    expected_size = dims[0] * dims[1] * dims[2]
    if len(raw_data) != expected_size:
        # 尺寸不匹配：通常是 dims 配置或输入文件有误
        raise ValueError(f"预期数据量 {expected_size}，实际得到 {len(raw_data)}")

    # 2) 重塑为 (Z, Y, X) 并转为本机小端 float32
    raw_data = raw_data.reshape((dims[2], dims[1], dims[0])).byteswap().view(np.float32)

    # 3) 展平缓存，后续请求基于该数组生成不同阈值视图
    VALUES_FLAT = raw_data.flatten()

    init_time = time.time() - init_start
    logging.info(f"初始化完成，数据已缓存，耗时：{init_time:.3f}秒")
except Exception as e:
    logging.error(f"初始化失败：{str(e)}", exc_info=True)
    raise

# =========================
# 线程池：封装写出与压缩任务
# =========================
executor = ThreadPoolExecutor(max_workers=4)

@app.route('/generate-vti', methods=['POST'])
def generate_vti():
    """
    按阈值范围生成 .vti.gz（VTK ImageData + gzip）并返回下载。
    流程：
      A. 参数校验
      B. Numba 加速筛选（置 0）
      C. 构建 vtkImageData 并绑定标量
      D. 在线程中写出 VTI（二进制）并 gzip 压缩
      E. 统计耗时并返回

    请求体(JSON)：
        {
            "min_val": <float>,
            "max_val": <float>
        }
    """
    start_time = time.time()

    # ===== A. 参数校验 =====
    param_start = time.time()
    data = request.get_json()
    min_val = data.get("min_val")
    max_val = data.get("max_val")
    if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
        logging.error(f"无效参数：min_val={min_val}, max_val={max_val}")
        return Response("无效的 min_val 或 max_val 参数", status=400)
    if min_val >= max_val:
        logging.error(f"范围错误：min_val={min_val} >= max_val={max_val}")
        return Response("min_val 必须小于 max_val", status=400)
    param_time = time.time() - param_start

    try:
        # ===== B. Numba 加速筛选（越界置 0）=====
        filter_start = time.time()
        scalar_vals = filter_values(VALUES_FLAT, min_val, max_val)
        filter_time = time.time() - filter_start

        # ===== C. 构建 VTI（规则体素网格）=====
        vti_start = time.time()
        image_data = vtkImageData()
        image_data.SetDimensions(dims[0], dims[1], dims[2])      # X, Y, Z
        image_data.SetSpacing(spacing[0], spacing[1], spacing[2])
        image_data.SetOrigin(origin[0], origin[1], origin[2])

        # 将 numpy 数组转为 VTK 数组并绑定为点数据的标量
        # 注意：array_type 指定为 VTK_FLOAT，确保与 numpy float32 对齐
        vtk_array = numpy_support.numpy_to_vtk(
            num_array=scalar_vals,
            deep=True,
            array_type=vtk.VTK_FLOAT
        )
        vtk_array.SetName("ScalarValue")
        image_data.GetPointData().SetScalars(vtk_array)
        vti_time = time.time() - vti_start

        # ===== D. 在线程中写出 VTI（二进制）并 gzip 压缩 =====
        def write_compressed_vti():
            """
            线程函数：将 image_data 写为 VTI（二进制）并使用 gzip 压缩。
            兼容说明：
                - 某些 VTK 版本的 writer.GetOutputString() 可能返回 bytes，
                  当前实现默认按 str.encode('utf-8') 处理；若上线遇到类型不符，
                  可改为：
                      data = writer.GetOutputString()
                      if isinstance(data, str): data = data.encode('utf-8')
                      gz.write(data)
            """
            buffer = BytesIO()
            writer = vtkXMLImageDataWriter()
            writer.SetInputData(image_data)
            writer.SetDataModeToBinary()     # 二进制写出
            writer.WriteToOutputStringOn()   # 输出到内存字符串
            writer.Write()
            vti_data = writer.GetOutputString()
            # 采用较低压缩级别以缩短 CPU 时间（体积与耗时的折中）
            with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=1) as gz:
                gz.write(vti_data.encode('utf-8'))  # 见上方兼容说明
            buffer.seek(0)
            return buffer

        compress_start = time.time()
        # 说明：此处 .result() 会等待线程任务完成，属于“同步等待线程结果”
        # 若要真正异步，应返回任务ID并由客户端轮询或使用后台队列。
        future = executor.submit(write_compressed_vti)
        compressed_output = future.result()
        compress_time = time.time() - compress_start

        # ===== E. 统计日志并返回 =====
        total_time = time.time() - start_time
        logging.info(
            f"请求处理完成：范围=({min_val},{max_val}) 点数={len(scalar_vals)} "
            f"参数验证耗时={param_time:.3f}秒 筛选耗时={filter_time:.3f}秒 "
            f"VTI生成耗时={vti_time:.3f}秒 压缩耗时={compress_time:.3f}秒 "
            f"总耗时={total_time:.3f}秒"
        )

        return send_file(
            compressed_output,
            mimetype='application/gzip',
            as_attachment=True,
            download_name='pointcloud.vti.gz'
        )

    except Exception as e:
        # 捕获处理链路中的所有异常，写入堆栈便于定位
        logging.error(f"处理失败：min_val={min_val}, max_val={max_val}, 错误={str(e)}", exc_info=True)
        return Response(f"服务器错误：{str(e)}", status=500)


if __name__ == '__main__':
    # 开发模式启动；生产部署建议使用 WSGI/ASGI（gunicorn/uwsgi 等）并关闭 debug
    app.run(host="0.0.0.0", port=5000, debug=True)
