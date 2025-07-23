<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的体视显微镜数据体渲染应用，用于加载 VTI 格式的体数据并进行体渲染。
  用户可以通过滑块调整标量值的范围（rangeMin 和 rangeMax），动态控制体渲染的不透明度映射，突出显示特定标量值范围的体视显微镜数据。
  应用使用颜色映射和不透明度映射来可视化体数据的不同标量值。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 获取体数据的标量范围，初始化滑块的范围和默认值。
  4. 配置颜色映射（RGB）和不透明度映射，根据用户调整的范围动态更新不透明度。
  5. 创建 VTK 体渲染管线（VolumeMapper 和 Volume）并添加至渲染器。
  6. 当滑块值变化时，更新不透明度映射并重新渲染。
-->

<template>
  <!-- 主容器，包含渲染窗口和控制面板 -->
  <div class="viewer-wrapper">
    <!-- VTK 渲染窗口，用于显示体渲染结果 -->
    <div ref="vtkContainer" class="vtk-viewer-container"></div>

    <!-- 控制面板，包含最小值和最大值滑块 -->
    <div class="control-panel">
      <!-- 最小值滑块，用于控制不透明度范围的下限 -->
      <label>
        最小值: {{ rangeMin }}
        <input
          type="range"
          :min="dataRange[0]"
          :max="dataRange[1]"
          :step="1"
          v-model.number="rangeMin"
          @input="updateOpacityRange"
        />
      </label>

      <!-- 最大值滑块，用于控制不透明度范围的上限 -->
      <label>
        最大值: {{ rangeMax }}
        <input
          type="range"
          :min="dataRange[0]"
          :max="dataRange[1]"
          :step="1"
          v-model.number="rangeMax"
          @input="updateOpacityRange"
        />
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Volume'; // 加载 VTK.js 的体渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'; // VTK 体渲染对象
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'; // 用于映射体数据到渲染对象
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 用于颜色映射
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'; // 用于不透明度映射

// 定义响应式变量
const vtkContainer = ref(null); // 绑定 HTML 渲染容器
const rangeMin = ref(0); // 标量范围最小值
const rangeMax = ref(100); // 标量范围最大值
const dataRange = ref([0, 100]); // 体数据的实际标量范围

// 定义 VTK 对象引用
let renderWindow, renderer;
let ctfun, ofun; // 颜色映射和不透明度映射函数
let volume; // 体渲染对象

// 组件挂载时执行的初始化逻辑
onMounted(async () => {
  // 初始化 VTK 全屏渲染窗口，设置容器和样式
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: vtkContainer.value,
    containerStyle: { height: '100%', width: '100%', position: 'relative' },
  });
  renderer = fullScreenRenderer.getRenderer(); // 获取渲染器
  renderWindow = fullScreenRenderer.getRenderWindow(); // 获取渲染窗口

  // 使用 fetch 加载 VTI 文件
  const response = await fetch('/SaltfFF.vti'); // 确保路径正确
  const arrayBuffer = await response.arrayBuffer(); // 获取文件数据的 ArrayBuffer

  // 创建 VTI 文件解析器并解析数据
  const reader = vtkXMLImageDataReader.newInstance();
  reader.parseAsArrayBuffer(arrayBuffer);

  // 获取解析后的体数据
  const imageData = reader.getOutputData(0);

  // 获取体数据的标量范围并设置滑块范围
  const scalars = imageData.getPointData().getScalars();
  dataRange.value = scalars.getRange();
  rangeMin.value = dataRange.value[0]; // 设置初始最小值
  rangeMax.value = dataRange.value[1]; // 设置初始最大值

  // 创建并配置 VolumeMapper，将体数据映射到渲染对象
  const mapper = vtkVolumeMapper.newInstance();
  mapper.setInputData(imageData);

  // 创建体渲染对象
  volume = vtkVolume.newInstance();

  // 配置颜色映射
  ctfun = vtkColorTransferFunction.newInstance();
  const [min, max] = dataRange.value;
  ctfun.addRGBPoint(min, 0.0, 0.0, 1.0); // 最小值映射为蓝色
  ctfun.addRGBPoint((min + max) / 2, 0.0, 1.0, 0.0); // 中间值映射为绿色
  ctfun.addRGBPoint(max, 1.0, 0.0, 0.0); // 最大值映射为红色

  // 初始化不透明度映射
  ofun = vtkPiecewiseFunction.newInstance();
  updateOpacityRange(); // 调用函数初始化不透明度映射

  // 配置体渲染属性
  const property = volume.getProperty();
  property.setRGBTransferFunction(0, ctfun); // 设置颜色映射
  property.setScalarOpacity(0, ofun); // 设置不透明度映射
  property.setScalarOpacityUnitDistance(0, 2.0); // 设置不透明度单位距离

  // 为体对象设置 Mapper
  volume.setMapper(mapper);

  // 将体对象添加到渲染器
  renderer.addVolume(volume);
  // 重置相机以适应渲染内容
  renderer.resetCamera();
  // 触发初始渲染
  renderWindow.render();
});

// 更新不透明度映射范围的函数
function updateOpacityRange() {
  if (!ofun) return;

  // 清空现有的不透明度映射点
  ofun.removeAllPoints();

  const [min, max] = dataRange.value;

  // 配置不透明度映射：范围外的值为完全透明，范围内为半透明
  ofun.addPoint(min, 0.0); // 数据最小值完全透明
  ofun.addPoint(rangeMin.value, 0.0); // 用户选择的最小值完全透明

  ofun.addPoint(rangeMin.value + 0.01, 0.5); // 最小值稍高处为半透明
  ofun.addPoint(rangeMax.value, 0.5); // 最大值为半透明

  ofun.addPoint(rangeMax.value + 0.01, 0.0); // 最大值稍高处完全透明
  ofun.addPoint(max, 0.0); // 数据最大值完全透明

  // 触发场景重新渲染
  renderWindow.render();
}
</script>

<style scoped>
/* 主容器样式，设置为横向 flex 布局，占满视口高度 */
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