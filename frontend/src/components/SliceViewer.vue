<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的体视显微镜数据切片渲染应用，用于加载 VTI 格式的体数据并在 X、Y、Z 三个方向上显示切片。
  用户可以通过滑块调整 X、Y、Z 方向的切片索引，动态更新显示的切片。
  应用使用正交投影渲染切片，并支持半透明叠加效果以便同时查看多个切片。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 获取体数据的维度和标量范围，初始化滑块范围和切片索引。
  4. 为 X、Y、Z 方向创建切片渲染管线（ImageMapper 和 ImageSlice）。
  5. 配置切片的颜色窗口、不透明度，并添加至渲染器。
  6. 当滑块值变化时，更新切片索引并重新渲染。
  7. 使用正交投影相机并自动调整视角。
-->

<template>
  <!-- 主容器，包含控制面板和渲染窗口 -->
  <div class="viewer-container">
    <!-- 控制面板：包含 X、Y、Z 方向切片索引的滑块 -->
    <div class="controls">
      <!-- X 方向切片索引滑块 -->
      <label>
        X:
        <input type="range" v-model.number="sliceX" @input="updateSlices" :min="0" :max="dims[0]-1">
      </label>
      <!-- Y 方向切片索引滑块 -->
      <label>
        Y:
        <input type="range" v-model.number="sliceY" @input="updateSlices" :min="0" :max="dims[1]-1">
      </label>
      <!-- Z 方向切片索引滑块 -->
      <label>
        Z:
        <input type="range" v-model.number="sliceZ" @input="updateSlices" :min="0" :max="dims[2]-1">
      </label>
    </div>

    <!-- VTK 渲染容器，用于显示 X、Y、Z 方向的切片 -->
    <div ref="vtkContainer" class="vtk-container"></div>
  </div>
</template>

<script setup>
// 导入 Vue 3 的组合式 API
import { ref, onMounted, reactive } from 'vue';

// 导入 VTK.js 的相关模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件
import vtkImageMapper from '@kitware/vtk.js/Rendering/Core/ImageMapper'; // 用于映射切片数据
import vtkImageSlice from '@kitware/vtk.js/Rendering/Core/ImageSlice'; // 用于渲染切片
import vtkAxesActor from '@kitware/vtk.js/Rendering/Core/AxesActor'; // 用于渲染坐标轴（未使用）
import vtkOrientationMarkerWidget from '@kitware/vtk.js/Interaction/Widgets/OrientationMarkerWidget'; // 用于显示方向标记（未使用）

// 定义响应式变量
const vtkContainer = ref(null); // 绑定 HTML 渲染容器
const sliceX = ref(0); // X 方向切片索引
const sliceY = ref(0); // Y 方向切片索引
const sliceZ = ref(0); // Z 方向切片索引
const dims = reactive([100, 100, 100]); // 体数据的维度，初始值为占位值

// 定义 VTK 对象引用
let renderWindow, actorX, actorY, actorZ, mapperX, mapperY, mapperZ;

// 更新切片的函数，当滑块值变化时调用
const updateSlices = () => {
  // 更新 X、Y、Z 方向的切片索引
  mapperX.setISlice(sliceX.value);
  mapperY.setJSlice(sliceY.value);
  mapperZ.setKSlice(sliceZ.value);
  // 打印当前切片索引以便调试
  console.log(`更新切片： बड़ा X=${sliceX.value}, Y=${sliceY.value}, Z=${sliceZ.value}`);
  // 触发场景重新渲染
  renderWindow.render();
};

// 组件挂载时执行的初始化逻辑
onMounted(async () => {
  // 初始化 VTK 全屏渲染窗口，设置背景和容器样式
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    background: [0, 0, 0], // 背景设为黑色
    rootContainer: vtkContainer.value, // 绑定 Vue 的渲染容器
    containerStyle: { width: '100%', height: '100%' },
  });

  // 获取渲染器和渲染窗口
  const renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();

  // 使用 fetch 加载 VTI 文件
  const response = await fetch('/SaltfFF.vti'); // 确保路径正确
  const arrayBuffer = await response.arrayBuffer(); // 获取文件数据的 ArrayBuffer

  // 创建 VTI 文件解析器并解析数据
  const reader = vtkXMLImageDataReader.newInstance();
  reader.parseAsArrayBuffer(arrayBuffer);

  // 获取解析后的体数据
  const imageData = reader.getOutputData(0);

  // 获取体数据的范围并更新维度
  const extent = imageData.getExtent();
  dims[0] = extent[1] + 1; // X 方向维度
  dims[1] = extent[3] + 1; // Y 方向维度
  dims[2] = extent[5] + 1; // Z 方向维度

  // 初始化切片索引为体数据的中间位置
  sliceX.value = Math.floor(dims[0] / 2);
  sliceY.value = Math.floor(dims[1] / 2);
  sliceZ.value = Math.floor(dims[2] / 2);

  // 获取体数据的标量范围，设置颜色窗口
  const scalars = imageData.getPointData().getScalars();
  const dataRange = scalars.getRange(); // [min, max]
  const window = dataRange[1] - dataRange[0]; // 颜色窗口宽度
  const level = (dataRange[1] + dataRange[0]) / 2; // 颜色窗口中心
  console.log("dims", dims[0], dims[1], dims[2]);

  // 创建 X 方向切片渲染管线
  mapperX = vtkImageMapper.newInstance();
  mapperX.setInputData(imageData);
  mapperX.setSlicingMode(vtkImageMapper.SlicingMode.I); // 设置为 X 方向切片
  mapperX.setISlice(sliceX.value);

  actorX = vtkImageSlice.newInstance();
  actorX.setMapper(mapperX);

  // 创建 Y 方向切片渲染管线
  mapperY = vtkImageMapper.newInstance();
  mapperY.setInputData(imageData);
  mapperY.setSlicingMode(vtkImageMapper.SlicingMode.J); // 设置为 Y 方向切片
  mapperY.setJSlice(sliceY.value);

  actorY = vtkImageSlice.newInstance();
  actorY.setMapper(mapperY);

  // 创建 Z 方向切片渲染管线
  mapperZ = vtkImageMapper.newInstance();
  mapperZ.setInputData(imageData);
  mapperZ.setSlicingMode(vtkImageMapper.SlicingMode.K); // 设置为 Z 方向切片
  mapperZ.setKSlice(sliceZ.value);

  actorZ = vtkImageSlice.newInstance();
  actorZ.setMapper(mapperZ);

  // 配置切片的渲染属性（颜色窗口和不透明度）
  actorX.getProperty().setColorWindow(window);
  actorX.getProperty().setColorLevel(level);
  actorX.getProperty().setOpacity(0.6); // 设置 X 方向切片半透明
  actorY.getProperty().setColorWindow(window);
  actorY.getProperty().setColorLevel(level);
  actorY.getProperty().setOpacity(0.6); // 设置 Y 方向切片半透明
  actorZ.getProperty().setColorWindow(window);
  actorZ.getProperty().setColorLevel(level);
  actorZ.getProperty().setOpacity(0.6); // 设置 Z 方向切片半透明

  // 将 X、Y、Z 方向的切片 Actor 添加到渲染器
  renderer.addActor(actorX);
  renderer.addActor(actorY);
  renderer.addActor(actorZ);
  // 打印渲染器中的 Actor 列表以便调试
  console.log('渲染器中的演员:', renderer.getActors());

  // 设置相机为正交投影，避免透视变形
  const camera = renderer.getActiveCamera();
  camera.setParallelProjection(true);
  camera.setFocalPoint(0, 0, 0); // 相机焦点设为原点
  camera.setPosition(1, 1, 1); // 相机位置设为 (1, 1, 1)

  // 重置相机以适应渲染内容
  renderer.resetCamera();

  // 触发初始渲染
  renderWindow.render();
});
</script>

<style scoped>
/* 主容器样式，设置为横向 flex 布局，占满视口高度 */
.viewer-container {
  display: flex;
  flex-direction: row;
  height: 100vh;
}

/* 控制面板样式，纵向排列滑块，深灰色背景，白色文字 */
.controls {
  display: flex;
  flex-direction: column; 
  justify-content: center;
  gap: 10px; 
  background: #222;
  color: #fff;
  padding: 10px;
}

/* 渲染窗口样式，占满剩余空间，背景为浅粉色 */
.vtk-container {
  flex: 1;
  background: rgb(229, 208, 208);
  height: 100vh;
}
</style>