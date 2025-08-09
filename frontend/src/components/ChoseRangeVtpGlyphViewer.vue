<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于从后端获取 gzip 压缩的 VTP 格式点云数据，以立方体形式（Glyph 渲染）紧密相邻显示。
  用户通过控制面板输入最小值、最大值和立方体间距，触发点云生成并在 3D 渲染窗口中显示。支持根据标量值应用颜色映射，并记录渲染日志发送到后端保存。

  主要功能：
  1. 初始化 VTK.js 渲染器，设置渲染窗口和深灰色背景。
  2. 用户通过控制面板输入最小值、最大值和立方体间距，点击“生成并渲染”按钮。
  3. 向后端发送请求获取 gzip 压缩的 VTP 文件，解压并解析为 vtkPolyData。
  4. 使用 vtkGlyph3DMapper 以立方体形式渲染点云，立方体大小由用户指定的间距控制。
  5. 根据标量值应用浅蓝-青-浅绿-浅黄-浅红的颜色映射。
  6. 记录请求、解压、解析、渲染的耗时日志，并在界面显示，同时发送到后端保存。
  7. 在组件卸载时清理 VTK 资源以防止内存泄漏。

  代码结构：
  - **模板部分**：包含渲染窗口、控制面板（输入框、按钮、加载状态、错误信息、日志显示）。
  - **脚本部分**：使用 Vue 3 的组合式 API（<script setup>），初始化 VTK.js 渲染器，处理用户输入，异步获取、解压、解析并渲染 VTP 文件，管理日志。
  - **样式部分**：定义 flex 布局、渲染窗口、控制面板和日志卡片的样式，确保界面美观且功能清晰。

  注意事项：
  - 后端 API 假设运行在 http://localhost:5000/generate-vtp 和 http://localhost:5000/save-log，需确保后端服务正常运行。
  - 立方体间距（cubeSpacing）需与后端生成数据的间距一致，否则可能导致立方体重叠或间隙过大。
  - Glyph 渲染对点云数量敏感，大量点可能导致性能问题，需测试渲染性能。
-->

<template>
  <div class="container">
    <!-- VTK 渲染窗口，用于以立方体形式显示 3D 点云 -->
    <div ref="renderContainer" class="render-window"></div>

    <!-- 控制面板：用于调节最小值、最大值、立方体间距并触发点云生成 -->
    <div class="control">
      <h3>点云控制面板（立方体渲染）</h3>
      <!-- 输入最小值的输入框 -->
      <div class="input-group">
        <label>最小值:</label>
        <input v-model.number="minValue" type="number" />
      </div>
      <!-- 输入最大值的输入框 -->
      <div class="input-group">
        <label>最大值:</label>
        <input v-model.number="maxValue" type="number" />
      </div>
      <!-- 输入立方体间距的输入框，步长为 0.1 -->
      <div class="input-group">
        <label>间距:</label>
        <input v-model.number="cubeSpacing" type="number" step="0.1" />
      </div>
      <!-- 触发点云生成和渲染的按钮，加载时禁用 -->
      <button :disabled="loading" @click="fetchAndRender">生成并渲染</button>
      <!-- 显示加载状态 -->
      <p v-if="loading">加载中...</p>
      <!-- 显示错误信息 -->
      <p v-if="error" class="error">{{ error }}</p>
      <!-- 日志显示区域，展示性能耗时 -->
      <div v-if="renderLog.length" class="log-card">
        <div v-for="(line, index) in renderLog" :key="index" class="log-line">
          {{ line }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import pako from 'pako'; // 用于解压 gzip 压缩的 VTP 文件

// VTK.js 渲染模块
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载几何渲染模块
import '@kitware/vtk.js/Rendering/Profiles/Glyph'; // 加载 Glyph 渲染模块，支持立方体渲染
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkXMLPolyDataReader from '@kitware/vtk.js/IO/XML/XMLPolyDataReader'; // 解析 VTP 文件
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // 渲染对象
import vtkGlyph3DMapper from '@kitware/vtk.js/Rendering/Core/Glyph3DMapper'; // Glyph 映射器，用于立方体渲染
import vtkCubeSource from '@kitware/vtk.js/Filters/Sources/CubeSource'; // 立方体源
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射

// 定义响应式变量
const minValue = ref(1500); // 最小值输入，默认为 1500，用于过滤点云数据
const maxValue = ref(4500); // 最大值输入，默认为 4500，用于过滤点云数据
const cubeSpacing = ref(20.0); // 立方体边长（间距），默认为 20.0，与后端生成数据匹配
const loading = ref(false); // 加载状态，控制按钮禁用和加载提示
const error = ref(''); // 错误信息，用于显示请求或渲染错误
const renderLog = ref([]); // 渲染日志，记录各阶段耗时
const renderContainer = ref(null); // 渲染容器 DOM 引用，用于 VTK.js 渲染窗口

// 定义 VTK 渲染相关变量
let fullScreenRenderer, renderer, renderWindow; // 全局保存渲染器、渲染窗口等对象
let currentActors = []; // 存储当前渲染的 Actor，便于清理

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
  // 清理 VTK 资源并释放渲染器
  cleanupVTK(); // 清理当前渲染的 Actor
  if (fullScreenRenderer) {
    fullScreenRenderer.delete(); // 释放渲染器及相关资源
  }
});

/**
 * 清理上一次渲染的 VTK 对象
 * 功能：释放当前的 Actor，移除渲染器中的所有 Actor，并清空 Actor 列表
 */
function cleanupVTK() {
  currentActors.forEach((a) => a.delete && a.delete()); // 释放每个 Actor 的资源
  renderer.removeAllActors(); // 移除渲染器中的所有 Actor
  currentActors = []; // 清空 Actor 列表
}

/**
 * 从后端请求 VTP.gz 数据 → 解压 → 解析 → 用立方体紧密相邻渲染
 * 功能：根据用户输入的最小值、最大值和间距，请求 VTP 文件，解压、解析并以立方体形式渲染
 * 参数：无（使用响应式变量 minValue、maxValue 和 cubeSpacing）
 * 返回值：无（通过修改响应式变量和渲染窗口更新界面）
 */
async function fetchAndRender() {
  cleanupVTK(); // 清理上一次渲染的 VTK 对象
  renderLog.value = []; // 清空渲染日志
  loading.value = true; // 设置加载状态
  error.value = ''; // 清空错误信息

  try {
    const t0 = performance.now(); // 记录总耗时开始

    // === 1. 请求数据 ===
    const reqStart = performance.now(); // 记录请求开始时间
    const response = await axios.post(
      'http://localhost:5000/generate-vtp', // 后端 API 端点，需确保服务运行
      { min_val: minValue.value, max_val: maxValue.value }, // 请求参数
      { responseType: 'arraybuffer' } // 以二进制数组接收 VTP 文件
    );
    renderLog.value.push(`请求耗时: ${(performance.now() - reqStart).toFixed(3)} ms`);

    // === 2. 解压数据 ===
    const unzipStart = performance.now(); // 记录解压开始时间
    const vtpData = pako.ungzip(new Uint8Array(response.data)); // 解压 gzip 压缩的 VTP 数据
    renderLog.value.push(`解压耗时: ${(performance.now() - unzipStart).toFixed(3)} ms`);

    // === 3. 解析 VTP ===
    const parseStart = performance.now(); // 记录解析开始时间
    const reader = vtkXMLPolyDataReader.newInstance();
    reader.parseAsArrayBuffer(vtpData.buffer); // 解析解压后的二进制 VTP 数据
    const polyData = reader.getOutputData(); // 获取解析后的点云数据（vtkPolyData）
    renderLog.value.push(`解析耗时: ${(performance.now() - parseStart).toFixed(3)} ms`);
    console.log("点数量", polyData.getPoints().getNumberOfPoints()); // 输出点云点数，便于调试

    // === 4. 立方体源（大小 = spacing，紧密相邻） ===
    const cubeSource = vtkCubeSource.newInstance({
      xLength: cubeSpacing.value, // 立方体 x 轴边长
      yLength: cubeSpacing.value, // 立方体 y 轴边长
      zLength: cubeSpacing.value  // 立方体 z 轴边长
    });

    // === 5. Glyph 映射 ===
    const mapper = vtkGlyph3DMapper.newInstance();
    mapper.setInputData(polyData); // 设置输入数据为点云
    mapper.setSourceConnection(cubeSource.getOutputPort()); // 设置立方体作为 Glyph 源
    mapper.setScaleModeToScaleByConstant(); // 使用固定缩放模式
    mapper.setScaleFactor(1.0); // 固定缩放比例，确保立方体大小与后端间距一致

    // === 6. 标量颜色映射 ===
    const scalars = polyData.getPointData().getArrayByName('ScalarValue'); // 获取标量数组
    if (scalars) {
      const lut = vtkColorTransferFunction.newInstance(); // 创建颜色查找表
      const min = minValue.value; // 标量最小值
      const max = maxValue.value; // 标量最大值
      // 定义五点颜色映射，创建浅蓝-青-浅绿-浅黄-浅红渐变
      lut.addRGBPoint(min, 0.6, 0.8, 1.0); // 浅蓝
      lut.addRGBPoint(min + (max - min) * 0.25, 0.5, 1.0, 0.9); // 青色
      lut.addRGBPoint(min + (max - min) * 0.5, 0.6, 1.0, 0.6); // 浅绿
      lut.addRGBPoint(min + (max - min) * 0.75, 1.0, 1.0, 0.6); // 浅黄
      lut.addRGBPoint(max, 1.0, 0.6, 0.6); // 浅红
      mapper.setLookupTable(lut); // 设置颜色查找表
      mapper.setScalarRange(min, max); // 设置标量范围
    }

    // 创建并配置 Actor
    const actor = vtkActor.newInstance();
    actor.setMapper(mapper); // 绑定 Glyph Mapper
    renderer.addActor(actor); // 将 Actor 添加到渲染器
    currentActors.push(actor); // 保存 Actor 以便清理

    // === 7. 渲染 ===
    const renderStart = performance.now(); // 记录渲染开始时间
    renderer.resetCamera(); // 重置相机以适应点云
    renderWindow.render(); // 触发渲染
    renderLog.value.push(`渲染耗时: ${(performance.now() - renderStart).toFixed(3)} ms`);

    // === 8. 总耗时 ===
    renderLog.value.push(`总耗时: ${(performance.now() - t0).toFixed(3)} ms`);

    // === 9. 自动把日志发到后端保存 ===
    try {
      await axios.post('http://localhost:5000/save-log', {
        logs: renderLog.value, // 渲染日志
        min_val: minValue.value, // 最小值
        max_val: maxValue.value, // 最大值
        point_count: polyData.getPoints().getNumberOfPoints() // 点云点数
      });
      console.log("立方体渲染日志已发送到后端保存");
    } catch (e) {
      console.warn("立方体渲染日志发送失败", e); // 记录日志发送失败的警告
    }

    console.table(renderLog.value); // 在控制台以表格形式显示日志
  } catch (err) {
    // 处理请求、解压、解析或渲染过程中的错误
    error.value = `加载失败: ${err.message}`;
  } finally {
    // 无论成功或失败，结束加载状态
    loading.value = false;
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

/* 日志卡片样式，浅灰色背景，带边框和内边距 */
.log-card {
  background-color: #f9f9f9;
  border: 1px solid #ddd;
  padding: 0.5rem;
  margin-top: 1rem;
  border-radius: 4px;
}

/* 日志行样式，设置字体大小和行间距 */
.log-line {
  font-size: 0.85rem;
  line-height: 1.5;
}
</style>