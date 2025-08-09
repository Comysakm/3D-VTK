<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的三维可视化应用，用于渲染一个由多个立方体组成的规则网格。每个立方体的位置按规则网格排列，大小随机生成，并根据大小应用蓝-绿-红渐变的颜色映射，展示动态的三维可视化效果。使用 VTK.js 的 Glyph3DMapper 实现立方体的绘制，结合缩放和颜色映射功能。

  主要功能：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和深灰色背景。
  2. 生成规则网格点（22x22x22，约10648个点），每个点对应一个立方体，位置按固定间距排列。
  3. 为每个立方体分配随机大小（0.3到5.3），存储在点数据中。
  4. 根据立方体大小应用蓝-绿-红颜色映射，增强可视化效果。
  5. 使用 vtkGlyph3DMapper 将点云渲染为立方体，立方体大小由点数据中的标量值控制。
  6. 将渲染对象添加到场景，自动调整相机并触发渲染。
  7. 在组件卸载时清理 VTK 资源以防止内存泄漏。

  代码结构：
  - **模板部分**：包含一个全屏渲染容器，用于承载 VTK.js 的渲染窗口。
  - **脚本部分**：使用 Vue 3 的组合式 API（<script setup>），初始化 VTK.js 渲染管道，生成网格点、立方体、颜色映射，并完成场景渲染。
  - **样式部分**：定义全屏布局样式，确保渲染窗口占满整个页面。

  注意事项：
  - 本代码为静态点云渲染，未涉及后端数据获取，点云数据在前端生成。如果需要动态数据，可扩展为从后端获取 VTP 文件。
  - 网格点数量（22^3）较大，渲染性能可能受硬件限制，建议根据设备性能调整 cubeCountPerAxis。
  - 颜色映射范围（0.3到5.3）与立方体大小一致，需确保范围与数据匹配，避免颜色失真。
-->

<template>
  <div class="container">
    <!-- VTK 渲染窗口，用于以立方体形式显示 3D 点云 -->
    <div ref="renderContainer" class="render-window"></div>
    <!-- 控制面板：用于调节最小值、最大值、立方体大小并触发点云生成 -->
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
      <!-- 输入立方体大小的输入框，步长为 0.1，限制范围 0.1-10 -->
      <div class="input-group">
        <label>立方体大小: </label>
        <input v-model.number="cubeSize" type="number" step="0.1" min="0.1" max="10" />
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
import pako from 'pako'; // 用于解压 gzip 压缩的 VTP 文件

// VTK.js 渲染模块
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载几何渲染模块
import '@kitware/vtk.js/Rendering/Profiles/Glyph'; // 加载 Glyph 渲染模块，支持立方体渲染
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkXMLPolyDataReader from '@kitware/vtk.js/IO/XML/XMLPolyDataReader'; // 解析 VTP 文件
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // 渲染对象
import vtkGlyph3DMapper from '@kitware/vtk.js/Rendering/Core/Glyph3DMapper'; // Glyph 映射器，用于立方体渲染
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射
import vtkCubeSource from '@kitware/vtk.js/Filters/Sources/CubeSource'; // 立方体源

// 定义响应式变量
const minValue = ref(1500); // 最小值输入，默认为 1500，用于过滤点云数据
const maxValue = ref(4500); // 最大值输入，默认为 4500，用于过滤点云数据
const cubeSize = ref(10); // 立方体大小，默认为 10，用于 Glyph 渲染
const loading = ref(false); // 加载状态，控制按钮禁用和进度显示
const progress = ref(0); // 加载进度，显示下载百分比
const error = ref(''); // 错误信息，用于显示请求或渲染错误
const fileInfo = ref(null); // 文件信息，存储 VTP 文件大小和点云点数
const renderLog = ref([]); // 渲染日志，记录各阶段耗时
const renderContainer = ref(null); // 渲染容器 DOM 引用，用于 VTK.js 渲染窗口

// 定义 VTK 渲染相关变量
let fullScreenRenderer, renderer, renderWindow; // 全局保存渲染器、渲染窗口等对象

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  // 初始化 VTK 全屏渲染窗口，绑定到 renderContainer DOM 元素，设置深灰色背景
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value, // 指定渲染容器
    background: [0.1, 0.1, 0.1], // 设置深灰色背景，便于立方体点云显示
  });
  renderer = fullScreenRenderer.getRenderer(); // 获取渲染器，用于管理渲染对象
  renderWindow = fullScreenRenderer.getRenderWindow(); // 获取渲染窗口，控制渲染行为
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 清理 VTK 渲染器资源，防止内存泄漏
  if (fullScreenRenderer) {
    fullScreenRenderer.delete(); // 释放渲染器及相关资源
  }
});

/**
 * 从后端请求 VTP.gz 数据 → 解压 → 解析 → 以立方体形式渲染
 * 功能：根据用户输入的最小值、最大值和立方体大小，请求 VTP 文件，解压、解析并以立方体形式渲染，记录日志并发送到后端
 * 参数：无（使用响应式变量 minValue、maxValue 和 cubeSize）
 * 返回值：无（通过修改响应式变量和渲染窗口更新界面）
 */
async function fetchAndRender() {
  // 验证输入值是否有效
  if (!minValue.value || !maxValue.value || minValue.value >= maxValue.value) {
    error.value = '请输入有效的范围（最小值 < 最大值）';
    return;
  }

  // 初始化状态
  loading.value = true; // 设置加载状态
  progress.value = 0; // 重置加载进度
  error.value = ''; // 清空错误信息
  fileInfo.value = null; // 清空文件信息
  renderer.removeAllActors(); // 移除渲染器中的所有 Actor
  renderLog.value = []; // 清空渲染日志

  try {
    const totalStart = performance.now(); // 记录总耗时开始

    // === 1. 请求数据 ===
    const reqStart = performance.now(); // 记录请求开始时间
    const response = await axios.post(
      'http://localhost:5000/generate-vtp', // 后端 API 端点，需确保服务运行
      { min_val: minValue.value, max_val: maxValue.value }, // 请求参数
      {
        responseType: 'arraybuffer', // 以二进制数组接收 VTP 文件
        onDownloadProgress: (evt) => {
          // 实时更新下载进度
          if (evt.total) {
            progress.value = Math.round((evt.loaded / evt.total) * 100);
          }
        },
      }
    );
    renderLog.value.push(`请求耗时: ${(performance.now() - reqStart).toFixed(3)} ms`);

    // === 2. 解压数据 ===
    const unzipStart = performance.now(); // 记录解压开始时间
    const vtpData = pako.ungzip(new Uint8Array(response.data)); // 解压 gzip 压缩的 VTP 数据
    renderLog.value.push(`解压耗时: ${(performance.now() - unzipStart).toFixed(3)} ms`);
    // 验证解压后的数据是否有效
    if (vtpData.length === 0) throw new Error('解压后的 VTP 数据为空');

    // === 3. 解析 VTP ===
    const parseStart = performance.now(); // 记录解析开始时间
    const reader = vtkXMLPolyDataReader.newInstance();
    reader.parseAsArrayBuffer(vtpData.buffer); // 解析解压后的二进制 VTP 数据
    const polyData = reader.getOutputData(); // 获取解析后的点云数据（vtkPolyData）
    renderLog.value.push(`解析耗时: ${(performance.now() - parseStart).toFixed(3)} ms`);

    // 获取点云点数并保存文件信息
    const numPoints = polyData.getPoints()?.getNumberOfPoints() || 0;
    fileInfo.value = {
      size: (response.data.byteLength / (1024 * 1024)).toFixed(2), // 文件大小（MB）
      points: numPoints // 点云点数
    };

    // === 4. 创建立方体 Glyph ===
    const cubeSource = vtkCubeSource.newInstance({
      xLength: cubeSize.value, // 立方体 x 轴边长
      yLength: cubeSize.value, // 立方体 y 轴边长
      zLength: cubeSize.value  // 立方体 z 轴边长
    });

    // 配置 Glyph 映射器
    const mapper = vtkGlyph3DMapper.newInstance();
    mapper.setInputData(polyData); // 设置输入数据为点云
    mapper.setSourceConnection(cubeSource.getOutputPort()); // 设置立方体作为 Glyph 源
    mapper.setScaleModeToScaleByConstant(); // 使用固定缩放模式
    mapper.setScaleFactor(cubeSize.value); // 设置缩放因子为立方体大小

    // === 5. 标量颜色映射 ===
    const scalars = polyData.getPointData().getArrayByName('ScalarValue'); // 获取标量数组
    if (scalars) {
      mapper.setScalarVisibility(true); // 启用标量可视化
      mapper.setScalarModeToUsePointData(); // 使用点数据的标量值
      mapper.setColorModeToMapScalars(); // 映射标量到颜色
      const lut = vtkColorTransferFunction.newInstance(); // 创建颜色查找表
      const scalarRange = scalars.getRange(); // 获取标量范围
      // 定义蓝-绿-红渐变颜色映射
      lut.addRGBPoint(scalarRange[0], 0, 0, 1); // 最小值映射为蓝色
      lut.addRGBPoint((scalarRange[0] + scalarRange[1]) / 2, 0, 1, 0); // 中间值映射为绿色
      lut.addRGBPoint(scalarRange[1], 1, 0, 0); // 最大值映射为红色
      mapper.setLookupTable(lut); // 设置颜色查找表
      mapper.setScalarRange(scalarRange[0], scalarRange[1]); // 设置标量范围
    } else {
      mapper.setScalarVisibility(false); // 无标量数据时禁用颜色映射
      console.warn('未找到标量数据，使用默认颜色'); // 警告缺失标量数据
    }

    // 创建并配置 Actor
    const actor = vtkActor.newInstance();
    actor.setMapper(mapper); // 绑定 Glyph Mapper
    renderer.addActor(actor); // 将 Actor 添加到渲染器

    // === 6. 渲染 ===
    const renderStart = performance.now(); // 记录渲染开始时间
    renderer.resetCamera(); // 重置相机以适应点云
    renderWindow.render(); // 触发渲染
    renderLog.value.push(`渲染耗时: ${(performance.now() - renderStart).toFixed(3)} ms`);

    // === 7. 总耗时 ===
    renderLog.value.push(`总耗时: ${(performance.now() - totalStart).toFixed(3)} ms`);

    // === 8. 自动保存日志到后端 ===
    try {
      await axios.post('http://localhost:5000/save-log', {
        logs: renderLog.value, // 渲染日志
        min_val: minValue.value, // 最小值
        max_val: maxValue.value, // 最大值
        point_count: numPoints // 点云点数
      });
      console.log('渲染日志已发送到后端保存');
    } catch (logErr) {
      console.warn('渲染日志保存失败', logErr); // 记录日志保存失败的警告
    }

    console.table(renderLog.value); // 在控制台以表格形式显示日志
  } catch (err) {
    // 处理请求、解压、解析或渲染过程中的错误
    error.value = `加载或渲染失败: ${err.message}`;
    console.error('渲染错误:', err);
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

/* 渲染窗口样式，占满剩余空间，深灰色背景以突出立方体点云 */
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