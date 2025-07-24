<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的体视显微镜数据渲染应用，用于加载 VTI 格式的体数据并提取其外表面进行渲染。
  应用使用 vtkGeometryFilter 提取体数据的表面几何，并通过下拉菜单选择渲染模式（当前仅支持“外表面”模式）。
  用户加载 VTI 文件后，应用会渲染体数据的外部几何表面，并自动调整相机以适应渲染内容。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 使用 vtkGeometryFilter 提取体数据的外部几何表面。
  4. 创建 VTK 渲染管线（PolyDataMapper 和 Actor）并添加至渲染器。
  5. 当渲染模式变化时，更新表面几何并重新渲染。
  6. 初始化相机并触发渲染。
-->

<template>
  <!-- 主容器，包含渲染窗口和控制面板 -->
  <div class="viewer-container">
    <!-- VTK 渲染窗口，用于显示体数据的外部几何表面 -->
    <div ref="vtkContainer" class="vtk-container"></div>
    <!-- 控制面板：包含渲染模式选择下拉菜单 -->
    <div class="controls">
      <div>
        <label>Render Mode: </label>
        <!-- 下拉菜单选择渲染模式，当前仅支持“外表面” -->
        <select v-model="renderMode" @change="updateSurface">
          <option value="basic">外表面</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象
import vtkPolyDataMapper from '@kitware/vtk.js/Rendering/Core/PolyDataMapper'; // 用于映射几何数据到渲染对象
import vtkGeometryFilter from '@kitware/vtk.js/Filters/Core/GeometryFilter'; // 用于提取体数据的外部几何表面
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件

// 定义响应式变量和容器引用
const vtkContainer = ref(null); // 绑定 HTML 渲染容器
const renderMode = ref('basic'); // 渲染模式，默认为“外表面”

// 定义 VTK 对象引用，用于后续更新或渲染
let renderer, renderWindow, actor, imageData, geometryFilter;

// 提取并更新外表面的函数
function updateSurface() {
  // 检查体数据是否已加载
  if (!imageData) return;

  // 使用 vtkGeometryFilter 提取体数据的外部几何表面
  geometryFilter.setInputData(imageData);
  const surfacePolyData = geometryFilter.getOutputData();

  // 创建并配置 PolyDataMapper，将提取的表面几何映射到渲染对象
  const mapper = vtkPolyDataMapper.newInstance();
  mapper.setInputData(surfacePolyData);

  // 如果 Actor 未创建，则创建并添加到渲染器
  if (!actor) {
    actor = vtkActor.newInstance();
    renderer.addActor(actor);
  }

  // 为 Actor 设置 Mapper
  actor.setMapper(mapper);
  // 触发场景重新渲染
  renderWindow.render();
}

// 组件挂载时执行的初始化逻辑
onMounted(async () => {
  // 初始化 VTK 全屏渲染窗口，设置容器和样式
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: vtkContainer.value,
    containerStyle: { height: '100%', width: '100%' },
  });

  // 获取渲染器和渲染窗口
  renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();

  // 使用 fetch 加载 VTI 文件
  const response = await fetch('/SaltfFF.vti'); // 确保路径正确
  const arrayBuffer = await response.arrayBuffer(); // 获取文件数据的 ArrayBuffer

  // 创建 VTI 文件解析器并解析数据
  const reader = vtkXMLImageDataReader.newInstance();
  reader.parseAsArrayBuffer(arrayBuffer);
  imageData = reader.getOutputData(0); // 获取解析后的体数据

  // 创建 vtkGeometryFilter 实例，用于提取外部几何表面
  geometryFilter = vtkGeometryFilter.newInstance();

  // 调用 updateSurface 初始化渲染
  updateSurface();
  // 重置相机以适应渲染内容
  renderer.resetCamera();
  // 触发初始渲染
  renderWindow.render();
});
</script>

<style scoped>
/* 主容器样式，设置为纵向 flex 布局，占满视口高度 */
.viewer-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 渲染窗口样式，占满剩余空间，背景为黑色 */
.vtk-container {
  flex: 1;
  background: black;
  height: 100%;
}

/* 控制面板样式，设置浅灰色背景，包含渲染模式选择 */
.controls {
  padding: 10px;
  background-color: #f0f0f0;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

/* 控制面板子容器样式，设置 flex 布局以对齐内容 */
.controls div {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>