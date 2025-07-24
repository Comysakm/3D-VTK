<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于从后端获取并渲染 PLY 格式的点云数据。
  用户可以通过控制面板输入最小值和最大值，触发点云数据生成并在 3D 渲染窗口中显示。
  同时支持鼠标交互，显示鼠标悬停点的 3D 坐标（这个功能有问题，还得修改）。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置渲染窗口和背景。
  2. 用户在控制面板输入最小值和最大值，点击“Generate and Render”按钮。
  3. 向后端发送请求，获取 PLY 文件数据，并显示加载进度。
  4. 解析 PLY 文件，创建 VTK 渲染管线（Mapper 和 Actor）。
  5. 根据点云的标量数据应用颜色映射，或者使用默认颜色。
  6. 渲染点云并支持鼠标交互，显示点的 3D 坐标。
  7. 在组件卸载时清理资源。
-->

<template>
  <div class="container">
    <!-- VTK 渲染窗口，用于显示 3D 点云 -->
    <div ref="renderContainer" class="render-window"></div>

    <!-- 控制面板：用于调节最小值、最大值并触发点云生成 -->
    <div class="control">
      <h3>Point Cloud Filter</h3>
      <!-- 输入最小值的输入框 -->
      <div class="input-group">
        <label>Minimum Value: </label>
        <input v-model.number="minValue" type="number" placeholder="e.g., 1500" />
      </div>
      <!-- 输入最大值的输入框 -->
      <div class="input-group">
        <label>Maximum Value: </label>
        <input v-model.number="maxValue" type="number" placeholder="e.g., 4500" />
      </div>
      <!-- 触发点云生成和渲染的按钮，加载时禁用 -->
      <button :disabled="loading" @click="fetchPlyFile">Generate and Render</button>
      <!-- 显示加载进度 -->
      <p v-if="loading">Loading... ({{ progress }}%)</p>
      <!-- 显示错误信息 -->
      <p v-if="error" class="error">{{ error }}</p>
      <!-- 显示文件大小和点云点数 -->
      <p v-if="fileInfo">File Size: {{ fileInfo.size }} MB, Points: {{ fileInfo.points }}</p>
    </div>

    <!-- 显示鼠标悬停点的 3D 坐标 -->
    <div class="coordinate-display" id="coordinate-display"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载 VTK.js 的几何渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkPLYReader from '@kitware/vtk.js/IO/Geometry/PLYReader'; // 用于解析 PLY 文件
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象
import vtkPolyDataMapper from '@kitware/vtk.js/Rendering/Core/Mapper'; // 用于映射点云数据到渲染对象
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 用于颜色映射
import vtkCellPicker from '@kitware/vtk.js/Rendering/Core/CellPicker'; // 用于拾取鼠标位置的点

// 定义响应式变量
const minValue = ref(1500); // 最小值输入，默认为 1500
const maxValue = ref(4500); // 最大值输入，默认为 4500
const loading = ref(false); // 加载状态
const progress = ref(0); // 加载进度
const error = ref(''); // 错误信息
const fileInfo = ref(null); // 文件信息（大小和点数）
const renderContainer = ref(null); // 渲染容器 DOM 引用

// 定义 VTK 渲染相关变量
let fullScreenRenderer, renderer, renderWindow;

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  console.log('Initializing vtk.js renderer...');
  // 初始化 VTK 全屏渲染窗口，设置容器和背景颜色（黑色）
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value,
    background: [0, 0, 0],
  });
  renderer = fullScreenRenderer.getRenderer(); // 获取渲染器
  renderWindow = fullScreenRenderer.getRenderWindow(); // 获取渲染窗口

  // 添加鼠标移动事件监听器，用于显示鼠标悬停点的 3D 坐标
  const interactor = renderWindow.getInteractor();
  interactor.onMouseMove((event) => {
    // 获取鼠标在窗口中的位置
    const mousePos = interactor.getEventPosition();
    // 创建并配置点拾取器，设置容差值为 0.001
    const picker = vtkCellPicker.newInstance();
    picker.setTolerance(0.001);
    // 执行拾取操作，获取鼠标位置对应的 3D 点
    picker.pick(mousePos[0], mousePos[1], 0, renderer);

    const pickedPosition = picker.getPickPosition();
    if (pickedPosition) {
      // 如果拾取到点，获取其 3D 坐标并显示
      const [x, y, z] = pickedPosition;
      document.getElementById('coordinate-display').innerText = `X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)}`;
    }
  });
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 如果渲染器存在，释放其资源
  if (fullScreenRenderer) {
    fullScreenRenderer.delete();
  }
});

// 获取并渲染 PLY 文件的异步函数
async function fetchPlyFile() {
  // 记录请求开始时间并格式化为 HH-MM-SS
  const now = new Date();
  const timeMs = now.toISOString().split('T')[1].replace('z', '');
  console.log("提交范围时间", timeMs);

  // 验证输入值是否有效
  if (!minValue.value || !maxValue.value || minValue.value >= maxValue.value) {
    error.value = 'Please enter valid min and max values (min < max).';
    return;
  }

  // 设置加载状态
  loading.value = true;
  progress.value = 0;
  error.value = '';
  fileInfo.value = null;
  // 移除渲染器中的所有 Actor
  renderer.removeAllActors();

  try {
    // 向后端发送 POST 请求获取 PLY 文件
    const response = await axios.post(
      'http://localhost:5000/generate-ply', // Flask 后端端点
      { min_val: minValue.value, max_val: maxValue.value },
      {
        responseType: 'arraybuffer', // 以二进制数组形式接收响应
        onDownloadProgress: (progressEvent) => {
          // 计算并更新下载进度
          if (progressEvent.total) {
            progress.value = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          }
        },
      }
    );

    // 获取 PLY 文件数据并计算文件大小（MB）
    const arrayBuffer = response.data;
    const fileSizeMB = (arrayBuffer.byteLength / (1024 * 1024)).toFixed(2);
    console.log(`Received PLY file, size: ${fileSizeMB} MB`);

    // 创建 PLY 文件解析器并解析数据
    const reader = vtkPLYReader.newInstance();
    console.time('parse_ply');
    reader.parseAsArrayBuffer(arrayBuffer);
    console.timeEnd('parse_ply');

    // 获取解析后的点云数据
    const polyData = reader.getOutputData();
    // 计算点云中的点数（顶点数 / 3）
    const numPoints = polyData.getPoints()?.getNumberOfValues() / 3 || 0;
    console.log(`Number of Points: ${numPoints}`);
    console.log(`Bounds:`, polyData.getBounds());

    // 获取点云的标量数据
    const pointData = polyData.getPointData();
    const scalars = pointData.getArrayByName('scalar') || pointData.getArrayByName('volume') || pointData.getScalars();
    
    // 如果存在标量数据，记录其名称和范围
    if (scalars) {
      console.log('Scalar Array Name:', scalars.getName());
      console.log('Scalar Range:', scalars.getRange());
    } else {
      console.warn('No scalar data, using default color');
    }

    // 保存文件信息（大小和点数）
    fileInfo.value = { size: fileSizeMB, points: numPoints };

    // 创建并配置 VTK Mapper，将点云数据映射到渲染对象
    const mapper = vtkPolyDataMapper.newInstance();
    mapper.setInputData(polyData);

    // 创建 VTK Actor，用于渲染点云
    const actor = vtkActor.newInstance();
    actor.setMapper(mapper);
    
    // 如果存在标量数据，应用颜色映射
    if (scalars) {
      mapper.setScalarVisibility(true); // 启用标量可视化
      mapper.setScalarModeToUsePointData(); // 使用点数据
      mapper.setColorModeToMapScalars(); // 映射标量到颜色
      // 创建颜色查找表并设置颜色映射
      const lut = vtkColorTransferFunction.newInstance();
      const scalarRange = scalars.getRange();
      lut.addRGBPoint(scalarRange[0], 0, 0, 1); // 最小值映射为蓝色
      lut.addRGBPoint((scalarRange[0] + scalarRange[1]) / 2, 0, 1, 0); // 中间值映射为绿色
      lut.addRGBPoint(scalarRange[1], 1, 0, 0); // 最大值映射为红色
      mapper.setLookupTable(lut);
      mapper.setScalarRange(scalarRange[0], scalarRange[1]); // 设置标量范围
    } else {
      // 如果没有标量数据，使用默认灰色
      mapper.setColorModeToDefault();
      actor.getProperty().setColor(128, 128, 128);
    }

    // 将 Actor 添加到渲染器
    renderer.addActor(actor);
    // 重置相机以适应点云
    renderer.resetCamera();
    console.log('Starting render...');
    // 触发渲染
    renderWindow.render();
    // 记录渲染完成时间
    const now = new Date();
    const timeMs = now.toISOString().split('T')[1].replace('z', '');
    console.log("渲染成功时间", timeMs);
    console.log('Render complete.');
  } catch (err) {
    // 处理错误并显示错误信息
    error.value = `Error: ${err.message}`;
    console.error('Error fetching or rendering PLY:', err);
  } finally {
    // 无论成功或失败，结束加载状态
    loading.value = false;
    progress.value = 0;
  }
}
</script>

<style scoped>
/* 容器样式，设置整体布局为 flex 水平排列，占满视口高度 */
.container {
  display: flex;
  flex-direction: row;
  height: 100vh;
  position: relative;
}

/* 渲染窗口样式，占满剩余空间，背景为黑色 */
.render-window {
  flex: 1;
  background: black;
  position: relative;
  z-index: 1;
}

/* 控制面板样式，固定宽度，浅灰色背景，允许垂直滚动 */
.control {
  width: 250px;
  padding: 1rem;
  background-color: #f4f4f4;
  font-family: sans-serif;
  overflow-y: auto;
  z-index: 2;
  position: relative;
}

/* 控制面板标题样式 */
.control h3 {
  margin-bottom: 1rem;
}

/* 输入组样式，设置间距 */
.input-group {
  margin: 10px 0;
}

/* 输入组标签样式 */
.input-group label {
  margin-right: 10px;
}

/* 输入框样式，设置内边距和宽度 */
input {
  padding: 5px;
  width: 100px;
}

/* 按钮样式，蓝色背景，白色文字 */
button {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  cursor: pointer;
}

/* 禁用按钮样式，灰色背景，禁用鼠标指针 */
button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

/* 错误信息样式，红色文字 */
.error {
  color: red;
}

/* 坐标显示样式，绝对定位，白色文字，半透明黑色背景 */
.coordinate-display {
  position: absolute;
  top: 20px;
  left: 20px;
  color: white;
  font-size: 14px;
  background-color: rgba(0, 0, 0, 0.6);
  padding: 5px;
  border-radius: 5px;
  z-index: 3;
}
</style>