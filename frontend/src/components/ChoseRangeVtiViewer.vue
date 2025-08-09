<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云体渲染应用，用于从后端获取二进制 VTI 格式的点云数据，过滤标量值为 0 的点后以体视形式渲染。
  用户通过控制面板输入最小值和最大值，触发点云数据生成并在 3D 渲染窗口中显示。支持根据标量值应用蓝-绿-红渐变的颜色映射，并优化了错误处理和性能日志。

  主要功能：
  1. 初始化 VTK.js 体渲染器，设置渲染窗口和深灰色背景。
  2. 用户通过控制面板输入最小值和最大值，点击“生成并渲染”按钮。
  3. 向后端发送请求获取 gzip 压缩的 VTI 文件，显示加载进度。
  4. 使用 pako 解压 VTI 数据，验证解压后数据长度，解析为 vtkImageData。
  5. 过滤标量值为 0 的点，创建新的 vtkImageData 对象，更新点数统计。
  6. 使用体渲染（vtkVolume 和 vtkVolumeMapper）显示过滤后的点云。
  7. 根据标量值应用颜色映射和不透明度映射（蓝-绿-红渐变）。
  8. 在组件卸载时清理 VTK 资源以防止内存泄漏。

  代码结构：
  - **模板部分**：包含渲染窗口、控制面板（输入框、按钮、加载进度、错误信息、文件信息）。
  - **脚本部分**：使用 Vue 3 的组合式 API（<script setup>），初始化 VTK.js 体渲染器，处理用户输入，异步获取、解压、解析并渲染 VTI 文件。
  - **样式部分**：定义 flex 布局、渲染窗口、控制面板的样式，确保界面美观且功能清晰。

  注意事项：
  - 后端 API 假设运行在 http://localhost:5000/generate-vti，需确保后端服务正常运行并返回 gzip 压缩的 VTI 文件。
  - 标量值为 0 的点被过滤，可能导致点云稀疏，需验证过滤逻辑是否符合预期。
  - 体渲染对硬件性能要求较高，需确保运行环境的 WebGL 支持。
-->

<template>
  <div class="container">
    <!-- VTK 渲染窗口，用于显示 3D 体视点云 -->
    <div ref="renderContainer" class="render-window"></div>
    <!-- 控制面板：用于调节最小值、最大值并触发点云生成 -->
    <div class="control">
      <h3>点云控制面板</h3>
      <!-- 输入最小值的输入框 -->
      <div class="input-group">
        <label>最小值: </label>
        <input v-model.number="minValue" type="number" placeholder="例如：1500" />
      </div>
      <!-- 输入最大值的输入框 -->
      <div class="input-group">
        <label>最大值: </label>
        <input v-model.number="maxValue" type="number" placeholder="例如：4500" />
      </div>
      <!-- 触发点云生成和渲染的按钮，加载时禁用 -->
      <button :disabled="loading" @click="fetchAndRender">生成并渲染</button>
      <!-- 显示加载进度 -->
      <p v-if="loading">加载中... ({{ progress }}%)</p>
      <!-- 显示错误信息 -->
      <p v-if="error" class="error">{{ error }}</p>
      <!-- 显示文件大小和点云点数 -->
      <p v-if="fileInfo">文件大小: {{ fileInfo.size }} MB, 点数: {{ fileInfo.points }}</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';
import pako from 'pako'; // 用于解压 gzip 压缩的 VTI 文件
import '@kitware/vtk.js/Rendering/Profiles/Volume'; // 加载 VTK.js 的体渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 解析 VTI 文件
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'; // 体渲染对象
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'; // 体渲染映射器
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'; // 不透明度映射
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData'; // 体视数据模型
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'; // 数据数组，用于存储标量值

// 定义响应式变量
const minValue = ref(1500); // 最小值输入，默认为 1500，用于过滤点云数据
const maxValue = ref(4500); // 最大值输入，默认为 4500，用于过滤点云数据
const loading = ref(false); // 加载状态，控制按钮禁用和进度显示
const progress = ref(0); // 加载进度，显示下载百分比
const error = ref(''); // 错误信息，用于显示请求、解压或渲染错误
const fileInfo = ref(null); // 文件信息，存储 VTI 文件大小和有效点数
const renderContainer = ref(null); // 渲染容器 DOM 引用，用于 VTK.js 渲染窗口

// 定义 VTK 渲染相关变量
let fullScreenRenderer, renderer, renderWindow; // 全局保存渲染器、渲染窗口等对象，便于操作和清理

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  // 初始化 VTK 全屏渲染窗口，绑定到 renderContainer DOM 元素，设置深灰色背景
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value, // 指定渲染容器
    background: [0.1, 0.1, 0.1], // 设置深灰色背景，便于体视点云显示
  });
  renderer = fullScreenRenderer.getRenderer(); // 获取渲染器，用于管理体渲染对象
  renderWindow = fullScreenRenderer.getRenderWindow(); // 获取渲染窗口，控制渲染行为
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 清理 VTK 渲染器资源，防止内存泄漏
  if (fullScreenRenderer) {
    fullScreenRenderer.delete(); // 释放渲染器及相关资源
  }
});

// 获取并渲染 VTI 文件的异步函数
async function fetchAndRender() {
  // 函数功能：根据用户输入的最小值和最大值，向后端请求 gzip 压缩的 VTI 文件，解压、解析、过滤并以体视形式渲染
  // 参数：无（使用响应式变量 minValue 和 maxValue）
  // 返回值：无（通过修改响应式变量和渲染窗口更新界面）

  // 验证输入值是否有效
  if (!minValue.value || !maxValue.value || minValue.value >= maxValue.value) {
    error.value = '请输入有效的范围（最小值 < 最大值）';
    return;
  }

  // 设置加载状态，禁用按钮并显示进度
  loading.value = true;
  progress.value = 0;
  error.value = ''; // 清空错误信息
  fileInfo.value = null; // 清空文件信息
  renderer.removeAllActors(); // 移除渲染器中的所有体渲染对象，清除之前的点云

  try {
    // 向后端发送 POST 请求，获取 gzip 压缩的 VTI 文件
    const response = await axios.post(
      'http://localhost:5000/generate-vti', // 后端 API 端点，需确保服务运行
      { min_val: minValue.value, max_val: maxValue.value }, // 请求参数
      {
        responseType: 'arraybuffer', // 以二进制数组接收 VTI 文件
        onDownloadProgress: (progressEvent) => {
          // 实时更新下载进度
          if (progressEvent.total) {
            progress.value = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          }
        },
      }
    );

    // 获取 VTI 文件数据并计算文件大小（单位：MB）
    const arrayBuffer = response.data;
    const fileSizeMB = (arrayBuffer.byteLength / (1024 * 1024)).toFixed(2);

    // 解压 gzip 压缩的 VTI 数据
    let vtiData;
    try {
      const decompressStart = performance.now(); // 记录解压开始时间
      vtiData = pako.ungzip(new Uint8Array(arrayBuffer)); // 解压为 Uint8Array
      console.debug('解压后的 VTI 数据长度（字节）：', vtiData.length);
      console.debug('解压耗时：', (performance.now() - decompressStart) / 1000, '秒');
      // 验证解压后的数据是否有效
      if (vtiData.length === 0) {
        throw new Error('解压后的 VTI 数据为空');
      }
      if (vtiData.length % 4 !== 0) {
        throw new Error(`解压后的 VTI 数据长度 ${vtiData.length} 不是 4 的倍数`);
      }
    } catch (err) {
      throw new Error(`解压 gzip 数据失败: ${err.message}`);
    }

    // 解析 VTI 数据
    const reader = vtkXMLImageDataReader.newInstance();
    try {
      const parseStart = performance.now(); // 记录解析开始时间
      reader.parseAsArrayBuffer(vtiData.buffer); // 解析解压后的二进制 VTI 数据
      console.debug('解析耗时：', (performance.now() - parseStart) / 1000, '秒');
    } catch (err) {
      throw new Error(`解析 VTI 文件失败: ${err.message}`);
    }
    const imageData = reader.getOutputData(); // 获取解析后的体视数据（vtkImageData）

    // 过滤标量值为 0 的点
    const filterStart = performance.now(); // 记录过滤开始时间
    const scalars = imageData.getPointData().getArrayByName('ScalarValue'); // 获取标量数组
    if (!scalars) {
      throw new Error('未找到标量数据数组');
    }
    const scalarArray = scalars.getData(); // 获取标量值数组
    const dims = imageData.getDimensions(); // 获取体数据的维度
    const spacing = imageData.getSpacing(); // 获取体数据的间距
    const origin = imageData.getOrigin(); // 获取体数据的原点

    // 创建新的标量数组，仅保留非零值
    const filteredScalars = new Float32Array(scalarArray.length);
    let validPointCount = 0;
    for (let i = 0; i < scalarArray.length; i++) {
      if (scalarArray[i] !== 0) {
        filteredScalars[i] = scalarArray[i]; // 保留非零标量值
        validPointCount++; // 统计有效点数
      }
    }

    // 创建新的 vtkImageData 对象，存储过滤后的数据
    const filteredImageData = vtkImageData.newInstance();
    filteredImageData.setDimensions(dims); // 设置维度
    filteredImageData.setSpacing(spacing); // 设置间距
    filteredImageData.setOrigin(origin); // 设置原点

    // 创建新的标量数组并绑定到过滤后的数据
    const newScalars = vtkDataArray.newInstance({
      name: 'ScalarValue',
      values: filteredScalars,
      numberOfComponents: 1, // 单分量标量
    });
    filteredImageData.getPointData().setScalars(newScalars); // 设置标量数据

    console.debug('过滤耗时：', (performance.now() - filterStart) / 1000, '秒');
    console.debug('有效点数：', validPointCount);

    // 保存文件信息，显示在界面上
    fileInfo.value = { size: fileSizeMB, points: validPointCount };

    // 创建体渲染 Mapper 和 Volume
    const mapper = vtkVolumeMapper.newInstance();
    mapper.setInputData(filteredImageData); // 设置输入数据为过滤后的体数据

    const volume = vtkVolume.newInstance();
    volume.setMapper(mapper); // 绑定 Mapper 到 Volume

    // 如果存在有效点，应用颜色映射和不透明度映射
    if (validPointCount > 0) {
      const scalarRange = newScalars.getRange(); // 获取标量范围
      // 创建颜色映射（蓝-绿-红渐变）
      const ctf = vtkColorTransferFunction.newInstance();
      ctf.addRGBPoint(scalarRange[0], 0, 0, 1); // 最小值映射为蓝色
      ctf.addRGBPoint((scalarRange[0] + scalarRange[1]) / 2, 0, 1, 0); // 中间值映射为绿色
      ctf.addRGBPoint(scalarRange[1], 1, 0, 0); // 最大值映射为红色

      // 创建不透明度映射
      const ofun = vtkPiecewiseFunction.newInstance();
      ofun.addPoint(scalarRange[0], 0.0); // 最小值完全透明
      ofun.addPoint((scalarRange[0] + scalarRange[1]) / 2, 0.5); // 中间值半透明
      ofun.addPoint(scalarRange[1], 1.0); // 最大值完全不透明

      // 应用颜色和不透明度映射
      volume.getProperty().setRGBTransferFunction(0, ctf);
      volume.getProperty().setScalarOpacity(0, ofun);
      volume.getProperty().setScalarOpacityUnitDistance(0, 1.0); // 设置不透明度单位距离
      volume.getProperty().setInterpolationTypeToLinear(); // 使用线性插值
    } else {
      // 如果没有有效点，使用默认灰色
      volume.getProperty().setRGBTransferFunction(0, vtkColorTransferFunction.newInstance());
      volume.getProperty().setScalarOpacity(0, vtkPiecewiseFunction.newInstance());
      volume.getProperty().setColor(0.5, 0.5, 0.5); // 设置默认灰色
    }

    // 将 Volume 添加到渲染器
    renderer.addVolume(volume);
    // 重置相机以适应体视数据
    renderer.resetCamera();
    // 触发渲染
    renderWindow.render();
  } catch (err) {
    // 处理请求、解压、解析或渲染过程中的错误
    error.value = `加载或渲染失败: ${err.message}`;
    console.error('加载或渲染 VTI 文件出错:', err);
  } finally {
    // 无论成功或失败，结束加载状态
    loading.value = false;
    progress.value = 0;
  }
}
</script>

<style scoped>
/* 容器样式，设置 flex 水平布局，占满视口高度 */
.container {
  display: flex;
  flex-direction: row;
  height: 100vh;
  position: relative;
}

/* 渲染窗口样式，占满剩余空间，深灰色背景以突出体视点云 */
.render-window {
  flex: 1;
  background: #1a1a1a;
  position: relative;
  z-index: 1; /* 确保渲染窗口在控制面板下方 */
}

/* 控制面板样式，固定宽度，浅灰色背景，支持垂直滚动 */
.control {
  width: 250px;
  padding: 1rem;
  background-color: #f4f4f4;
  font-family: Arial, sans-serif;
  overflow-y: auto; /* 允许垂直滚动以适应长内容 */
  z-index: 2; /* 确保控制面板在渲染窗口上方 */
  position: relative;
}

/* 控制面板标题样式，设置底部外边距和字体大小 */
.control h3 {
  margin-bottom: 1rem;
  font-size: 1.2rem;
}

/* 输入组样式，设置 flex 布局和垂直外边距 */
.input-group {
  margin: 0.5rem 0;
  display: flex;
  align-items: center; /* 垂直居中对齐 */
}

/* 输入组标签样式，固定宽度 */
.input-group label {
  width: 100px;
  font-size: 0.9rem;
}

/* 输入框样式，设置内边距、宽度、边框和圆角 */
input {
  padding: 0.4rem;
  width: 120px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

/* 按钮样式，蓝色背景，白色文字，圆角边框 */
button {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 0.5rem;
}

/* 禁用按钮样式，灰色背景，禁用鼠标指针 */
button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

/* 错误信息样式，红色文字以突出显示 */
.error {
  color: #dc3545;
  margin: 0.5rem 0;
  font-size: 0.9rem;
}
</style>