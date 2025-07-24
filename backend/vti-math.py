import vtk
from vtkmodules.util import numpy_support
import numpy as np
import matplotlib.pyplot as plt


def read_vti(file_path):
    # 读取VTI文件
    reader = vtk.vtkXMLImageDataReader()
    reader.SetFileName(file_path)
    reader.Update()

    # 获取图像数据
    image_data = reader.GetOutput()

    # 提取标量数据（数值数据）
    scalars = image_data.GetPointData().GetScalars()

    # 转换为numpy数组
    np_array = numpy_support.vtk_to_numpy(scalars)

    return np_array


def plot_distribution(np_array):
    # 绘制数据分布
    plt.figure(figsize=(8, 6))
    plt.hist(np_array, bins=100, color='blue', alpha=0.7)
    plt.title('Value Distribution in VTI File')
    plt.xlabel('Value')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.show()


# 读取vti文件并绘制分布
file_path = 'SaltfFF.vti'  # 替换为你的文件路径
np_array = read_vti(file_path)
plot_distribution(np_array)
