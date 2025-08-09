<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于从后端获取 gzip 压缩的 VTP 格式点云数据，直接以点云形式渲染。
  用户通过控制面板输入最小值、最大值和立方体大小（未实际使用，仅占位），触发点云生成并在 3D 渲染窗口中显示。
  支持根据标量值应用浅蓝-青-浅绿-浅黄-浅红的颜色映射，记录渲染日志并发送到后端保存。

  主要功能：
  1. 初始化 VTK.js 渲染器，设置渲染窗口和深灰色背景。
  2. 用户通过控制面板输入最小值、最大值和立方体大小，点击“生成并渲染”按钮。
  3. 向后端发送请求获取 gzip 压缩的 VTP 文件，解压并解析为 vtkPolyData。
  4. 使用 vtkMapper 直接渲染点云，应用标量颜色映射。
  5. 记录请求、解压、解析、渲染的耗时日志，显示在控制台并发送到后端保存。
  6. 在组件卸载时清理 VTK 资源以防止内存泄漏。

  代码结构：
  - **模板部分**：包含渲染窗口、控制面板（输入框、按钮、加载进度、错误信息、文件信息）。
  - **脚本部分**：使用 Vue 3 的组合式 API（<script setup>），初始化 VTK.js 渲染器，处理用户输入，异步获取、解压、解析并渲染 VTP 文件，管理日志。
  - **样式部分**：定义 flex 布局、渲染窗口和控制面板的样式，确保界面美观且功能清晰。

  注意事项：
  - 后端 API 假设运行在 http://localhost:5000/generate-vtp 和 http://localhost:5000/save-log，需确保后端服务正常运行。
  - 立方体大小（cubeSize）当前未在渲染中使用，仅作为占位参数，建议移除或实现 Glyph 渲染以利用该参数。
  - 日志显示在控制台但未在界面显示，建议与上一版本一致添加日志显示区域。
-->

<template>
  <div class="container">
    <!-- VTK 渲染窗口，用于显示 3D 点云 -->
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
      <!-- 输入立方体大小的输入框，步长为 0.1，限制范围 0.1-10（当前未使用） -->
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
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import pako from 'pako'; // 用于解压 gzip 压缩的 VTP 文件

// VTK.js 渲染模块
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载几何渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkXMLPolyDataReader from '@kitware/vtk.js/IO/XML/XMLPolyDataReader'; // 解析 VTP 文件
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // 渲染对象
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper'; // 点云映射器
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射

// 定义响应式变量
const minValue = ref(1500); // 最小值输入，默认为 1500，用于过滤点云数据
const maxValue = ref(4500); // 最大值输入，默认为 4500，用于过滤点云数据
const cubeSize = ref(1.0); // 立方体大小，当前未使用，占位参数
const loading = ref(false); // 加载状态，控制按钮禁用和进度显示
const progress = ref(0); // 加载进度，显示下载百分比
const error = ref(''); // 错误信息，用于显示请求或渲染错误
const fileInfo = ref(null); // 文件信息，存储 VTP 文件大小和点云点数
const renderLog = ref([]); // 渲染日志，记录各阶段耗时
const renderContainer = ref(null); // 渲染容器 DOM 引用，用于 VTK.js 渲染窗口

// 定义 VTK 渲染相关变量
let fullScreenRenderer, renderer, renderWindow; // 全局保存渲染器、渲染窗口等对象
let currentActors = []; // 保存当前渲染的 Actor，便于清理

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  // 初始化 VTK 全屏渲染窗口，绑定到 renderContainer DOM 元素，设置深灰色背景
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value, // 指定渲染容器
    background: [0.1, 0.1, 0.1], // 设置深灰色背景，便于点云显示
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
 * 从后端请求 VTP.gz 数据 → 解压 → 解析 → 直接渲染
 * 功能：根据用户输入的最小值和最大值，请求 VTP 文件，解压、解析并以点云形式渲染，记录日志并发送到后端
 * 参数：无（使用响应式变量 minValue 和 maxValue，cubeSize 未使用）
 * 返回值：无（通过修改响应式变量和渲染窗口更新界面）
 */
async function fetchAndRender() {
  cleanupVTK(); // 清理上一次渲染的 VTK 对象
  renderLog.value = []; // 清空渲染日志
  loading.value = true; // 设置加载状态
  error.value = ''; // 清空错误信息
  fileInfo.value = null; // 清空文件信息

  try {
    const t0 = performance.now(); // 记录总耗时开始

    // === 1. 发送请求 ===
    const reqStart = performance.now(); // 记录请求开始时间
    const response = await axios.post(
      'http://localhost:5000/generate-vtp', // 后端 API 端点，需确保服务运行
      { min_val: minValue.value, max_val: maxValue.value }, // 请求参数
      {
        responseType: 'arraybuffer', // 以二进制数组接收 VTP 文件
        onDownloadProgress: (progressEvent) => {
          // 实时更新下载进度
          if (progressEvent.total) {
            progress.value = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          }
        },
      }
    );
    renderLog.value.push(`请求耗时: ${(performance.now() - reqStart).toFixed(3)} ms`);

    // 计算文件大小（单位：MB）
    const fileSizeMB = (response.data.byteLength / (1024 * 1024)).toFixed(2);

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

    // 获取点云点数
    const pointCount = polyData.getPoints().getNumberOfPoints();

    // === 4. Mapper & 颜色映射 ===
    const mapper = vtkMapper.newInstance();
    mapper.setInputData(polyData); // 设置输入数据为点云
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
    } else {
      console.warn('未找到标量数据，使用默认颜色'); // 警告缺失标量数据
    }

    // 创建并配置 Actor
    const actor = vtkActor.newInstance();
    actor.setMapper(mapper); // 绑定 Mapper
    renderer.addActor(actor); // 将 Actor 添加到渲染器
    currentActors.push(actor); // 保存 Actor 以便清理

    // === 5. 渲染 ===
    const renderStart = performance.now(); // 记录渲染开始时间
    renderer.resetCamera(); // 重置相机以适应点云
    renderWindow.render(); // 触发渲染
    renderLog.value.push(`渲染耗时: ${(performance.now() - renderStart).toFixed(3)} ms`);

    // === 6. 总耗时 ===
    renderLog.value.push(`总耗时: ${(performance.now() - t0).toFixed(3)} ms`);

    // 保存文件信息
    fileInfo.value = { size: fileSizeMB, points: pointCount };

    // === 7. 自动把日志发给后端保存 ===
    try {
      await axios.post('http://localhost:5000/save-log', {
        logs: renderLog.value, // 渲染日志
        min_val: minValue.value, // 最小值
        max_val: maxValue.value, // 最大值
        point_count: pointCount // 点云点数
      });
      console.log("渲染日志已发送到后端保存");
    } catch (e) {
      console.warn("渲染日志发送失败", e); // 记录日志发送失败的警告
    }

    console.table(renderLog.value); // 在控制台以表格形式显示日志
  } catch (err) {
    // 处理请求、解压、解析或渲染过程中的错误
    error.value = `加载失败: ${err.message}`;
    console.error('加载或渲染 VTP 文件出错:', err);
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

/* 渲染窗口样式，占满剩余空间，深灰色背景以突出点云 */
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