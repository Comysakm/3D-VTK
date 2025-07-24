<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的等值面渲染应用，用于加载并渲染 VTI 格式的体视显微镜数据（体视显微镜体数据的等值面）。
  用户可以通过滑块调整等值面值（contourValue），动态更新渲染的等值面，并实时显示在 3D 渲染窗口中。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 使用 Marching Cubes 算法提取指定等值面的几何数据。
  4. 创建 VTK 渲染管线（Mapper 和 Actor）并添加至渲染器。
  5. 通过滑块动态调整等值面值，更新 Marching Cubes 算法并重新渲染。
  6. 打印三角面数以便调试，自动调整相机以适应等值面。
-->

<template>
  <!-- 主容器，包含渲染窗口和控制面板 -->
  <div class="viewer-wrapper">
    <!-- VTK 渲染窗口，用于显示 3D 等值面 -->
    <div ref="vtkContainer" class="vtk-viewer-container"></div>

    <!-- 控制面板：包含滑块，用于调节等值面值 -->
    <div class="control-panel">
      <label>
        <!-- 显示当前等值面值 -->
        等值面值 (contourValue): {{ contourValue }}
        <!-- 滑块输入，用于动态调整等值面值 -->
        <input
          type="range"
          min="1500"
          max="4482"
          step="1"
          v-model.number="contourValue"
          @input="updateContourValue"
        />
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载 VTK.js 的几何渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件
import vtkImageMarchingCubes from '@kitware/vtk.js/Filters/General/ImageMarchingCubes'; // 用于提取等值面
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper'; // 用于映射几何数据到渲染对象
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象

// 定义响应式变量和容器引用
const vtkContainer = ref(null); // 绑定 HTML 渲染容器
const contourValue = ref(4482); // 当前等值面值，初始值为 4482

// 定义 VTK 对象引用，用于后续更新或渲染
let marchingCubes, renderWindow, mapper;

// 组件挂载时执行的初始化逻辑
onMounted(async () => {
  // 初始化 VTK 全屏渲染窗口，设置容器和样式
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: vtkContainer.value,
    containerStyle: { height: '100%', width: '100%', position: 'relative' },
  });
  const renderer = fullScreenRenderer.getRenderer(); // 获取渲染器
  renderWindow = fullScreenRenderer.getRenderWindow(); // 获取渲染窗口

  // 使用 fetch 加载 VTI 文件
  const response = await fetch('/SaltfFF.vti');
  const arrayBuffer = await response.arrayBuffer(); // 获取文件数据的 ArrayBuffer

  // 创建 VTI 文件解析器并解析数据
  const reader = vtkXMLImageDataReader.newInstance();
  reader.parseAsArrayBuffer(arrayBuffer);

  // 创建 Marching Cubes 实例，用于提取等值面
  marchingCubes = vtkImageMarchingCubes.newInstance({
    contourValue: contourValue.value, // 设置初始等值面值
  });

  // 将 VTI 数据连接到 Marching Cubes 算法
  marchingCubes.setInputConnection(reader.getOutputPort());

  // 创建并配置 Mapper，将 Marching Cubes 的输出（几何数据）映射到渲染对象
  mapper = vtkMapper.newInstance();
  mapper.setInputConnection(marchingCubes.getOutputPort());

  // 创建 VTK Actor，用于渲染等值面
  const actor = vtkActor.newInstance();
  actor.setMapper(mapper);
  // 将 Actor 添加到渲染器
  renderer.addActor(actor);

  // 打印三角面数以便调试
  const polyData = marchingCubes.getOutputData();
  consolemissing
console.log('面数:', polyData.getPolys().getNumberOfCells());

  // 初始化相机并触发渲染
  renderer.resetCamera();
  renderWindow.render();
});

// 当滑块值变化时，更新等值面并重新渲染
function updateContourValue() {
  if (marchingCubes) {
    try {
      // 更新 Marching Cubes 算法的等值面值
      marchingCubes.setContourValue(contourValue.value);
      marchingCubes.update(); // 重新计算等值面几何数据

      // 触发场景重新渲染
      renderWindow.render();
    } catch (error) {
      // 处理更新等值面值时的错误
      alert('更新等值面值时出错: ' + error.message);
    }
  }
}
</script>

<style scoped>
/* 主容器样式，设置 flex 布局，占满视口高度 */
.viewer-wrapper {
  display: flex;
  flex-direction: row;
  height: 100vh;
}

/* 渲染窗口样式，占满剩余空间，背景为黑色 */
.vtk-viewer-container {
  flex: 1;
  background: black;
}

/* 控制面板样式，固定宽度，浅灰色背景 */
.control-panel {
  width: 250px;
  padding: 1rem;
  background-color: #f4f4f4;
  font-family: sans-serif;
}

/* 控制面板标签样式，设置下边距 */
.control-panel label {
  display: block;
  margin-bottom: 1rem;
}
</style>